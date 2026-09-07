from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from leon_control_plane.agent_run_model import (
    SUPPORTED_AGENT_RUN_ROLES,
    estimate_agent_run_cost,
    next_action_for_review_status,
    normalize_agent_run_role,
)
from leon_control_plane.morning_brief import build_morning_brief_from_run
from leon_control_plane.risk_policy import evaluate_action_policy
from leon_control_plane.secret_scanner import (
    SecretScanError,
    assert_no_secrets,
    contains_secret,
    redact_text,
    redact_value,
    scan_value,
)
from leon_control_plane.transparency import build_transparency_inspectors


TASK_STATUSES = {
    "new",
    "planned",
    "active",
    "waiting_for_approval",
    "waiting_for_secret",
    "waiting_for_user",
    "blocked",
    "review",
    "done",
    "rejected",
}

DECISION_FEEDBACK_TYPES = {"useful", "wrong", "risky", "low_value"}
ROUTING_EVAL_ROUTES = {
    "direct_answer",
    "clarification_required",
    "quick_tool_use",
    "memory_retrieval",
    "shell_agent_flow",
    "research_agent",
    "task_queue",
    "approval_required",
    "refuse_redirect",
}
MEMORY_STATUSES = {"candidate", "active", "rejected", "deleted", "scrubbed"}
MEMORY_TYPES = {"session", "working", "long_term", "episodic", "negative", "preference", "project_fact"}
MEMORY_SENSITIVITY_LEVELS = {"low", "medium", "high"}
MEMORY_PRIVACY_LEVELS = {"normal", "private", "sensitive"}
SOURCE_RECORD_TYPES = {
    "local_document",
    "project_file",
    "repo_doc",
    "task",
    "leon_run",
    "mail_message",
    "calendar_event",
}
SOURCE_RECORD_STATUSES = {"active", "deleted", "scrubbed", "blocked_secret"}
GRAPH_ENTITY_TYPES = {
    "document",
    "project",
    "task",
    "person",
    "organization",
    "decision",
    "memory",
    "source",
    "tool",
    "agent_run",
    "workflow",
    "risk",
    "approval",
    "component",
}
GRAPH_RELATIONSHIP_TYPES = {
    "belongs_to",
    "mentions",
    "depends_on",
    "derived_from",
    "conflicts_with",
    "supersedes",
    "requested_by",
    "generated_by",
    "approved_by",
    "blocked_by",
    "related_to",
}
MEMORY_CONFLICT_STATUSES = {"none", "conflicted", "resolved"}
RETRIEVAL_SCOPES = {"context", "project", "document", "memory", "source"}
RETRIEVAL_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]{1,}", re.IGNORECASE)
RETRIEVAL_STOPWORDS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "ask",
    "can",
    "context",
    "does",
    "document",
    "documents",
    "for",
    "from",
    "have",
    "how",
    "into",
    "is",
    "it",
    "know",
    "memory",
    "of",
    "on",
    "or",
    "project",
    "question",
    "show",
    "source",
    "sources",
    "tell",
    "that",
    "the",
    "this",
    "to",
    "what",
    "when",
    "where",
    "which",
    "why",
    "with",
}

APPROVAL_STATUSES = {"pending", "approved", "rejected", "expired", "consumed"}

ROLLBACK_RECORD_KINDS = {"cache", "local_persistent", "code_system", "external_write"}
ROLLBACK_STATUSES = {
    "prepared",
    "delete_supported",
    "undo_supported",
    "scrub_supported",
    "compensation_available",
    "compensation_unavailable",
    "applied",
    "deleted",
    "scrubbed",
    "not_applicable",
}

BASELINE_TRANSITIONS = {
    "new": {"planned"},
    "planned": {"active", "waiting_for_approval"},
    "active": {"waiting_for_approval", "waiting_for_secret", "waiting_for_user", "blocked", "review"},
    "review": {"done", "rejected"},
    "blocked": {"active"},
    "waiting_for_approval": {"active", "blocked"},
    "waiting_for_secret": {"active"},
    "waiting_for_user": {"active"},
    "done": {"planned"},
    "rejected": {"planned"},
}


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def slug_id(prefix: str, title: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in title).strip("-")
    slug = "-".join(part for part in slug.split("-") if part)
    return f"{prefix}-{slug[:48] or uuid.uuid4().hex[:12]}"


def _normalize_source_refs(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        value = [part.strip() for part in value.splitlines()]
    if not isinstance(value, list):
        raise ValueError("source_refs must be a list of strings or newline-separated string")
    refs: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            assert_no_secrets("source_refs", text)
            refs.append(text)
    return refs


def _normalize_value_score(value: Any) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        score = 3
    if score < 0 or score > 5:
        raise ValueError("value_score must be between 0 and 5")
    return score


def _reject_secret_like_text(label: str, value: str) -> None:
    assert_no_secrets(label, value or "")


def _reject_unsafe_memory_text(label: str, value: str) -> None:
    assert_no_secrets(label, value or "")


def _normalize_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.5
    if confidence < 0 or confidence > 1:
        raise ValueError("confidence must be between 0 and 1")
    return round(confidence, 4)


def _normalize_graph_entity_type(value: Any) -> str:
    entity_type = str(value or "memory").strip().lower().replace("-", "_").replace(" ", "_")
    if entity_type not in GRAPH_ENTITY_TYPES:
        raise ValueError("invalid graph entity type")
    return entity_type


def _normalize_graph_relationship_type(value: Any) -> str:
    relationship_type = str(value or "related_to").strip().lower().replace("-", "_").replace(" ", "_")
    if relationship_type not in GRAPH_RELATIONSHIP_TYPES:
        raise ValueError("invalid graph relationship type")
    return relationship_type


def _json_dumps(value: Any) -> str:
    return json.dumps(_redact_audit_value(value), ensure_ascii=False, sort_keys=True)


def _json_loads(value: Any, fallback: Any) -> Any:
    if value is None or value == "":
        return fallback
    try:
        return json.loads(str(value))
    except (TypeError, json.JSONDecodeError):
        return fallback


def _list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [value]


def redact_audit_text(value: str) -> str:
    return redact_text(value or "")


def _redact_audit_value(value: Any) -> Any:
    return redact_value(value)


def _as_non_empty_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        value = [str(value)]
    return [redact_audit_text(str(item).strip()) for item in value if str(item).strip()]


def _compact_summary(value: Any, fallback: str) -> str:
    text = redact_audit_text(str(value or fallback or "").strip())
    if len(text) <= 280:
        return text
    return text[:277].rstrip() + "..."


def _memory_query_from_run(run: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("action_results", "failures", "sources", "changes"):
        collection = run.get(key)
        if not isinstance(collection, list):
            continue
        for item in collection[:8]:
            if not isinstance(item, dict):
                continue
            for field in ("action_id", "title", "summary", "reason", "source_ref", "ref", "type"):
                value = str(item.get(field) or "").strip()
                if value and value not in parts:
                    parts.append(value)
    return " ".join(parts)[:1000] or "night queue morning brief context"


def _normalize_recovery_suggestions(value: Any, *, fallback_reason: str = "") -> list[dict[str, str]]:
    if value is None or value == "":
        value = []
    if isinstance(value, str):
        value = [{"action": "review_failure", "summary": value}]
    if not isinstance(value, list):
        value = [value]
    suggestions: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, dict):
            action = str(item.get("action") or item.get("type") or "review_failure").strip()
            summary = str(item.get("summary") or item.get("suggestion") or item.get("reason") or "").strip()
        else:
            action = "review_failure"
            summary = str(item or "").strip()
        if not summary:
            continue
        suggestions.append(
            {
                "action": redact_audit_text(action or "review_failure"),
                "summary": redact_audit_text(summary),
            }
        )
    if suggestions:
        return suggestions[:6]
    reason = redact_audit_text(str(fallback_reason or "The autonomous task failed before producing a reviewable result."))
    return [
        {
            "action": "review_failure_log",
            "summary": f"Inspect the failed run evidence and audit event: {reason}",
        },
        {
            "action": "retry_after_scope_fix",
            "summary": "Retry only after narrowing scope, fixing the reported blocker, or moving the work behind approval.",
        },
        {
            "action": "use_rollback_record",
            "summary": "Use the attached rollback status or registry record to delete temporary output or undo local changes before retrying.",
        },
    ]


def _approval_plan_fingerprint(
    *,
    action_type: str,
    summary: str,
    reason: str,
    affected_systems: str,
    permissions: str,
    external_effect: str,
    cost_estimate: str,
    risk_level: str,
    risk_class: str,
    expected_change: str,
    rollback_plan: str,
    failure_mode: str,
) -> str:
    payload = {
        "action_type": action_type.strip(),
        "summary": summary.strip(),
        "reason": reason.strip(),
        "affected_systems": affected_systems.strip(),
        "permissions": permissions.strip(),
        "external_effect": external_effect.strip(),
        "cost_estimate": cost_estimate.strip(),
        "risk_level": risk_level.strip(),
        "risk_class": risk_class.strip(),
        "expected_change": expected_change.strip(),
        "rollback_plan": rollback_plan.strip(),
        "failure_mode": failure_mode.strip(),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _retrieval_tokens(value: Any) -> list[str]:
    tokens: list[str] = []
    for match in RETRIEVAL_TOKEN_RE.findall(str(value or "").lower()):
        token = match.strip("_-")
        if len(token) < 2 or token in RETRIEVAL_STOPWORDS:
            continue
        if token not in tokens:
            tokens.append(token)
    return tokens


def _retrieval_token_score(query_tokens: list[str], value: Any) -> float:
    if not query_tokens:
        return 0
    haystack_tokens = set(_retrieval_tokens(value))
    if not haystack_tokens:
        return 0
    overlap = sum(1 for token in query_tokens if token in haystack_tokens)
    return round(overlap / len(query_tokens), 4)


def _retrieval_excerpt(value: Any, query_tokens: list[str], *, limit: int = 280) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return redact_audit_text(text)
    lowered = text.lower()
    positions = [lowered.find(token.lower()) for token in query_tokens if lowered.find(token.lower()) >= 0]
    if positions:
        start = max(0, min(positions) - 80)
    else:
        start = 0
    excerpt = text[start : start + limit].strip()
    if start > 0:
        excerpt = "..." + excerpt
    if start + limit < len(text):
        excerpt = excerpt.rstrip() + "..."
    return redact_audit_text(excerpt)


def _risk_class_from_level(risk_level: str) -> str:
    normalized = str(risk_level or "").strip().lower()
    if normalized == "low":
        return "R1"
    if normalized == "medium":
        return "R2"
    if normalized == "high":
        return "R4"
    return "R3"


def _routing_decision_outcome(
    decision_id: str,
    *,
    proposals_by_decision: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    proposals = proposals_by_decision.get(decision_id, [])
    if not proposals:
        return {
            "status": "recorded",
            "summary": "Decision recorded; no orchestration proposal has been created yet.",
            "orchestration_proposal_ids": [],
            "task_ids": [],
            "approval_ids": [],
        }
    task_ids = [str(item.get("applied_task_id") or "") for item in proposals if item.get("applied_task_id")]
    approval_ids = [str(item.get("applied_approval_id") or "") for item in proposals if item.get("applied_approval_id")]
    statuses = {str(item.get("status") or "") for item in proposals}
    if "applied" in statuses:
        status = "applied"
        summary = "A reviewed orchestration proposal was applied without executing external actions."
    elif "rejected" in statuses:
        status = "rejected"
        summary = "An orchestration proposal for this decision was rejected during review."
    else:
        status = "proposal_prepared"
        summary = "A reviewable orchestration proposal is prepared for this decision."
    return {
        "status": status,
        "summary": summary,
        "orchestration_proposal_ids": [str(item.get("id")) for item in proposals if item.get("id")],
        "task_ids": task_ids,
        "approval_ids": approval_ids,
    }


def _routing_feedback_summary(feedback: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {feedback_type: 0 for feedback_type in sorted(DECISION_FEEDBACK_TYPES)}
    latest: dict[str, Any] | None = None
    for item in feedback:
        feedback_type = str(item.get("feedback_type") or "")
        if feedback_type in counts:
            counts[feedback_type] += 1
        if latest is None or str(item.get("created_at") or "") > str(latest.get("created_at") or ""):
            latest = item
    return {
        "count": len(feedback),
        "allowed_types": sorted(DECISION_FEEDBACK_TYPES),
        "counts": counts,
        "latest": latest or {},
    }


def _routing_eval_impact(current: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    quality = current.get("routing_quality") if isinstance(current.get("routing_quality"), dict) else {}
    safety = current.get("routing_safety") if isinstance(current.get("routing_safety"), dict) else {}
    current_accuracy = float(quality.get("accuracy") if quality.get("accuracy") is not None else 0)
    current_safety_failures = int(safety.get("safety_failures") or 0)
    current_failed = int(current.get("failed") or quality.get("failed") or 0)
    if not previous:
        return {
            "baseline_run_id": "",
            "baseline_release_label": "",
            "accuracy_delta": None,
            "failed_delta": None,
            "safety_failure_delta": None,
            "summary": "No previous eval run is available for comparison.",
        }

    previous_summary = previous.get("summary") if isinstance(previous.get("summary"), dict) else {}
    previous_quality = previous_summary.get("routing_quality") if isinstance(previous_summary.get("routing_quality"), dict) else {}
    previous_safety = previous_summary.get("routing_safety") if isinstance(previous_summary.get("routing_safety"), dict) else {}
    previous_accuracy = float(previous_quality.get("accuracy") if previous_quality.get("accuracy") is not None else 0)
    previous_safety_failures = int(previous_safety.get("safety_failures") or 0)
    previous_failed = int(previous_summary.get("failed") or previous_quality.get("failed") or 0)
    accuracy_delta = round(current_accuracy - previous_accuracy, 4)
    failed_delta = current_failed - previous_failed
    safety_failure_delta = current_safety_failures - previous_safety_failures
    return {
        "baseline_run_id": previous.get("id") or "",
        "baseline_release_label": previous.get("release_label") or "",
        "accuracy_delta": accuracy_delta,
        "failed_delta": failed_delta,
        "safety_failure_delta": safety_failure_delta,
        "summary": (
            f"Accuracy delta {accuracy_delta:+.4f}; "
            f"failed cases delta {failed_delta:+d}; "
            f"safety failures delta {safety_failure_delta:+d}."
        ),
    }


def _infer_audit_risk_class(event_type: str, risk_level: str, payload: dict[str, Any]) -> str:
    risk_policy = payload.get("risk_policy") if isinstance(payload.get("risk_policy"), dict) else {}
    risk_class = str(payload.get("risk_class") or risk_policy.get("risk_class") or "").strip()
    if risk_class:
        return risk_class
    if event_type.startswith("secret_"):
        return "R5"
    if event_type in {
        "provider_adapter_dry_run_created",
        "planner_preview_created",
        "mcp_candidate_intake_created",
        "agent_run_started",
        "agent_run_completed",
    }:
        return "R1"
    if event_type in {"routing_decided", "tool_permission_checked"}:
        return _risk_class_from_level(risk_level)
    if any(marker in event_type for marker in ("created", "updated", "deleted", "changed", "applied", "decided", "consumed", "reviewed", "registered")):
        return "R2"
    return _risk_class_from_level(risk_level)


def _selected_model_or_agent(actor_id: str, payload: dict[str, Any]) -> str:
    for key in ("selected_model_or_agent", "agent_role", "model", "provider_id", "tool_id"):
        value = str(payload.get(key) or "").strip()
        if value:
            return redact_audit_text(value)
    route = str(payload.get("route") or payload.get("model_route") or "").strip()
    model = str(payload.get("model") or "").strip()
    if route and model:
        return redact_audit_text(f"{route}/{model}")
    return redact_audit_text(actor_id)


def _infer_source_references(evidence: str, payload: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("source_references", "source_refs", "sources", "required_env_keys", "missing_env_keys"):
        refs.extend(_as_non_empty_list(payload.get(key)))
    for key in ("source_url", "source", "requested_scope"):
        refs.extend(_as_non_empty_list(payload.get(key)))
    if evidence:
        refs.extend(_as_non_empty_list(evidence))
    seen: set[str] = set()
    deduped: list[str] = []
    for ref in refs:
        if ref not in seen:
            seen.add(ref)
            deduped.append(ref)
    return deduped[:20]


def _infer_state_references(
    *,
    event_type: str,
    task_id: str | None,
    approval_id: str | None,
    payload: dict[str, Any],
) -> dict[str, list[dict[str, str]]]:
    before_refs = payload.get("before_references") or payload.get("before_refs") or []
    after_refs = payload.get("after_references") or payload.get("after_refs") or []
    before = [
        {"type": "state", "ref": ref}
        for ref in _as_non_empty_list(before_refs)
    ]
    after = [
        {"type": "state", "ref": ref}
        for ref in _as_non_empty_list(after_refs)
    ]
    old_status = str(payload.get("old_status") or "").strip()
    new_status = str(payload.get("new_status") or payload.get("status") or payload.get("review_status") or payload.get("decision") or "").strip()
    primary_ids = {
        "task": task_id or payload.get("task_id"),
        "approval": approval_id or payload.get("approval_id"),
        "agent_run": payload.get("agent_run_id"),
        "agent_assignment_proposal": payload.get("agent_assignment_proposal_id"),
        "orchestration_proposal": payload.get("orchestration_proposal_id"),
        "routing_decision": payload.get("routing_decision_id"),
        "tool": payload.get("tool_id"),
        "tool_permission_check": payload.get("check_id") if str(payload.get("tool_id") or "").strip() else None,
        "connector": payload.get("connector_id"),
        "connector_permission_check": payload.get("check_id") if str(payload.get("connector_id") or "").strip() else None,
        "planner_preview": payload.get("planner_preview_id"),
        "provider_dry_run": payload.get("provider_dry_run_id"),
        "mcp_candidate_intake": payload.get("mcp_candidate_intake_id"),
        "memory": payload.get("memory_id"),
        "memory_edge": payload.get("edge_id"),
        "source_record": payload.get("source_record_id"),
    }
    for ref_type, raw_ref in primary_ids.items():
        ref = str(raw_ref or "").strip()
        if not ref:
            continue
        if old_status:
            before.append({"type": ref_type, "ref": f"{ref}@{old_status}"})
        if new_status:
            after.append({"type": ref_type, "ref": f"{ref}@{new_status}"})
        elif any(marker in event_type for marker in ("created", "registered", "started")):
            after.append({"type": ref_type, "ref": ref})
    return {"before": before[:20], "after": after[:20]}


def _infer_rollback_status(payload: dict[str, Any], risk_class: str) -> dict[str, Any]:
    rollback = payload.get("rollback_status")
    if isinstance(rollback, dict):
        return _redact_audit_value(rollback)
    if risk_class == "R1" and "read" in str(payload.get("action_type") or "").lower():
        return {
            "required": False,
            "status": "not_applicable",
            "reason": "read-only action",
        }
    return {
        "required": risk_class in {"R1", "R2", "R3", "R4", "R5"},
        "status": "missing",
        "reason": "no rollback registry record supplied",
    }


def build_audit_payload(
    *,
    actor_id: str,
    event_type: str,
    summary: str,
    risk_level: str,
    evidence: str,
    task_id: str | None,
    approval_id: str | None,
    timestamp: str,
    redacted_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    details = _redact_audit_value(redacted_payload or {})
    if not isinstance(details, dict):
        details = {"details": details}
    risk_class = _infer_audit_risk_class(event_type, risk_level, details)
    output_summary = details.get("output_summary") or details.get("result_summary") or details.get("reason") or summary
    result = details.get("result") or details.get("status") or details.get("decision") or "recorded"
    return {
        "intent": _compact_summary(details.get("intent"), event_type),
        "input_summary": _compact_summary(details.get("input_summary"), summary),
        "output_summary": _compact_summary(output_summary, summary),
        "selected_model_or_agent": _selected_model_or_agent(actor_id, details),
        "risk_class": risk_class,
        "timestamps": {
            "started_at": redact_audit_text(str(details.get("started_at") or timestamp)),
            "completed_at": redact_audit_text(str(details.get("completed_at") or timestamp)),
            "recorded_at": timestamp,
        },
        "result": redact_audit_text(str(result)),
        "source_references": _infer_source_references(evidence, details),
        "state_references": _infer_state_references(
            event_type=event_type,
            task_id=task_id,
            approval_id=approval_id,
            payload=details,
        ),
        "rollback_status": _infer_rollback_status(details, risk_class),
        "details": details,
    }


def sanitize_audit_event_for_display(row: dict[str, Any]) -> dict[str, Any]:
    event = dict(row)
    for key in ("actor_type", "actor_id", "task_id", "approval_id"):
        if event.get(key):
            event[key] = redact_audit_text(str(event[key]))
    event["summary"] = redact_audit_text(str(event.get("summary") or ""))
    event["evidence"] = redact_audit_text(str(event.get("evidence") or ""))
    try:
        payload = json.loads(str(event.get("redacted_payload_json") or "{}"))
    except json.JSONDecodeError:
        payload = {"unparsed_payload": str(event.get("redacted_payload_json") or "")}
    required_keys = {
        "intent",
        "input_summary",
        "output_summary",
        "selected_model_or_agent",
        "risk_class",
        "timestamps",
        "result",
        "source_references",
        "state_references",
        "rollback_status",
    }
    if not required_keys.issubset(set(payload)) or not isinstance(payload.get("state_references"), dict):
        payload = build_audit_payload(
            actor_id=str(event.get("actor_id") or ""),
            event_type=str(event.get("event_type") or ""),
            summary=str(event.get("summary") or ""),
            risk_level=str(event.get("risk_level") or "low"),
            evidence=str(event.get("evidence") or ""),
            task_id=event.get("task_id"),
            approval_id=event.get("approval_id"),
            timestamp=str(event.get("timestamp") or now_iso()),
            redacted_payload=payload if isinstance(payload, dict) else {"payload": payload},
        )
    event["redacted_payload_json"] = json.dumps(_redact_audit_value(payload), ensure_ascii=False, sort_keys=True)
    return event


def _audit_display_payload(event: dict[str, Any]) -> dict[str, Any]:
    return _json_loads(event.get("redacted_payload_json"), {})


def _audit_event_matches(
    event: dict[str, Any],
    *,
    ref_type: str,
    ref_id: str,
    task_id: str | None = None,
    approval_id: str | None = None,
) -> bool:
    if not ref_id:
        return False
    if task_id and event.get("task_id") == task_id:
        return True
    if approval_id and event.get("approval_id") == approval_id:
        return True
    payload = _audit_display_payload(event)
    details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
    if str(details.get(f"{ref_type}_id") or "") == ref_id:
        return True
    if ref_type == "agent_run" and str(details.get("agent_run_id") or "") == ref_id:
        return True
    if ref_type == "source_record" and str(details.get("source_record_id") or "") == ref_id:
        return True
    state_refs = payload.get("state_references") if isinstance(payload.get("state_references"), dict) else {}
    for side in ("before", "after"):
        for item in _list(state_refs.get(side)):
            if not isinstance(item, dict) or item.get("type") != ref_type:
                continue
            ref = str(item.get("ref") or "")
            if ref == ref_id or ref.startswith(f"{ref_id}@"):
                return True
    return False


def _related_audit_events(
    audit_events: list[dict[str, Any]],
    *,
    ref_type: str,
    ref_id: str,
    task_id: str | None = None,
    approval_id: str | None = None,
    limit: int = 12,
) -> list[dict[str, Any]]:
    matches = [
        event
        for event in audit_events
        if _audit_event_matches(
            event,
            ref_type=ref_type,
            ref_id=ref_id,
            task_id=task_id,
            approval_id=approval_id,
        )
    ]
    return matches[:limit]


def audit_hash_payload(event: dict[str, Any]) -> str:
    return json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class ControlPlaneStore:
    def __init__(self, db_path: Path, seed_path: Path):
        self.db_path = db_path
        self.seed_path = seed_path

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            self._migrate(conn)
            if self._is_empty(conn):
                self._seed(conn)
            self._ensure_default_connector_manifests(conn)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS phases (
              id TEXT PRIMARY KEY,
              title TEXT NOT NULL,
              goal TEXT NOT NULL,
              status TEXT NOT NULL,
              sort_order INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tasks (
              id TEXT PRIMARY KEY,
              title TEXT NOT NULL,
              goal TEXT NOT NULL,
              phase_id TEXT,
              owner TEXT NOT NULL,
              status TEXT NOT NULL,
              priority TEXT NOT NULL,
              risk_level TEXT NOT NULL,
              value_score INTEGER NOT NULL DEFAULT 3,
              source_refs_json TEXT NOT NULL DEFAULT '[]',
              parent_task_id TEXT,
              approval_required INTEGER NOT NULL DEFAULT 0,
              acceptance_criteria TEXT NOT NULL DEFAULT '',
              blocked_reason TEXT NOT NULL DEFAULT '',
              result TEXT NOT NULL DEFAULT '',
              verification_note TEXT NOT NULL DEFAULT '',
              review_note TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              done_at TEXT,
              FOREIGN KEY (phase_id) REFERENCES phases(id),
              FOREIGN KEY (parent_task_id) REFERENCES tasks(id)
            );

            CREATE TABLE IF NOT EXISTS approvals (
              id TEXT PRIMARY KEY,
              task_id TEXT,
              action_type TEXT NOT NULL DEFAULT 'manual',
              summary TEXT NOT NULL,
              reason TEXT NOT NULL,
              affected_systems TEXT NOT NULL DEFAULT '',
              permissions TEXT NOT NULL DEFAULT '',
              external_effect TEXT NOT NULL DEFAULT '',
              cost_estimate TEXT NOT NULL DEFAULT '',
              risk_level TEXT NOT NULL DEFAULT 'medium',
              risk_class TEXT NOT NULL DEFAULT '',
              expected_change TEXT NOT NULL DEFAULT '',
              rollback_plan TEXT NOT NULL DEFAULT '',
              failure_mode TEXT NOT NULL DEFAULT '',
              plan_fingerprint TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL,
              requested_by TEXT NOT NULL DEFAULT 'system',
              required_before TEXT,
              decided_at TEXT,
              decision_note TEXT NOT NULL DEFAULT '',
              expires_at TEXT,
              consumed_at TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (task_id) REFERENCES tasks(id)
            );

            CREATE TABLE IF NOT EXISTS required_env (
              key TEXT PRIMARY KEY,
              purpose TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS engineering_rules (
              sort_order INTEGER PRIMARY KEY,
              rule TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_events (
              id TEXT PRIMARY KEY,
              sequence INTEGER NOT NULL UNIQUE,
              timestamp TEXT NOT NULL,
              actor_type TEXT NOT NULL,
              actor_id TEXT NOT NULL,
              event_type TEXT NOT NULL,
              task_id TEXT,
              approval_id TEXT,
              risk_level TEXT NOT NULL DEFAULT 'low',
              summary TEXT NOT NULL,
              evidence TEXT NOT NULL DEFAULT '',
              redacted_payload_json TEXT NOT NULL DEFAULT '{}',
              prev_hash TEXT NOT NULL,
              event_hash TEXT NOT NULL UNIQUE
            );

            CREATE TRIGGER IF NOT EXISTS audit_events_no_update
            BEFORE UPDATE ON audit_events
            BEGIN
              SELECT RAISE(ABORT, 'audit_events are append-only');
            END;

            CREATE TRIGGER IF NOT EXISTS audit_events_no_delete
            BEFORE DELETE ON audit_events
            BEGIN
              SELECT RAISE(ABORT, 'audit_events are append-only');
            END;

            CREATE TABLE IF NOT EXISTS agent_runs (
              id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              agent_role TEXT NOT NULL,
              role TEXT NOT NULL DEFAULT 'Code/Improvement',
              status TEXT NOT NULL,
              task_type TEXT NOT NULL,
              complexity TEXT NOT NULL,
              risk TEXT NOT NULL,
              privacy TEXT NOT NULL,
              budget_mode TEXT NOT NULL,
              provider TEXT NOT NULL,
              route TEXT NOT NULL,
              model TEXT NOT NULL,
              reasoning_effort TEXT NOT NULL,
              route_reason TEXT NOT NULL,
              model_route_json TEXT NOT NULL DEFAULT '{}',
              approval_required INTEGER NOT NULL DEFAULT 0,
              task_json TEXT NOT NULL DEFAULT '{}',
              task_packet_json TEXT NOT NULL,
              input_sources_json TEXT NOT NULL DEFAULT '[]',
              allowed_actions_json TEXT NOT NULL,
              forbidden_actions_json TEXT NOT NULL,
              result_summary TEXT NOT NULL DEFAULT '',
              output_json TEXT NOT NULL DEFAULT '{}',
              confidence REAL NOT NULL DEFAULT 0,
              cost_estimate_json TEXT NOT NULL DEFAULT '{}',
              risk_assessment_json TEXT NOT NULL DEFAULT '{}',
              evidence_json TEXT NOT NULL DEFAULT '[]',
              review_status TEXT NOT NULL DEFAULT 'pending',
              review_note TEXT NOT NULL DEFAULT '',
              reviewer_result_json TEXT NOT NULL DEFAULT '{}',
              rollback_status_json TEXT NOT NULL DEFAULT '{}',
              recovery_suggestions_json TEXT NOT NULL DEFAULT '[]',
              next_action TEXT NOT NULL DEFAULT 'review_agent_run',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              started_at TEXT,
              completed_at TEXT,
              FOREIGN KEY (task_id) REFERENCES tasks(id)
            );

            CREATE TABLE IF NOT EXISTS agent_assignment_proposals (
              id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              status TEXT NOT NULL,
              agent_role TEXT NOT NULL,
              runner_kind TEXT NOT NULL,
              execution_mode TEXT NOT NULL,
              execution_allowed INTEGER NOT NULL,
              external_calls_made INTEGER NOT NULL DEFAULT 0,
              external_calls_allowed INTEGER NOT NULL DEFAULT 0,
              secret_values_read INTEGER NOT NULL DEFAULT 0,
              shell_commands_allowed INTEGER NOT NULL DEFAULT 0,
              file_writes_allowed INTEGER NOT NULL DEFAULT 0,
              task_type TEXT NOT NULL,
              complexity TEXT NOT NULL,
              risk TEXT NOT NULL,
              privacy TEXT NOT NULL,
              budget_mode TEXT NOT NULL,
              provider TEXT NOT NULL,
              route TEXT NOT NULL,
              model TEXT NOT NULL,
              reasoning_effort TEXT NOT NULL,
              route_reason TEXT NOT NULL,
              task_packet_json TEXT NOT NULL,
              allowed_actions_json TEXT NOT NULL,
              forbidden_actions_json TEXT NOT NULL,
              proposal_json TEXT NOT NULL,
              applied_agent_run_id TEXT,
              review_note TEXT NOT NULL DEFAULT '',
              audit_event_id TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              applied_at TEXT,
              FOREIGN KEY (task_id) REFERENCES tasks(id),
              FOREIGN KEY (applied_agent_run_id) REFERENCES agent_runs(id)
            );

            CREATE TABLE IF NOT EXISTS provider_dry_runs (
              id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              agent_assignment_proposal_id TEXT,
              provider_id TEXT NOT NULL,
              adapter_id TEXT NOT NULL,
              status TEXT NOT NULL,
              decision TEXT NOT NULL,
              execution_allowed INTEGER NOT NULL DEFAULT 0,
              provider_calls_made INTEGER NOT NULL DEFAULT 0,
              dependency_installed INTEGER NOT NULL DEFAULT 0,
              sdk_imported INTEGER NOT NULL DEFAULT 0,
              secret_values_read INTEGER NOT NULL DEFAULT 0,
              approval_consumed INTEGER NOT NULL DEFAULT 0,
              shell_commands_allowed INTEGER NOT NULL DEFAULT 0,
              file_writes_allowed INTEGER NOT NULL DEFAULT 0,
              required_env_keys_json TEXT NOT NULL DEFAULT '[]',
              missing_env_keys_json TEXT NOT NULL DEFAULT '[]',
              dry_run_json TEXT NOT NULL,
              audit_event_id TEXT,
              created_at TEXT NOT NULL,
              FOREIGN KEY (task_id) REFERENCES tasks(id),
              FOREIGN KEY (agent_assignment_proposal_id) REFERENCES agent_assignment_proposals(id)
            );

            CREATE TABLE IF NOT EXISTS routing_decisions (
              id TEXT PRIMARY KEY,
              created_at TEXT NOT NULL,
              input_text_redacted TEXT NOT NULL,
              route TEXT NOT NULL,
              intent TEXT NOT NULL,
              confidence REAL NOT NULL,
              complexity TEXT NOT NULL,
              risk_level TEXT NOT NULL,
              privacy_level TEXT NOT NULL,
              urgency TEXT NOT NULL,
              value_score INTEGER NOT NULL,
              requires_sources INTEGER NOT NULL,
              requires_tool INTEGER NOT NULL,
              external_effect TEXT NOT NULL,
              approval_required INTEGER NOT NULL,
              approval_reason TEXT NOT NULL DEFAULT '',
              recommended_task_status TEXT NOT NULL DEFAULT '',
              provider TEXT NOT NULL,
              model_route TEXT NOT NULL,
              model TEXT NOT NULL,
              model_reason TEXT NOT NULL,
              decision_json TEXT NOT NULL,
              audit_event_id TEXT
            );

            CREATE TABLE IF NOT EXISTS decision_feedback (
              id TEXT PRIMARY KEY,
              routing_decision_id TEXT NOT NULL,
              feedback_type TEXT NOT NULL,
              note TEXT NOT NULL DEFAULT '',
              actor_type TEXT NOT NULL DEFAULT 'user',
              actor_id TEXT NOT NULL DEFAULT 'dashboard',
              audit_event_id TEXT,
              created_at TEXT NOT NULL,
              FOREIGN KEY (routing_decision_id) REFERENCES routing_decisions(id)
            );

            CREATE TABLE IF NOT EXISTS routing_eval_cases (
              id TEXT PRIMARY KEY,
              routing_decision_id TEXT NOT NULL,
              source_feedback_id TEXT,
              input_text_redacted TEXT NOT NULL,
              expected_route TEXT NOT NULL,
              actual_route TEXT NOT NULL,
              failure_type TEXT NOT NULL,
              reason TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL DEFAULT 'active',
              case_json TEXT NOT NULL,
              audit_event_id TEXT,
              created_at TEXT NOT NULL,
              FOREIGN KEY (routing_decision_id) REFERENCES routing_decisions(id),
              FOREIGN KEY (source_feedback_id) REFERENCES decision_feedback(id)
            );

            CREATE TABLE IF NOT EXISTS routing_eval_runs (
              id TEXT PRIMARY KEY,
              release_label TEXT NOT NULL,
              decision_logic_fingerprint TEXT NOT NULL DEFAULT '',
              passed INTEGER NOT NULL,
              total INTEGER NOT NULL,
              failed INTEGER NOT NULL,
              accuracy REAL NOT NULL,
              safety_case_count INTEGER NOT NULL DEFAULT 0,
              safety_failures INTEGER NOT NULL DEFAULT 0,
              safety_ok INTEGER NOT NULL DEFAULT 1,
              impact_json TEXT NOT NULL DEFAULT '{}',
              summary_json TEXT NOT NULL,
              audit_event_id TEXT,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS orchestration_proposals (
              id TEXT PRIMARY KEY,
              routing_decision_id TEXT,
              status TEXT NOT NULL,
              route TEXT NOT NULL,
              summary TEXT NOT NULL,
              execution_allowed INTEGER NOT NULL DEFAULT 0,
              requires_user_review INTEGER NOT NULL DEFAULT 1,
              recommended_next_step TEXT NOT NULL DEFAULT '',
              proposal_json TEXT NOT NULL,
              applied_task_id TEXT,
              applied_approval_id TEXT,
              review_note TEXT NOT NULL DEFAULT '',
              audit_event_id TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              applied_at TEXT,
              FOREIGN KEY (routing_decision_id) REFERENCES routing_decisions(id),
              FOREIGN KEY (applied_task_id) REFERENCES tasks(id),
              FOREIGN KEY (applied_approval_id) REFERENCES approvals(id)
            );

            CREATE TABLE IF NOT EXISTS tool_manifests (
              tool_id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              source_type TEXT NOT NULL,
              source_url TEXT NOT NULL DEFAULT '',
              purpose TEXT NOT NULL DEFAULT '',
              owner TEXT NOT NULL DEFAULT 'Leon',
              risk_level TEXT NOT NULL DEFAULT 'medium',
              status TEXT NOT NULL,
              read_scopes_json TEXT NOT NULL DEFAULT '[]',
              write_scopes_json TEXT NOT NULL DEFAULT '[]',
              required_env_keys_json TEXT NOT NULL DEFAULT '[]',
              cost_profile TEXT NOT NULL DEFAULT 'unknown',
              resource_profile TEXT NOT NULL DEFAULT 'low',
              external_effects_json TEXT NOT NULL DEFAULT '[]',
              approval_required_for_json TEXT NOT NULL DEFAULT '[]',
              allowed_without_approval_json TEXT NOT NULL DEFAULT '[]',
              forbidden_actions_json TEXT NOT NULL DEFAULT '[]',
              audit_events_json TEXT NOT NULL DEFAULT '[]',
              rollback_notes TEXT NOT NULL DEFAULT '',
              maintenance_status TEXT NOT NULL DEFAULT 'unverified',
              sandbox_required INTEGER NOT NULL DEFAULT 1,
              notes TEXT NOT NULL DEFAULT '',
              manifest_json TEXT NOT NULL,
              audit_event_id TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tool_permission_checks (
              id TEXT PRIMARY KEY,
              tool_id TEXT NOT NULL,
              action_type TEXT NOT NULL,
              requested_scope TEXT NOT NULL,
              decision TEXT NOT NULL,
              approval_required INTEGER NOT NULL DEFAULT 0,
              required_gate TEXT NOT NULL DEFAULT '',
              reason TEXT NOT NULL DEFAULT '',
              risk_level TEXT NOT NULL DEFAULT 'medium',
              approval_id TEXT,
              check_json TEXT NOT NULL,
              audit_event_id TEXT,
              created_at TEXT NOT NULL,
              FOREIGN KEY (tool_id) REFERENCES tool_manifests(tool_id),
              FOREIGN KEY (approval_id) REFERENCES approvals(id)
            );

            CREATE TABLE IF NOT EXISTS connector_manifests (
              connector_id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              connector_type TEXT NOT NULL,
              status TEXT NOT NULL,
              owner TEXT NOT NULL DEFAULT 'Leon',
              purpose TEXT NOT NULL DEFAULT '',
              read_scopes_json TEXT NOT NULL DEFAULT '[]',
              write_scopes_json TEXT NOT NULL DEFAULT '[]',
              required_env_keys_json TEXT NOT NULL DEFAULT '[]',
              external_system INTEGER NOT NULL DEFAULT 0,
              external_effects_json TEXT NOT NULL DEFAULT '[]',
              approval_required_for_json TEXT NOT NULL DEFAULT '[]',
              allowed_without_approval_json TEXT NOT NULL DEFAULT '[]',
              forbidden_actions_json TEXT NOT NULL DEFAULT '[]',
              connector_policy_allows_autonomy INTEGER NOT NULL DEFAULT 0,
              risk_level TEXT NOT NULL DEFAULT 'medium',
              rollback_notes TEXT NOT NULL DEFAULT '',
              secret_handling_json TEXT NOT NULL DEFAULT '{}',
              notes TEXT NOT NULL DEFAULT '',
              manifest_json TEXT NOT NULL,
              audit_event_id TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS connector_permission_checks (
              id TEXT PRIMARY KEY,
              connector_id TEXT NOT NULL,
              action_type TEXT NOT NULL,
              requested_scope TEXT NOT NULL,
              decision TEXT NOT NULL,
              approval_required INTEGER NOT NULL DEFAULT 0,
              required_gate TEXT NOT NULL DEFAULT '',
              reason TEXT NOT NULL DEFAULT '',
              risk_level TEXT NOT NULL DEFAULT 'medium',
              risk_class TEXT NOT NULL DEFAULT '',
              policy_decision TEXT NOT NULL DEFAULT '',
              approval_id TEXT,
              connector_executed INTEGER NOT NULL DEFAULT 0,
              write_performed INTEGER NOT NULL DEFAULT 0,
              check_json TEXT NOT NULL,
              audit_event_id TEXT,
              created_at TEXT NOT NULL,
              FOREIGN KEY (connector_id) REFERENCES connector_manifests(connector_id),
              FOREIGN KEY (approval_id) REFERENCES approvals(id)
            );

            CREATE TABLE IF NOT EXISTS mcp_candidate_intakes (
              id TEXT PRIMARY KEY,
              tool_id TEXT NOT NULL,
              status TEXT NOT NULL,
              decision TEXT NOT NULL,
              execution_allowed INTEGER NOT NULL DEFAULT 0,
              no_approval_granted INTEGER NOT NULL DEFAULT 1,
              status_unchanged INTEGER NOT NULL DEFAULT 1,
              install_allowed_now INTEGER NOT NULL DEFAULT 0,
              connect_allowed_now INTEGER NOT NULL DEFAULT 0,
              write_allowed_now INTEGER NOT NULL DEFAULT 0,
              checklist_json TEXT NOT NULL,
              audit_event_id TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (tool_id) REFERENCES tool_manifests(tool_id)
            );

            CREATE TABLE IF NOT EXISTS planner_previews (
              id TEXT PRIMARY KEY,
              task_id TEXT,
              decision TEXT NOT NULL,
              execution_allowed INTEGER NOT NULL DEFAULT 0,
              external_calls_made INTEGER NOT NULL DEFAULT 0,
              accounts_connected INTEGER NOT NULL DEFAULT 0,
              secret_values_read INTEGER NOT NULL DEFAULT 0,
              write_allowed_now INTEGER NOT NULL DEFAULT 0,
              approval_required INTEGER NOT NULL DEFAULT 0,
              preview_json TEXT NOT NULL,
              audit_event_id TEXT,
              created_at TEXT NOT NULL,
              FOREIGN KEY (task_id) REFERENCES tasks(id)
            );

            CREATE TABLE IF NOT EXISTS memory_items (
              id TEXT PRIMARY KEY,
              status TEXT NOT NULL,
              memory_type TEXT NOT NULL,
              content TEXT NOT NULL,
              source TEXT NOT NULL DEFAULT '',
              source_task_id TEXT,
              confidence REAL NOT NULL,
              sensitivity TEXT NOT NULL,
              privacy_level TEXT NOT NULL,
              expires_at TEXT,
              review_note TEXT NOT NULL DEFAULT '',
              correction_of TEXT,
              graph_entities_json TEXT NOT NULL DEFAULT '[]',
              provenance_json TEXT NOT NULL DEFAULT '{}',
              conflict_status TEXT NOT NULL DEFAULT 'none',
              conflict_memory_ids_json TEXT NOT NULL DEFAULT '[]',
              conflict_note TEXT NOT NULL DEFAULT '',
              audit_event_id TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              deleted_at TEXT,
              FOREIGN KEY (source_task_id) REFERENCES tasks(id),
              FOREIGN KEY (correction_of) REFERENCES memory_items(id)
            );

            CREATE TABLE IF NOT EXISTS memory_graph_edges (
              id TEXT PRIMARY KEY,
              source_memory_id TEXT NOT NULL,
              subject TEXT NOT NULL,
              predicate TEXT NOT NULL,
              object TEXT NOT NULL,
              relationship_type TEXT NOT NULL DEFAULT 'related_to',
              confidence REAL NOT NULL,
              source TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL DEFAULT 'active',
              audit_event_id TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              deleted_at TEXT,
              FOREIGN KEY (source_memory_id) REFERENCES memory_items(id)
            );

            CREATE TABLE IF NOT EXISTS memory_graph_entities (
              id TEXT PRIMARY KEY,
              entity_type TEXT NOT NULL,
              label TEXT NOT NULL,
              source_memory_id TEXT,
              external_ref TEXT NOT NULL DEFAULT '',
              provenance_json TEXT NOT NULL DEFAULT '{}',
              confidence REAL NOT NULL DEFAULT 0.5,
              status TEXT NOT NULL DEFAULT 'active',
              audit_event_id TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              deleted_at TEXT,
              FOREIGN KEY (source_memory_id) REFERENCES memory_items(id)
            );

            CREATE TABLE IF NOT EXISTS memory_graph_relationships (
              id TEXT PRIMARY KEY,
              relationship_type TEXT NOT NULL,
              from_entity_id TEXT NOT NULL,
              to_entity_id TEXT NOT NULL,
              source_memory_id TEXT,
              label TEXT NOT NULL DEFAULT '',
              provenance_json TEXT NOT NULL DEFAULT '{}',
              confidence REAL NOT NULL DEFAULT 0.5,
              status TEXT NOT NULL DEFAULT 'active',
              audit_event_id TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              deleted_at TEXT,
              FOREIGN KEY (from_entity_id) REFERENCES memory_graph_entities(id),
              FOREIGN KEY (to_entity_id) REFERENCES memory_graph_entities(id),
              FOREIGN KEY (source_memory_id) REFERENCES memory_items(id)
            );

            CREATE TABLE IF NOT EXISTS source_records (
              id TEXT PRIMARY KEY,
              source_type TEXT NOT NULL,
              source_ref TEXT NOT NULL,
              title TEXT NOT NULL,
              status TEXT NOT NULL,
              content_hash TEXT NOT NULL DEFAULT '',
              content_excerpt TEXT NOT NULL DEFAULT '',
              content_bytes INTEGER NOT NULL DEFAULT 0,
              metadata_json TEXT NOT NULL DEFAULT '{}',
              secret_scan_json TEXT NOT NULL DEFAULT '{}',
              audit_event_id TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              deleted_at TEXT
            );

            CREATE TABLE IF NOT EXISTS memory_retrieval_queries (
              id TEXT PRIMARY KEY,
              query_redacted TEXT NOT NULL,
              scope TEXT NOT NULL DEFAULT 'context',
              answer TEXT NOT NULL,
              answer_status TEXT NOT NULL,
              confidence REAL NOT NULL DEFAULT 0,
              latency_ms INTEGER NOT NULL DEFAULT 0,
              relevance_score REAL NOT NULL DEFAULT 0,
              match_count INTEGER NOT NULL DEFAULT 0,
              memory_match_count INTEGER NOT NULL DEFAULT 0,
              source_match_count INTEGER NOT NULL DEFAULT 0,
              conflict_count INTEGER NOT NULL DEFAULT 0,
              source_refs_json TEXT NOT NULL DEFAULT '[]',
              related_graph_entries_json TEXT NOT NULL DEFAULT '[]',
              conflicts_json TEXT NOT NULL DEFAULT '[]',
              metrics_json TEXT NOT NULL DEFAULT '{}',
              audit_event_id TEXT,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS rollback_records (
              id TEXT PRIMARY KEY,
              kind TEXT NOT NULL,
              status TEXT NOT NULL,
              risk_class TEXT NOT NULL,
              task_id TEXT,
              approval_id TEXT,
              action_ref_type TEXT NOT NULL DEFAULT '',
              action_ref_id TEXT NOT NULL DEFAULT '',
              target_type TEXT NOT NULL,
              target_ref TEXT NOT NULL,
              operation TEXT NOT NULL,
              summary TEXT NOT NULL,
              before_snapshot_json TEXT NOT NULL DEFAULT '{}',
              after_snapshot_json TEXT NOT NULL DEFAULT '{}',
              undo_payload_json TEXT NOT NULL DEFAULT '{}',
              patch_snapshot TEXT NOT NULL DEFAULT '',
              test_results_json TEXT NOT NULL DEFAULT '{}',
              audit_details_json TEXT NOT NULL DEFAULT '{}',
              compensating_action_json TEXT NOT NULL DEFAULT '{}',
              deletion_supported INTEGER NOT NULL DEFAULT 0,
              undo_supported INTEGER NOT NULL DEFAULT 0,
              scrub_supported INTEGER NOT NULL DEFAULT 0,
              compensation_supported INTEGER NOT NULL DEFAULT 0,
              audit_event_id TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              applied_at TEXT,
              FOREIGN KEY (task_id) REFERENCES tasks(id),
              FOREIGN KEY (approval_id) REFERENCES approvals(id)
            );

            CREATE TABLE IF NOT EXISTS missing_component_records (
              id TEXT PRIMARY KEY,
              requested_component TEXT NOT NULL,
              requested_capability TEXT NOT NULL DEFAULT '',
              route TEXT NOT NULL DEFAULT '',
              space TEXT NOT NULL DEFAULT '',
              task_status TEXT NOT NULL DEFAULT '',
              risk_level TEXT NOT NULL DEFAULT 'medium',
              fallback_component_ids_json TEXT NOT NULL DEFAULT '[]',
              context_json TEXT NOT NULL DEFAULT '{}',
              source_ref TEXT NOT NULL DEFAULT '',
              run_id TEXT,
              task_id TEXT,
              status TEXT NOT NULL DEFAULT 'open',
              audit_event_id TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (task_id) REFERENCES tasks(id)
            );

            CREATE TABLE IF NOT EXISTS night_queue_runs (
              id TEXT PRIMARY KEY,
              status TEXT NOT NULL,
              started_at TEXT NOT NULL,
              ended_at TEXT,
              selected_agents_json TEXT NOT NULL DEFAULT '[]',
              selected_models_json TEXT NOT NULL DEFAULT '[]',
              cost_estimate_json TEXT NOT NULL DEFAULT '{}',
              policy_limits_json TEXT NOT NULL DEFAULT '{}',
              action_results_json TEXT NOT NULL DEFAULT '[]',
              failures_json TEXT NOT NULL DEFAULT '[]',
              sources_json TEXT NOT NULL DEFAULT '[]',
              changes_json TEXT NOT NULL DEFAULT '[]',
              rollback_status_json TEXT NOT NULL DEFAULT '{}',
              morning_brief_json TEXT NOT NULL DEFAULT '{}',
              audit_event_id TEXT,
              completed_audit_event_id TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            """
        )
        self._ensure_column(conn, "tasks", "value_score", "INTEGER NOT NULL DEFAULT 3")
        self._ensure_column(conn, "tasks", "source_refs_json", "TEXT NOT NULL DEFAULT '[]'")
        self._ensure_column(conn, "tasks", "parent_task_id", "TEXT")
        self._ensure_column(conn, "agent_runs", "role", "TEXT NOT NULL DEFAULT 'Code/Improvement'")
        self._ensure_column(conn, "agent_runs", "model_route_json", "TEXT NOT NULL DEFAULT '{}'")
        self._ensure_column(conn, "agent_runs", "task_json", "TEXT NOT NULL DEFAULT '{}'")
        self._ensure_column(conn, "agent_runs", "input_sources_json", "TEXT NOT NULL DEFAULT '[]'")
        self._ensure_column(conn, "agent_runs", "output_json", "TEXT NOT NULL DEFAULT '{}'")
        self._ensure_column(conn, "agent_runs", "confidence", "REAL NOT NULL DEFAULT 0")
        self._ensure_column(conn, "agent_runs", "cost_estimate_json", "TEXT NOT NULL DEFAULT '{}'")
        self._ensure_column(conn, "agent_runs", "risk_assessment_json", "TEXT NOT NULL DEFAULT '{}'")
        self._ensure_column(conn, "agent_runs", "reviewer_result_json", "TEXT NOT NULL DEFAULT '{}'")
        self._ensure_column(conn, "agent_runs", "rollback_status_json", "TEXT NOT NULL DEFAULT '{}'")
        self._ensure_column(conn, "agent_runs", "recovery_suggestions_json", "TEXT NOT NULL DEFAULT '[]'")
        self._ensure_column(conn, "agent_runs", "next_action", "TEXT NOT NULL DEFAULT 'review_agent_run'")
        self._ensure_column(conn, "memory_items", "provenance_json", "TEXT NOT NULL DEFAULT '{}'")
        self._ensure_column(conn, "memory_items", "conflict_status", "TEXT NOT NULL DEFAULT 'none'")
        self._ensure_column(conn, "memory_items", "conflict_memory_ids_json", "TEXT NOT NULL DEFAULT '[]'")
        self._ensure_column(conn, "memory_items", "conflict_note", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(conn, "memory_graph_edges", "relationship_type", "TEXT NOT NULL DEFAULT 'related_to'")
        self._ensure_column(conn, "connector_permission_checks", "risk_class", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(conn, "connector_permission_checks", "policy_decision", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(conn, "connector_permission_checks", "connector_executed", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column(conn, "connector_permission_checks", "write_performed", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column(conn, "approvals", "risk_class", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(conn, "approvals", "expected_change", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(conn, "approvals", "failure_mode", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(conn, "approvals", "plan_fingerprint", "TEXT NOT NULL DEFAULT ''")

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _is_empty(self, conn: sqlite3.Connection) -> bool:
        row = conn.execute("SELECT COUNT(*) AS count FROM metadata").fetchone()
        return int(row["count"]) == 0

    def _ensure_default_connector_manifests(self, conn: sqlite3.Connection) -> None:
        from leon_control_plane.connector_registry import DEFAULT_CONNECTOR_MANIFESTS, normalize_connector_manifest

        timestamp = now_iso()
        for raw_manifest in DEFAULT_CONNECTOR_MANIFESTS:
            manifest = _redact_audit_value(normalize_connector_manifest(raw_manifest))
            existing = conn.execute(
                "SELECT connector_id FROM connector_manifests WHERE connector_id = ?",
                (manifest["connector_id"],),
            ).fetchone()
            if existing is not None:
                continue
            audit_event_id = self.append_audit_event(
                conn,
                actor_type="system",
                actor_id="connector-registry",
                event_type="connector_manifest_registered",
                risk_level=manifest["risk_level"],
                summary=f"Default connector manifest {manifest['connector_id']} registered as {manifest['status']}.",
                evidence="default connector permission manifest seed",
                redacted_payload={
                    "connector_id": manifest["connector_id"],
                    "name": manifest["name"],
                    "connector_type": manifest["connector_type"],
                    "status": manifest["status"],
                    "read_scope_count": len(manifest["read_scopes"]),
                    "write_scope_count": len(manifest["write_scopes"]),
                    "required_env_keys": manifest["required_env_keys"],
                    "raw_secret_values_stored": False,
                },
                timestamp=timestamp,
            )
            conn.execute(
                """
                INSERT INTO connector_manifests(
                  connector_id, name, connector_type, status, owner, purpose,
                  read_scopes_json, write_scopes_json, required_env_keys_json,
                  external_system, external_effects_json, approval_required_for_json,
                  allowed_without_approval_json, forbidden_actions_json,
                  connector_policy_allows_autonomy, risk_level, rollback_notes,
                  secret_handling_json, notes, manifest_json, audit_event_id,
                  created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    manifest["connector_id"],
                    manifest["name"],
                    manifest["connector_type"],
                    manifest["status"],
                    manifest["owner"],
                    manifest["purpose"],
                    json.dumps(manifest["read_scopes"], ensure_ascii=False, sort_keys=True),
                    json.dumps(manifest["write_scopes"], ensure_ascii=False, sort_keys=True),
                    json.dumps(manifest["required_env_keys"], ensure_ascii=False, sort_keys=True),
                    int(bool(manifest["external_system"])),
                    json.dumps(manifest["external_effects"], ensure_ascii=False, sort_keys=True),
                    json.dumps(manifest["approval_required_for"], ensure_ascii=False, sort_keys=True),
                    json.dumps(manifest["allowed_without_approval"], ensure_ascii=False, sort_keys=True),
                    json.dumps(manifest["forbidden_actions"], ensure_ascii=False, sort_keys=True),
                    int(bool(manifest["connector_policy_allows_autonomy"])),
                    manifest["risk_level"],
                    manifest["rollback_notes"],
                    json.dumps(manifest["secret_handling"], ensure_ascii=False, sort_keys=True),
                    manifest["notes"],
                    json.dumps(manifest, ensure_ascii=False, sort_keys=True),
                    audit_event_id,
                    timestamp,
                    timestamp,
                ),
            )

    def _seed(self, conn: sqlite3.Connection) -> None:
        with self.seed_path.open("r", encoding="utf-8") as handle:
            seed = json.load(handle)
        created_at = seed.get("metadata", {}).get("created_at") or now_iso()
        updated_at = seed.get("metadata", {}).get("updated_at") or created_at

        metadata = dict(seed.get("metadata", {}))
        metadata["created_at"] = created_at
        metadata["updated_at"] = updated_at
        for key, value in metadata.items():
            conn.execute(
                "INSERT INTO metadata(key, value) VALUES (?, ?)",
                (key, json.dumps(value, ensure_ascii=False)),
            )

        for index, phase in enumerate(seed.get("phases", [])):
            conn.execute(
                "INSERT INTO phases(id, title, goal, status, sort_order) VALUES (?, ?, ?, ?, ?)",
                (phase["id"], phase["title"], phase["goal"], phase["status"], index),
            )

        for task in seed.get("tasks", []):
            source_refs = _normalize_source_refs(task.get("source_refs") or task.get("sources") or [])
            value_score = _normalize_value_score(task.get("value_score", 3))
            conn.execute(
                """
                INSERT INTO tasks(
                  id, title, goal, phase_id, owner, status, priority, risk_level,
                  value_score, source_refs_json, parent_task_id, approval_required,
                  acceptance_criteria, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task["id"],
                    task["title"],
                    task.get("goal") or task.get("acceptance", ""),
                    task.get("phase_id"),
                    task["owner"],
                    task["status"],
                    task["priority"],
                    task.get("risk_level") or task.get("risk", "medium"),
                    value_score,
                    json.dumps(source_refs, ensure_ascii=False, sort_keys=True),
                    task.get("parent_task_id"),
                    int(bool(task.get("approval_required", False))),
                    task.get("acceptance", ""),
                    created_at,
                    updated_at,
                ),
            )

        for approval in seed.get("approvals", []):
            status = approval.get("status", "pending")
            if status == "waiting":
                status = "pending"
            conn.execute(
                """
                INSERT INTO approvals(
                  id, task_id, action_type, summary, reason, affected_systems, permissions,
                  external_effect, cost_estimate, risk_level, risk_class, expected_change,
                  rollback_plan, failure_mode, plan_fingerprint, status,
                  requested_by, required_before, decided_at, decision_note, expires_at,
                  consumed_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    approval["id"],
                    approval.get("task_id"),
                    approval.get("action_type", "manual"),
                    approval.get("summary") or approval["title"],
                    approval["reason"],
                    approval.get("affected_systems", "Leon local control plane"),
                    approval.get("permissions", "bounded manual approval"),
                    approval.get("external_effect", "none until consumed"),
                    approval.get("cost_estimate", "unknown/none"),
                    approval.get("risk_level", "medium"),
                    approval.get("risk_class", _risk_class_from_level(approval.get("risk_level", "medium"))),
                    approval.get("expected_change", approval.get("summary") or approval.get("title", "")),
                    approval.get("rollback_plan", "Stop related task and restore previous config if applicable."),
                    approval.get("failure_mode", "If rejected, the action remains blocked until a changed plan is reviewed."),
                    approval.get("plan_fingerprint", ""),
                    status,
                    approval.get("requested_by", "system"),
                    approval.get("required_before"),
                    approval.get("decided_at"),
                    approval.get("note", ""),
                    approval.get("expires_at"),
                    approval.get("consumed_at"),
                    created_at,
                    updated_at,
                ),
            )

        for item in seed.get("required_env", []):
            conn.execute(
                "INSERT INTO required_env(key, purpose, created_at) VALUES (?, ?, ?)",
                (item["key"], item["purpose"], created_at),
            )

        for index, rule in enumerate(seed.get("engineering_rules", [])):
            conn.execute(
                "INSERT INTO engineering_rules(sort_order, rule) VALUES (?, ?)",
                (index, rule),
            )

        self.append_audit_event(
            conn,
            actor_type="system",
            actor_id="control-plane",
            event_type="control_plane_seeded",
            summary="SQLite control-plane store initialized from JSON seed.",
            risk_level="low",
            evidence="state/control-plane.seed.json",
            timestamp=created_at,
        )

    def get_state(self) -> dict[str, Any]:
        self.initialize()
        with self.connect() as conn:
            metadata = {
                row["key"]: json.loads(row["value"])
                for row in conn.execute("SELECT key, value FROM metadata")
            }
            phases = [
                dict(row)
                for row in conn.execute("SELECT id, title, goal, status FROM phases ORDER BY sort_order")
            ]
            tasks = []
            for row in conn.execute(
                """
                SELECT id, title, goal, phase_id, owner, status, priority, risk_level,
                       value_score, source_refs_json, parent_task_id, approval_required,
                       acceptance_criteria, blocked_reason, result, verification_note,
                       review_note, created_at, updated_at, done_at
                FROM tasks
                ORDER BY CASE priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 ELSE 2 END, created_at, id
                """
            ):
                task = dict(row)
                task["risk"] = task["risk_level"]
                task["acceptance"] = task["acceptance_criteria"]
                try:
                    task["source_refs"] = json.loads(task.get("source_refs_json") or "[]")
                except json.JSONDecodeError:
                    task["source_refs"] = []
                task["subtasks"] = []
                task["subtask_count"] = 0
                task["approval_count"] = 0
                task["approval_id"] = ""
                task["approval_gate_summary"] = ""
                task["approval_status"] = "required_not_created" if task["approval_required"] else "none"
                task["audit_events"] = []
                tasks.append(task)
            approvals = []
            for row in conn.execute(
                """
                SELECT id, task_id, action_type, summary, reason, affected_systems,
                       permissions, external_effect, cost_estimate, risk_level,
                       risk_class, expected_change, rollback_plan, failure_mode,
                       plan_fingerprint, status, requested_by, required_before,
                       decided_at, decision_note, expires_at, consumed_at,
                       created_at, updated_at
                FROM approvals
                ORDER BY created_at, id
                """
            ):
                item = dict(row)
                item["title"] = item["summary"]
                item["note"] = item["decision_note"]
                approvals.append(item)
            task_by_id = {task["id"]: task for task in tasks}
            approval_rank = {
                "none": 0,
                "required_not_created": 1,
                "expired": 2,
                "rejected": 3,
                "pending": 4,
                "approved": 5,
                "consumed": 6,
            }
            for approval in approvals:
                task_id = approval.get("task_id")
                if task_id not in task_by_id:
                    continue
                task = task_by_id[task_id]
                task["approval_count"] += 1
                status = str(approval.get("status") or "pending")
                if approval_rank.get(status, 0) >= approval_rank.get(task["approval_status"], 0):
                    task["approval_status"] = status
                    task["approval_id"] = approval["id"]
                    task["approval_gate_summary"] = approval.get("summary") or approval.get("reason") or ""
            for task in tasks:
                parent_id = task.get("parent_task_id")
                if parent_id and parent_id in task_by_id:
                    parent = task_by_id[parent_id]
                    parent["subtask_count"] += 1
                    parent["subtasks"].append(
                        {
                            "id": task["id"],
                            "title": task["title"],
                            "status": task["status"],
                            "priority": task["priority"],
                            "risk_level": task["risk_level"],
                            "value_score": task["value_score"],
                        }
                    )
            required_env = [
                dict(row)
                for row in conn.execute("SELECT key, purpose FROM required_env ORDER BY created_at, key")
            ]
            engineering_rules = [
                row["rule"]
                for row in conn.execute("SELECT rule FROM engineering_rules ORDER BY sort_order")
            ]
            audit_events = [
                sanitize_audit_event_for_display(dict(row))
                for row in conn.execute(
                    """
                    SELECT id, sequence, timestamp, actor_type, actor_id, event_type,
                           task_id, approval_id, risk_level, summary, evidence,
                           redacted_payload_json, prev_hash, event_hash
                    FROM audit_events
                    ORDER BY sequence DESC
                    LIMIT 50
                    """
                )
            ]
            task_ids = list(task_by_id)
            if task_ids:
                placeholders = ",".join("?" for _ in task_ids)
                task_audit_rows = conn.execute(
                    f"""
                    SELECT id, sequence, timestamp, event_type, task_id, summary
                    FROM audit_events
                    WHERE task_id IN ({placeholders})
                    ORDER BY sequence DESC
                    """,
                    task_ids,
                )
                for event in task_audit_rows:
                    task_id = event["task_id"]
                    if task_id in task_by_id and len(task_by_id[task_id]["audit_events"]) < 10:
                        task_by_id[task_id]["audit_events"].append(
                            {
                                "id": event["id"],
                                "sequence": event["sequence"],
                                "timestamp": event["timestamp"],
                                "event_type": event["event_type"],
                                "summary": redact_audit_text(event["summary"]),
                            }
                        )
            agent_runs = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, task_id, agent_role, role, status, task_type, complexity, risk,
                           privacy, budget_mode, provider, route, model, reasoning_effort,
                           route_reason, model_route_json, approval_required, task_json,
                           task_packet_json, input_sources_json, allowed_actions_json,
                           forbidden_actions_json, result_summary, output_json, confidence,
                           cost_estimate_json, risk_assessment_json, evidence_json,
                           review_status, review_note, reviewer_result_json,
                           rollback_status_json, recovery_suggestions_json, next_action,
                           created_at, updated_at, started_at, completed_at
                    FROM agent_runs
                    ORDER BY created_at DESC, id DESC
                    LIMIT 50
                    """
                )
            ]
            for run in agent_runs:
                run["task"] = _json_loads(run.get("task_json"), {"id": run.get("task_id")})
                run["model_route"] = _json_loads(run.get("model_route_json"), {
                    "provider": run.get("provider"),
                    "route": run.get("route"),
                    "model": run.get("model"),
                    "reasoning_effort": run.get("reasoning_effort"),
                    "reason": run.get("route_reason"),
                })
                run["input_sources"] = _json_loads(run.get("input_sources_json"), [])
                run["output"] = _json_loads(run.get("output_json"), {})
                run["cost_estimate"] = _json_loads(run.get("cost_estimate_json"), {})
                run["risk_assessment"] = _json_loads(run.get("risk_assessment_json"), {})
                run["reviewer_result"] = _json_loads(run.get("reviewer_result_json"), {})
                run["rollback_status"] = _json_loads(run.get("rollback_status_json"), {})
                run["recovery_suggestions"] = _json_loads(run.get("recovery_suggestions_json"), [])
                run["evidence"] = _json_loads(run.get("evidence_json"), [])
            agent_assignment_proposals = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, task_id, status, agent_role, runner_kind, execution_mode,
                           execution_allowed, external_calls_made, external_calls_allowed,
                           secret_values_read, shell_commands_allowed, file_writes_allowed,
                           task_type, complexity, risk, privacy, budget_mode,
                           provider, route, model, reasoning_effort, route_reason,
                           task_packet_json, allowed_actions_json, forbidden_actions_json,
                           proposal_json, applied_agent_run_id, review_note, audit_event_id,
                           created_at, updated_at, applied_at
                    FROM agent_assignment_proposals
                    ORDER BY created_at DESC, id DESC
                    LIMIT 50
                    """
                )
            ]
            provider_dry_runs = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, task_id, agent_assignment_proposal_id, provider_id,
                           adapter_id, status, decision, execution_allowed,
                           provider_calls_made, dependency_installed, sdk_imported,
                           secret_values_read, approval_consumed,
                           shell_commands_allowed, file_writes_allowed,
                           required_env_keys_json, missing_env_keys_json,
                           dry_run_json, audit_event_id, created_at
                    FROM provider_dry_runs
                    ORDER BY created_at DESC, id DESC
                    LIMIT 50
                    """
                )
            ]
            routing_decisions = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, created_at, input_text_redacted, route, intent, confidence,
                           complexity, risk_level, privacy_level, urgency, value_score,
                           requires_sources, requires_tool, external_effect, approval_required,
                           approval_reason, recommended_task_status, provider, model_route,
                           model, model_reason, decision_json, audit_event_id
                    FROM routing_decisions
                    ORDER BY created_at DESC, id DESC
                    LIMIT 50
                    """
                )
            ]
            orchestration_proposals = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, routing_decision_id, status, route, summary,
                           execution_allowed, requires_user_review,
                           recommended_next_step, proposal_json, applied_task_id,
                           applied_approval_id, review_note, audit_event_id,
                           created_at, updated_at, applied_at
                    FROM orchestration_proposals
                    ORDER BY created_at DESC, id DESC
                    LIMIT 50
                    """
                )
            ]
            decision_feedback = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, routing_decision_id, feedback_type, note,
                           actor_type, actor_id, audit_event_id, created_at
                    FROM decision_feedback
                    ORDER BY created_at DESC, id DESC
                    LIMIT 100
                    """
                )
            ]
            routing_eval_cases = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, routing_decision_id, source_feedback_id,
                           input_text_redacted, expected_route, actual_route,
                           failure_type, reason, status, case_json,
                           audit_event_id, created_at
                    FROM routing_eval_cases
                    ORDER BY created_at DESC, id DESC
                    LIMIT 100
                    """
                )
            ]
            routing_eval_runs = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, release_label, decision_logic_fingerprint,
                           passed, total, failed, accuracy, safety_case_count,
                           safety_failures, safety_ok, impact_json,
                           summary_json, audit_event_id, created_at
                    FROM routing_eval_runs
                    ORDER BY created_at DESC, id DESC
                    LIMIT 50
                    """
                )
            ]
            for eval_case in routing_eval_cases:
                eval_case["case"] = _json_loads(eval_case.get("case_json"), {})
            for eval_run in routing_eval_runs:
                eval_run["impact"] = _json_loads(eval_run.get("impact_json"), {})
                eval_run["summary"] = _json_loads(eval_run.get("summary_json"), {})
            proposals_by_decision: dict[str, list[dict[str, Any]]] = {}
            for proposal in orchestration_proposals:
                routing_decision_id = str(proposal.get("routing_decision_id") or "")
                if routing_decision_id:
                    proposals_by_decision.setdefault(routing_decision_id, []).append(proposal)
            feedback_by_decision: dict[str, list[dict[str, Any]]] = {}
            for feedback in decision_feedback:
                routing_decision_id = str(feedback.get("routing_decision_id") or "")
                if routing_decision_id:
                    feedback_by_decision.setdefault(routing_decision_id, []).append(feedback)
            for decision in routing_decisions:
                decision_id = str(decision.get("id") or "")
                try:
                    detail = json.loads(str(decision.get("decision_json") or "{}"))
                except (TypeError, ValueError, json.JSONDecodeError):
                    detail = {}
                if not isinstance(detail, dict):
                    detail = {}
                risk_policy = detail.get("risk_policy") if isinstance(detail.get("risk_policy"), dict) else {}
                outcome = _routing_decision_outcome(decision_id, proposals_by_decision=proposals_by_decision)
                feedback_summary = _routing_feedback_summary(feedback_by_decision.get(decision_id, []))
                evidence_summary = {
                    "routing_decision_id": decision_id,
                    "input_text_redacted": decision.get("input_text_redacted", ""),
                    "score": decision.get("value_score", 0),
                    "route": decision.get("route", ""),
                    "risk_level": decision.get("risk_level", ""),
                    "risk_class": detail.get("risk_class") or risk_policy.get("risk_class") or "",
                    "outcome": outcome,
                    "audit_event_id": decision.get("audit_event_id"),
                    "decision_json_fields": [
                        "value_score_inputs",
                        "value_band",
                        "risk_policy",
                        "execution_path",
                        "retrieved_context",
                    ],
                }
                decision["outcome"] = outcome
                decision["decision_evidence"] = evidence_summary
                decision["feedback_summary"] = feedback_summary
            eval_case_summary = {
                "total": len(routing_eval_cases),
                "active": sum(1 for item in routing_eval_cases if item.get("status") == "active"),
                "by_failure_type": {},
            }
            for eval_case in routing_eval_cases:
                failure_type = str(eval_case.get("failure_type") or "unknown")
                eval_case_summary["by_failure_type"][failure_type] = (
                    eval_case_summary["by_failure_type"].get(failure_type, 0) + 1
                )
            latest_eval_run = routing_eval_runs[0] if routing_eval_runs else {}
            tool_manifests = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT tool_id, name, source_type, source_url, purpose, owner,
                           risk_level, status, read_scopes_json, write_scopes_json,
                           required_env_keys_json, cost_profile, resource_profile,
                           external_effects_json, approval_required_for_json,
                           allowed_without_approval_json, forbidden_actions_json,
                           audit_events_json, rollback_notes, maintenance_status,
                           sandbox_required, notes, manifest_json, audit_event_id,
                           created_at, updated_at
                    FROM tool_manifests
                    ORDER BY CASE status
                      WHEN 'approved_write_gated' THEN 0
                      WHEN 'approved_readonly' THEN 1
                      WHEN 'reviewed' THEN 2
                      WHEN 'candidate' THEN 3
                      ELSE 4
                    END, risk_level DESC, name
                    LIMIT 100
                    """
                )
            ]
            tool_permission_checks = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, tool_id, action_type, requested_scope, decision,
                           approval_required, required_gate, reason, risk_level,
                           approval_id, check_json, audit_event_id, created_at
                    FROM tool_permission_checks
                    ORDER BY created_at DESC, id DESC
                    LIMIT 100
                    """
                )
            ]
            connector_manifests = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT connector_id, name, connector_type, status, owner, purpose,
                           read_scopes_json, write_scopes_json, required_env_keys_json,
                           external_system, external_effects_json,
                           approval_required_for_json, allowed_without_approval_json,
                           forbidden_actions_json, connector_policy_allows_autonomy,
                           risk_level, rollback_notes, secret_handling_json, notes,
                           manifest_json, audit_event_id, created_at, updated_at
                    FROM connector_manifests
                    ORDER BY CASE status
                      WHEN 'approved_write_gated' THEN 0
                      WHEN 'approved_readonly' THEN 1
                      WHEN 'disabled' THEN 2
                      ELSE 3
                    END, connector_type, name
                    LIMIT 100
                    """
                )
            ]
            for connector in connector_manifests:
                connector["read_scopes"] = _json_loads(connector.get("read_scopes_json"), [])
                connector["write_scopes"] = _json_loads(connector.get("write_scopes_json"), [])
                connector["required_env_keys"] = _json_loads(connector.get("required_env_keys_json"), [])
                connector["external_effects"] = _json_loads(connector.get("external_effects_json"), [])
                connector["approval_required_for"] = _json_loads(connector.get("approval_required_for_json"), [])
                connector["allowed_without_approval"] = _json_loads(connector.get("allowed_without_approval_json"), [])
                connector["forbidden_actions"] = _json_loads(connector.get("forbidden_actions_json"), [])
                connector["secret_handling"] = _json_loads(connector.get("secret_handling_json"), {})
            connector_permission_checks = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, connector_id, action_type, requested_scope, decision,
                           approval_required, required_gate, reason, risk_level,
                           risk_class, policy_decision, approval_id,
                           connector_executed, write_performed, check_json,
                           audit_event_id, created_at
                    FROM connector_permission_checks
                    ORDER BY created_at DESC, id DESC
                    LIMIT 100
                    """
                )
            ]
            mcp_candidate_intakes = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, tool_id, status, decision, execution_allowed,
                           no_approval_granted, status_unchanged,
                           install_allowed_now, connect_allowed_now,
                           write_allowed_now, checklist_json, audit_event_id,
                           created_at, updated_at
                    FROM mcp_candidate_intakes
                    ORDER BY created_at DESC, id DESC
                    LIMIT 100
                    """
                )
            ]
            planner_previews = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, task_id, decision, execution_allowed,
                           external_calls_made, accounts_connected,
                           secret_values_read, write_allowed_now,
                           approval_required, preview_json, audit_event_id,
                           created_at
                    FROM planner_previews
                    ORDER BY created_at DESC, id DESC
                    LIMIT 50
                    """
                )
            ]
            memory_items = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, status, memory_type, content, source, source_task_id,
                           confidence, sensitivity, privacy_level, expires_at,
                           review_note, correction_of, graph_entities_json,
                           provenance_json, conflict_status, conflict_memory_ids_json, conflict_note,
                           audit_event_id, created_at, updated_at, deleted_at
                    FROM memory_items
                    ORDER BY CASE status
                      WHEN 'candidate' THEN 0
                      WHEN 'active' THEN 1
                      WHEN 'rejected' THEN 2
                      ELSE 3
                    END, updated_at DESC, id DESC
                    LIMIT 100
                    """
                )
            ]
            for item in memory_items:
                try:
                    item["graph_entities"] = json.loads(item.get("graph_entities_json") or "[]")
                except json.JSONDecodeError:
                    item["graph_entities"] = []
                item["provenance"] = _json_loads(item.get("provenance_json"), {})
                if not item["provenance"]:
                    item["provenance"] = {
                        "source": item.get("source") or "",
                        "source_task_id": item.get("source_task_id"),
                        "captured_by": "leon_control_plane",
                    }
                item["conflict_memory_ids"] = _json_loads(item.get("conflict_memory_ids_json"), [])
                item["has_conflicts"] = item.get("conflict_status") == "conflicted" or bool(item["conflict_memory_ids"])
            memory_graph_edges = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, source_memory_id, subject, predicate, object, relationship_type, confidence,
                           source, status, audit_event_id, created_at, updated_at, deleted_at
                    FROM memory_graph_edges
                    ORDER BY updated_at DESC, id DESC
                    LIMIT 100
                    """
                )
            ]
            memory_graph_entities = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, entity_type, label, source_memory_id, external_ref,
                           provenance_json, confidence, status, audit_event_id,
                           created_at, updated_at, deleted_at
                    FROM memory_graph_entities
                    ORDER BY updated_at DESC, id DESC
                    LIMIT 200
                    """
                )
            ]
            for entity in memory_graph_entities:
                entity["provenance"] = _json_loads(entity.get("provenance_json"), {})
            memory_graph_relationships = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT relationship.id, relationship.relationship_type,
                           relationship.from_entity_id, relationship.to_entity_id,
                           relationship.source_memory_id, relationship.label,
                           relationship.provenance_json, relationship.confidence,
                           relationship.status, relationship.audit_event_id,
                           relationship.created_at, relationship.updated_at, relationship.deleted_at,
                           source_entity.entity_type AS from_entity_type,
                           source_entity.label AS from_label,
                           target_entity.entity_type AS to_entity_type,
                           target_entity.label AS to_label
                    FROM memory_graph_relationships AS relationship
                    JOIN memory_graph_entities AS source_entity ON source_entity.id = relationship.from_entity_id
                    JOIN memory_graph_entities AS target_entity ON target_entity.id = relationship.to_entity_id
                    ORDER BY relationship.updated_at DESC, relationship.id DESC
                    LIMIT 200
                    """
                )
            ]
            for relationship in memory_graph_relationships:
                relationship["provenance"] = _json_loads(relationship.get("provenance_json"), {})
            source_records = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, source_type, source_ref, title, status, content_hash,
                           content_excerpt, content_bytes, metadata_json,
                           secret_scan_json, audit_event_id, created_at, updated_at,
                           deleted_at
                    FROM source_records
                    ORDER BY CASE status
                      WHEN 'active' THEN 0
                      WHEN 'blocked_secret' THEN 1
                      WHEN 'scrubbed' THEN 2
                      ELSE 3
                    END, updated_at DESC, id DESC
                    LIMIT 200
                    """
                )
            ]
            for record in source_records:
                record["metadata"] = _json_loads(record.get("metadata_json"), {})
                record["secret_scan"] = _json_loads(record.get("secret_scan_json"), {})
            memory_retrieval_queries = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, query_redacted, scope, answer, answer_status,
                           confidence, latency_ms, relevance_score, match_count,
                           memory_match_count, source_match_count, conflict_count,
                           source_refs_json, related_graph_entries_json,
                           conflicts_json, metrics_json, audit_event_id, created_at
                    FROM memory_retrieval_queries
                    ORDER BY created_at DESC, id DESC
                    LIMIT 50
                    """
                )
            ]
            for retrieval in memory_retrieval_queries:
                retrieval["source_refs"] = _json_loads(retrieval.get("source_refs_json"), [])
                retrieval["related_graph_entries"] = _json_loads(retrieval.get("related_graph_entries_json"), [])
                retrieval["conflicts"] = _json_loads(retrieval.get("conflicts_json"), [])
                retrieval["metrics"] = _json_loads(retrieval.get("metrics_json"), {})
            rollback_records = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, kind, status, risk_class, task_id, approval_id,
                           action_ref_type, action_ref_id, target_type, target_ref,
                           operation, summary, before_snapshot_json, after_snapshot_json,
                           undo_payload_json, patch_snapshot, test_results_json,
                           audit_details_json, compensating_action_json,
                           deletion_supported, undo_supported, scrub_supported,
                           compensation_supported, audit_event_id,
                           created_at, updated_at, applied_at
                    FROM rollback_records
                    ORDER BY created_at DESC, id DESC
                    LIMIT 100
                    """
                )
            ]
            for record in rollback_records:
                record["before_snapshot"] = _json_loads(record.get("before_snapshot_json"), {})
                record["after_snapshot"] = _json_loads(record.get("after_snapshot_json"), {})
                record["undo_payload"] = _json_loads(record.get("undo_payload_json"), {})
                record["test_results"] = _json_loads(record.get("test_results_json"), {})
                record["audit_details"] = _json_loads(record.get("audit_details_json"), {})
                record["compensating_action"] = _json_loads(record.get("compensating_action_json"), {})
            missing_component_records = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, requested_component, requested_capability, route, space,
                           task_status, risk_level, fallback_component_ids_json,
                           context_json, source_ref, run_id, task_id, status,
                           audit_event_id, created_at, updated_at
                    FROM missing_component_records
                    ORDER BY created_at DESC, id DESC
                    LIMIT 100
                    """
                )
            ]
            for record in missing_component_records:
                record["fallback_component_ids"] = _json_loads(record.get("fallback_component_ids_json"), [])
                record["context"] = _json_loads(record.get("context_json"), {})
            night_queue_runs = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, status, started_at, ended_at, selected_agents_json,
                           selected_models_json, cost_estimate_json, policy_limits_json,
                           action_results_json, failures_json, sources_json,
                           changes_json, rollback_status_json, morning_brief_json,
                           audit_event_id, completed_audit_event_id, created_at, updated_at
                    FROM night_queue_runs
                    ORDER BY started_at DESC, id DESC
                    LIMIT 50
                    """
                )
            ]
            for run in night_queue_runs:
                run["selected_agents"] = _json_loads(run.get("selected_agents_json"), [])
                run["selected_models"] = _json_loads(run.get("selected_models_json"), [])
                run["cost_estimate"] = _json_loads(run.get("cost_estimate_json"), {})
                run["policy_limits"] = _json_loads(run.get("policy_limits_json"), {})
                run["action_results"] = _json_loads(run.get("action_results_json"), [])
                run["failures"] = _json_loads(run.get("failures_json"), [])
                run["sources"] = _json_loads(run.get("sources_json"), [])
                run["changes"] = _json_loads(run.get("changes_json"), [])
                run["rollback_status"] = _json_loads(run.get("rollback_status_json"), {})
                run["morning_brief"] = _json_loads(run.get("morning_brief_json"), {})

        metadata.setdefault("status", "active")
        metadata["updated_at"] = now_iso()
        memory_by_id = {item["id"]: item for item in memory_items}
        conflicting_memories = []
        for item in memory_items:
            conflict_ids = [conflict_id for conflict_id in item.get("conflict_memory_ids", []) if conflict_id in memory_by_id]
            if item.get("conflict_status") == "conflicted" or conflict_ids:
                conflicting_memories.append({
                    "memory_id": item["id"],
                    "status": item.get("status"),
                    "conflict_status": item.get("conflict_status") or "none",
                    "conflict_memory_ids": conflict_ids,
                    "conflict_note": item.get("conflict_note") or "",
                    "confidence": item.get("confidence"),
                    "provenance": item.get("provenance", {}),
                })
        rollback_by_action_ref = {
            (record.get("action_ref_type"), record.get("action_ref_id")): record
            for record in rollback_records
            if record.get("action_ref_type") and record.get("action_ref_id")
        }
        rollback_records_by_action_ref: dict[tuple[Any, Any], list[dict[str, Any]]] = {}
        for record in rollback_records:
            key = (record.get("action_ref_type"), record.get("action_ref_id"))
            if key[0] and key[1]:
                rollback_records_by_action_ref.setdefault(key, []).append(record)
        rollback_by_approval: dict[str, list[dict[str, Any]]] = {}
        for record in rollback_records:
            approval_id = str(record.get("approval_id") or "")
            if approval_id:
                rollback_by_approval.setdefault(approval_id, []).append(record)
        retrieval_count = len(memory_retrieval_queries)
        retrieval_with_matches = [item for item in memory_retrieval_queries if int(item.get("match_count") or 0) > 0]
        memory_retrieval_metrics = {
            "query_count": retrieval_count,
            "successful_query_count": len(retrieval_with_matches),
            "success_rate": round(len(retrieval_with_matches) / retrieval_count, 4) if retrieval_count else 0,
            "average_latency_ms": round(
                sum(int(item.get("latency_ms") or 0) for item in memory_retrieval_queries) / retrieval_count,
                2,
            ) if retrieval_count else 0,
            "average_relevance_score": round(
                sum(float(item.get("relevance_score") or 0) for item in memory_retrieval_queries) / retrieval_count,
                4,
            ) if retrieval_count else 0,
            "latest_latency_ms": int(memory_retrieval_queries[0].get("latency_ms") or 0) if memory_retrieval_queries else 0,
            "latest_relevance_score": float(memory_retrieval_queries[0].get("relevance_score") or 0) if memory_retrieval_queries else 0,
            "conflict_marked_query_count": sum(1 for item in memory_retrieval_queries if int(item.get("conflict_count") or 0) > 0),
        }
        rollback_by_task: dict[str, list[dict[str, Any]]] = {}
        for record in rollback_records:
            task_id = str(record.get("task_id") or "")
            if task_id:
                rollback_by_task.setdefault(task_id, []).append(record)
        for approval in approvals:
            approval_id = str(approval.get("id") or "")
            task_id = str(approval.get("task_id") or "")
            records = rollback_by_approval.get(approval_id, []) + rollback_by_task.get(task_id, [])[:4]
            graph_entities_for_approval = [
                entity
                for entity in memory_graph_entities
                if entity.get("entity_type") == "approval"
                and (entity.get("external_ref") == approval_id or entity.get("provenance", {}).get("approval_id") == approval_id)
            ]
            graph_relationships_for_approval = [
                relationship
                for relationship in memory_graph_relationships
                if relationship.get("provenance", {}).get("approval_id") == approval_id
            ]
            transparency = build_transparency_inspectors(
                surface="approval",
                record=approval,
                audit_events=_related_audit_events(
                    audit_events,
                    ref_type="approval",
                    ref_id=approval_id,
                    task_id=task_id or None,
                    approval_id=approval_id,
                ),
                rollback_records=records[:5],
                graph_entities=graph_entities_for_approval,
                graph_relationships=graph_relationships_for_approval,
            )
            approval["transparency"] = transparency
            approval["default_view"] = transparency["default_view"]
            approval["inspectors"] = transparency["inspectors"]
        for record in source_records:
            source_id = str(record.get("id") or "")
            records = [
                item
                for item in rollback_records
                if item.get("action_ref_type") == "source_record" and item.get("action_ref_id") == source_id
            ][:5]
            graph_entities_for_source = [
                entity
                for entity in memory_graph_entities
                if entity.get("provenance", {}).get("source_record_id") == source_id
            ]
            graph_relationships_for_source = [
                relationship
                for relationship in memory_graph_relationships
                if relationship.get("provenance", {}).get("source_record_id") == source_id
            ]
            transparency = build_transparency_inspectors(
                surface="source_record",
                record=record,
                audit_events=_related_audit_events(
                    audit_events,
                    ref_type="source_record",
                    ref_id=source_id,
                ),
                rollback_records=records,
                graph_entities=graph_entities_for_source,
                graph_relationships=graph_relationships_for_source,
            )
            record["transparency"] = transparency
            record["default_view"] = transparency["default_view"]
            record["inspectors"] = transparency["inspectors"]
        for run in agent_runs:
            direct_record = rollback_by_action_ref.get(("agent_run", run["id"]))
            task_records = rollback_by_task.get(str(run.get("task_id") or ""), [])
            records = ([direct_record] if direct_record else []) + [
                record for record in task_records if record is not direct_record
            ][:4]
            if records:
                run["rollback_records"] = records[:5]
                run["rollback_status"] = {
                    "status": records[0]["status"],
                    "record_count": len(records),
                    "latest_record_id": records[0]["id"],
                    "kinds": sorted({str(record["kind"]) for record in records}),
                    "operations": sorted({str(record["operation"]) for record in records}),
                }
            elif not run.get("rollback_status"):
                risk_class = (run.get("risk_assessment") or {}).get("risk_class", "")
                run["rollback_status"] = {
                    "status": "not_applicable" if risk_class == "" else "missing",
                    "record_count": 0,
                    "latest_record_id": "",
                    "kinds": [],
                    "operations": [],
                }
            graph_entities_for_run = [
                entity
                for entity in memory_graph_entities
                if entity.get("external_ref") == run["id"] or entity.get("provenance", {}).get("agent_run_id") == run["id"]
            ]
            graph_relationships_for_run = [
                relationship
                for relationship in memory_graph_relationships
                if relationship.get("provenance", {}).get("agent_run_id") == run["id"]
            ]
            run_records = run.get("rollback_records") if isinstance(run.get("rollback_records"), list) else []
            transparency = build_transparency_inspectors(
                surface="agent_run",
                record=run,
                audit_events=_related_audit_events(
                    audit_events,
                    ref_type="agent_run",
                    ref_id=run["id"],
                    task_id=str(run.get("task_id") or "") or None,
                ),
                rollback_records=run_records,
                graph_entities=graph_entities_for_run,
                graph_relationships=graph_relationships_for_run,
            )
            run["transparency"] = transparency
            run["default_view"] = transparency["default_view"]
            run["inspectors"] = transparency["inspectors"]
        for run in night_queue_runs:
            records = rollback_records_by_action_ref.get(("night_queue_run", run["id"]), [])[:5]
            if records:
                run["rollback_records"] = records
                rollback_status = run.get("rollback_status") if isinstance(run.get("rollback_status"), dict) else {}
                run["rollback_status"] = {
                    **rollback_status,
                    "recorded": True,
                    "record_count": len(records),
                    "latest_record_id": records[0]["id"],
                    "kinds": sorted({str(record["kind"]) for record in records}),
                    "operations": sorted({str(record["operation"]) for record in records}),
                }
        run_log = list(agent_runs)
        rollback_attention = [
            {
                "rollback_record_id": record["id"],
                "kind": record["kind"],
                "status": record["status"],
                "risk_class": record["risk_class"],
                "target": f"{record['target_type']}:{record['target_ref']}",
                "operation": record["operation"],
                "task_id": record.get("task_id"),
            }
            for record in rollback_records
            if record["status"] in {"prepared", "compensation_unavailable", "undo_supported", "scrub_supported", "delete_supported"}
        ][:10]
        connector_failures = [
            {
                "connector_permission_check_id": check["id"],
                "connector_id": check["connector_id"],
                "action_type": check["action_type"],
                "requested_scope": check["requested_scope"],
                "decision": check["decision"],
                "risk_class": check.get("risk_class") or "",
                "policy_decision": check.get("policy_decision") or "",
                "required_gate": check.get("required_gate") or "",
                "reason": check.get("reason") or "",
                "connector_executed": bool(check.get("connector_executed")),
                "write_performed": bool(check.get("write_performed")),
            }
            for check in connector_permission_checks
            if check.get("decision") != "allowed"
        ][:10]
        missing_ui_capabilities = [
            {
                "missing_component_record_id": record["id"],
                "requested_component": record["requested_component"],
                "requested_capability": record.get("requested_capability") or "",
                "route": record.get("route") or "",
                "space": record.get("space") or "",
                "risk_level": record.get("risk_level") or "",
                "fallback_component_ids": record.get("fallback_component_ids") or [],
                "task_id": record.get("task_id"),
                "status": record.get("status") or "open",
                "source_ref": record.get("source_ref") or "",
                "run_id": record.get("run_id"),
            }
            for record in missing_component_records
            if record.get("status") == "open"
        ][:10]
        morning_brief = {
            "status": "preview",
            "agent_runs": run_log[:10],
            "night_queue_runs": night_queue_runs[:5],
            "latest_night_run": night_queue_runs[0] if night_queue_runs else None,
            "generated": night_queue_runs[0].get("morning_brief", {}) if night_queue_runs else None,
            "sections": (night_queue_runs[0].get("morning_brief", {}) if night_queue_runs else {}).get("sections", []),
            "details_collapsed_by_default": True,
            "rollback": {
                "records": rollback_records[:10],
                "attention": rollback_attention,
            },
            "connector_failures": connector_failures,
            "missing_ui_capabilities": missing_ui_capabilities,
            "attention": [
                {
                    "agent_run_id": run["id"],
                    "task_id": run["task_id"],
                    "role": run.get("role") or run.get("agent_role"),
                    "next_action": run.get("next_action", "review_agent_run"),
                    "risk_class": (run.get("risk_assessment") or {}).get("risk_class", ""),
                    "rollback_status": run.get("rollback_status", {}),
                }
                for run in run_log
                if run.get("next_action") == "review_agent_run" or run.get("status") in {"waiting_for_review", "failed"}
            ][:10] + connector_failures[:5] + rollback_attention[:5] + missing_ui_capabilities[:5],
        }
        partial_failures: list[dict[str, Any]] = []
        for run in run_log:
            if run.get("status") != "failed":
                continue
            partial_failures.append(
                {
                    "type": "agent_run",
                    "id": run["id"],
                    "task_id": run.get("task_id"),
                    "status": run.get("status"),
                    "summary": run.get("result_summary") or (run.get("output") or {}).get("summary") or "Agent run failed.",
                    "visible_to_user": True,
                    "rollback_status": run.get("rollback_status", {}),
                    "recovery_suggestions": _normalize_recovery_suggestions(
                        run.get("recovery_suggestions"),
                        fallback_reason=run.get("result_summary") or "Agent run failed.",
                    ),
                }
            )
        for run in night_queue_runs:
            failures = run.get("failures") if isinstance(run.get("failures"), list) else []
            if not failures and run.get("status") not in {"failed", "completed_with_attention"}:
                continue
            suggestions: list[dict[str, str]] = []
            for failure in failures:
                if not isinstance(failure, dict):
                    continue
                suggestions.extend(
                    _normalize_recovery_suggestions(
                        failure.get("recovery_suggestions"),
                        fallback_reason=failure.get("reason") or failure.get("policy_reason") or "Night queue action failed.",
                    )
                )
            deduped_suggestions: list[dict[str, str]] = []
            seen_suggestions: set[tuple[str, str]] = set()
            for suggestion in suggestions:
                key = (suggestion["action"], suggestion["summary"])
                if key in seen_suggestions:
                    continue
                seen_suggestions.add(key)
                deduped_suggestions.append(suggestion)
            partial_failures.append(
                {
                    "type": "night_queue_run",
                    "id": run["id"],
                    "status": run.get("status"),
                    "failure_count": len(failures),
                    "failures": failures[:5],
                    "visible_to_user": True,
                    "rollback_status": run.get("rollback_status", {}),
                    "recovery_suggestions": deduped_suggestions[:6],
                }
            )
        for failure in connector_failures:
            partial_failures.append(
                {
                    "type": "connector_permission_check",
                    "id": failure["connector_permission_check_id"],
                    "status": failure.get("decision"),
                    "summary": failure.get("reason") or "Connector action was not allowed.",
                    "visible_to_user": True,
                    "recovery_suggestions": [
                        {
                            "action": "review_connector_gate",
                            "summary": "Review connector scope, missing secrets, required approval, or policy denial before retrying.",
                        }
                    ],
                }
            )
        partial_failure_summary = {
            "visible_to_user": True,
            "count": len(partial_failures),
            "has_partial_failure": bool(partial_failures),
            "items": partial_failures[:15],
        }
        morning_brief["partial_failure_summary"] = partial_failure_summary
        morning_transparency = build_transparency_inspectors(
            surface="morning_brief",
            record=morning_brief.get("generated") or morning_brief,
            audit_events=[
                event
                for event in audit_events
                if event.get("event_type") in {
                    "night_queue_started",
                    "night_queue_completed",
                    "morning_brief_generated",
                    "connector_permission_denied",
                    "connector_permission_waiting_for_secret",
                    "connector_permission_waiting_for_approval",
                    "missing_component_registered",
                }
            ][:12],
            rollback_records=rollback_records[:10],
            graph_entities=[],
            graph_relationships=[],
        )
        morning_brief["transparency"] = morning_transparency
        morning_brief["default_view"] = morning_transparency["default_view"]
        morning_brief["inspectors"] = morning_transparency["inspectors"]
        return _redact_audit_value({
            "metadata": metadata,
            "phases": phases,
            "tasks": tasks,
            "approvals": approvals,
            "required_env": required_env,
            "engineering_rules": engineering_rules,
            "audit_events": audit_events,
            "agent_run_roles": SUPPORTED_AGENT_RUN_ROLES,
            "agent_runs": agent_runs,
            "run_log": run_log,
            "morning_brief": morning_brief,
            "partial_failures": partial_failures[:15],
            "partial_failure_summary": partial_failure_summary,
            "agent_assignment_proposals": agent_assignment_proposals,
            "provider_dry_runs": provider_dry_runs,
            "routing_decisions": routing_decisions,
            "decision_feedback": decision_feedback,
            "routing_eval_cases": routing_eval_cases,
            "routing_eval_case_summary": eval_case_summary,
            "routing_eval_runs": routing_eval_runs,
            "routing_eval_latest_run": latest_eval_run,
            "orchestration_proposals": orchestration_proposals,
            "tool_manifests": tool_manifests,
            "tool_permission_checks": tool_permission_checks,
            "connector_manifests": connector_manifests,
            "connector_permission_checks": connector_permission_checks,
            "mcp_candidate_intakes": mcp_candidate_intakes,
            "planner_previews": planner_previews,
            "memory_graph_schema": {
                "entity_types": sorted(GRAPH_ENTITY_TYPES),
                "relationship_types": sorted(GRAPH_RELATIONSHIP_TYPES),
                "memory_required_fields": ["provenance", "confidence", "created_at", "updated_at"],
                "conflict_statuses": sorted(MEMORY_CONFLICT_STATUSES),
            },
            "memory_items": memory_items,
            "memory_graph_edges": memory_graph_edges,
            "memory_graph_entities": memory_graph_entities,
            "memory_graph_relationships": memory_graph_relationships,
            "source_records": source_records,
            "conflicting_memories": conflicting_memories,
            "memory_retrieval_queries": memory_retrieval_queries,
            "memory_retrieval_metrics": memory_retrieval_metrics,
            "rollback_registry": rollback_records,
            "missing_component_records": missing_component_records,
            "night_queue_runs": night_queue_runs,
        })

    def create_task(
        self,
        *,
        title: str,
        goal: str,
        phase_id: str | None = None,
        owner: str = "Codex",
        status: str = "new",
        priority: str = "P1",
        risk_level: str = "medium",
        approval_required: bool = False,
        acceptance_criteria: str = "",
        value_score: int = 3,
        source_refs: list[str] | str | None = None,
        parent_task_id: str | None = None,
        actor_type: str = "user",
        actor_id: str = "dashboard",
    ) -> str:
        title = title.strip()
        goal = goal.strip()
        if not title or not goal:
            raise ValueError("Task title and goal are required")
        _reject_secret_like_text("Task title", title)
        _reject_secret_like_text("Task goal", goal)
        _reject_secret_like_text("Task acceptance_criteria", acceptance_criteria)
        if status not in TASK_STATUSES:
            raise ValueError("Invalid task status")
        if status not in {"new", "planned"}:
            raise ValueError("New tasks must start as new or planned; use status transitions for gated states")
        if priority not in {"P0", "P1", "P2"}:
            raise ValueError("Invalid priority")
        value_score = _normalize_value_score(value_score)
        source_refs = _normalize_source_refs(source_refs)
        parent_task_id = str(parent_task_id or "").strip() or None
        self.initialize()
        task_id = slug_id("task", title)
        timestamp = now_iso()
        with self.connect() as conn:
            if parent_task_id and conn.execute("SELECT 1 FROM tasks WHERE id = ?", (parent_task_id,)).fetchone() is None:
                raise ValueError("parent_task_id must refer to an existing task")
            suffix = 2
            base_id = task_id
            while conn.execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone():
                task_id = f"{base_id}-{suffix}"
                suffix += 1
            conn.execute(
                """
                INSERT INTO tasks(
                  id, title, goal, phase_id, owner, status, priority, risk_level,
                  value_score, source_refs_json, parent_task_id, approval_required,
                  acceptance_criteria, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    title,
                    goal,
                    phase_id,
                    owner,
                    status,
                    priority,
                    risk_level,
                    value_score,
                    json.dumps(source_refs, ensure_ascii=False, sort_keys=True),
                    parent_task_id,
                    int(approval_required),
                    acceptance_criteria,
                    timestamp,
                    timestamp,
                ),
            )
            self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="task_created",
                task_id=task_id,
                risk_level=risk_level,
                summary=f"Task created: {title}",
                evidence="dashboard task create API",
                redacted_payload={
                    "title": title,
                    "priority": priority,
                    "risk_level": risk_level,
                    "value_score": value_score,
                    "source_ref_count": len(source_refs),
                    "source_refs": source_refs,
                    "parent_task_id": parent_task_id,
                },
                timestamp=timestamp,
            )
        return task_id

    def register_missing_component_need(
        self,
        *,
        requested_component: str,
        requested_capability: str = "",
        route: str = "",
        space: str = "",
        task_status: str = "",
        risk_level: str = "medium",
        fallback_component_ids: list[str] | None = None,
        context: dict[str, Any] | None = None,
        source_ref: str = "",
        run_id: str | None = None,
        actor_type: str = "system",
        actor_id: str = "missing-component-protocol",
    ) -> dict[str, Any]:
        requested_component = str(requested_component or "").strip() or "unknown_ui_capability"
        requested_capability = str(requested_capability or "").strip()
        route = str(route or "").strip()
        space = str(space or "").strip()
        task_status = str(task_status or "").strip()
        risk_level = str(risk_level or "medium").strip() or "medium"
        source_ref = str(source_ref or "").strip()
        run_id = str(run_id or "").strip() or None
        fallback_component_ids = _as_non_empty_list(fallback_component_ids or [])
        context = dict(context or {})
        context = {
            **context,
            "requested_component": requested_component,
            "requested_capability": requested_capability,
            "route": route,
            "space": space,
            "task_status": task_status,
            "risk_level": risk_level,
            "fallback_component_ids": fallback_component_ids,
            "source_ref": source_ref,
            "run_id": run_id,
        }

        for label, value in {
            "requested_component": requested_component,
            "requested_capability": requested_capability,
            "route": route,
            "space": space,
            "task_status": task_status,
            "risk_level": risk_level,
            "source_ref": source_ref,
        }.items():
            _reject_secret_like_text(f"Missing component {label}", value)
        assert_no_secrets("Missing component context", context)

        display_component = requested_component.replace("route:", "route ")
        task_title = f"Implement UI capability: {display_component}"
        task_goal = (
            f"Design and register a reviewed Leon UI capability for {display_component}. "
            f"Temporary fallback uses: {', '.join(fallback_component_ids) or 'registered safe context components'}."
        )
        acceptance = (
            "Component contract declares purpose, allowed spaces, required state, safety role, "
            "fallback replacement behavior, and tests proving unknown UI is no longer needed."
        )
        task_refs = [ref for ref in [source_ref] if ref]
        timestamp = now_iso()
        self.initialize()
        with self.connect() as conn:
            existing = conn.execute(
                """
                SELECT id FROM tasks
                WHERE title = ? AND status NOT IN ('done', 'rejected')
                ORDER BY created_at
                LIMIT 1
                """,
                (task_title,),
            ).fetchone()
        if existing is None:
            task_id = self.create_task(
                title=task_title,
                goal=task_goal,
                owner="Design/System",
                status="new",
                priority="P1",
                risk_level="medium",
                approval_required=False,
                acceptance_criteria=acceptance,
                source_refs=task_refs,
                actor_type=actor_type,
                actor_id=actor_id,
            )
            task_reused = False
        else:
            task_id = str(existing["id"])
            task_reused = True

        record_id = slug_id("missing-component", f"{requested_component}-{route}-{source_ref or run_id or ''}")
        with self.connect() as conn:
            suffix = 2
            base_id = record_id
            while conn.execute("SELECT 1 FROM missing_component_records WHERE id = ?", (record_id,)).fetchone():
                record_id = f"{base_id}-{suffix}"
                suffix += 1
            audit_event_id = self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="missing_component_registered",
                task_id=task_id,
                risk_level=risk_level if risk_level in {"low", "medium", "high"} else "medium",
                summary=f"Missing UI capability registered: {display_component}.",
                evidence="missing component protocol created a local development task and fallback context",
                redacted_payload={
                    "missing_component_record_id": record_id,
                    "requested_component": requested_component,
                    "requested_capability": requested_capability,
                    "route": route,
                    "space": space,
                    "task_status": task_status,
                    "risk_level": risk_level,
                    "fallback_component_ids": fallback_component_ids,
                    "source_ref": source_ref,
                    "run_id": run_id,
                    "task_id": task_id,
                    "task_reused": task_reused,
                    "context": context,
                },
                timestamp=timestamp,
            )
            conn.execute(
                """
                INSERT INTO missing_component_records(
                  id, requested_component, requested_capability, route, space,
                  task_status, risk_level, fallback_component_ids_json,
                  context_json, source_ref, run_id, task_id, status,
                  audit_event_id, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    requested_component,
                    requested_capability,
                    route,
                    space,
                    task_status,
                    risk_level,
                    _json_dumps(fallback_component_ids),
                    _json_dumps(context),
                    source_ref,
                    run_id,
                    task_id,
                    "open",
                    audit_event_id,
                    timestamp,
                    timestamp,
                ),
            )
        return _redact_audit_value({
            "id": record_id,
            "requested_component": requested_component,
            "requested_capability": requested_capability,
            "route": route,
            "space": space,
            "task_status": task_status,
            "risk_level": risk_level,
            "fallback_component_ids": fallback_component_ids,
            "context": context,
            "source_ref": source_ref,
            "run_id": run_id,
            "task_id": task_id,
            "task_reused": task_reused,
            "status": "open",
            "audit_event_id": audit_event_id,
        })

    def update_task_status(
        self,
        task_id: str,
        status: str,
        *,
        blocked_reason: str = "",
        result: str = "",
        verification_note: str = "",
        review_note: str = "",
        approval_id: str | None = None,
        secret_key: str | None = None,
        reopen: bool = False,
        actor_type: str = "reviewer",
        actor_id: str = "dashboard",
    ) -> None:
        if status not in TASK_STATUSES:
            raise ValueError("Invalid task status")
        for label, value in {
            "blocked_reason": blocked_reason,
            "result": result,
            "verification_note": verification_note,
            "review_note": review_note,
        }.items():
            _reject_secret_like_text(label, value)
        self.initialize()
        timestamp = now_iso()
        with self.connect() as conn:
            row = conn.execute("SELECT id, status FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                raise ValueError("Unknown task id")
            old_status = row["status"]
            self._validate_task_transition(
                conn,
                task_id=task_id,
                old_status=old_status,
                new_status=status,
                blocked_reason=blocked_reason,
                result=result,
                verification_note=verification_note,
                review_note=review_note,
                approval_id=approval_id,
                secret_key=secret_key,
                reopen=reopen,
            )
            conn.execute(
                """
                UPDATE tasks
                SET status = ?,
                    blocked_reason = CASE WHEN ? != '' THEN ? ELSE blocked_reason END,
                    result = CASE WHEN ? != '' THEN ? ELSE result END,
                    verification_note = CASE WHEN ? != '' THEN ? ELSE verification_note END,
                    review_note = CASE WHEN ? != '' THEN ? ELSE review_note END,
                    updated_at = ?,
                    done_at = CASE WHEN ? = 'done' THEN ? ELSE done_at END
                WHERE id = ?
                """,
                (
                    status,
                    blocked_reason,
                    blocked_reason,
                    result,
                    result,
                    verification_note,
                    verification_note,
                    review_note,
                    review_note,
                    timestamp,
                    status,
                    timestamp,
                    task_id,
                ),
            )
            event_type = "task_reopened" if old_status in {"done", "rejected"} and status == "planned" else "task_status_changed"
            self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type=event_type,
                task_id=task_id,
                approval_id=approval_id,
                risk_level="low",
                summary=f"Task {task_id} changed from {old_status} to {status}.",
                evidence="dashboard task status API",
                redacted_payload={
                    "old_status": old_status,
                    "new_status": status,
                    "blocked_reason_present": bool(blocked_reason),
                    "result_present": bool(result),
                    "verification_note_present": bool(verification_note),
                    "review_note_present": bool(review_note),
                    "secret_key": secret_key,
                },
                timestamp=timestamp,
            )

    def _validate_task_transition(
        self,
        conn: sqlite3.Connection,
        *,
        task_id: str,
        old_status: str,
        new_status: str,
        blocked_reason: str,
        result: str,
        verification_note: str,
        review_note: str,
        approval_id: str | None,
        secret_key: str | None,
        reopen: bool,
    ) -> None:
        if old_status == new_status:
            return
        allowed = BASELINE_TRANSITIONS.get(old_status, set())
        if new_status not in allowed:
            raise ValueError(f"Invalid task transition: {old_status} -> {new_status}")
        if old_status in {"done", "rejected"} and new_status == "planned" and not reopen:
            raise ValueError("Terminal tasks require explicit reopen=true")
        if old_status == "waiting_for_approval" and new_status == "active":
            if not approval_id:
                raise ValueError("waiting_for_approval -> active requires consumed approval_id")
            approval = conn.execute(
                "SELECT id, status, task_id FROM approvals WHERE id = ?",
                (approval_id,),
            ).fetchone()
            if approval is None or approval["status"] != "consumed":
                raise ValueError("waiting_for_approval -> active requires a consumed approval")
            if approval["task_id"] and approval["task_id"] != task_id:
                raise ValueError("approval_id belongs to a different task")
        if new_status == "done" and (not result.strip() or not verification_note.strip()):
            raise ValueError("Done tasks require result and verification_note")
        if new_status == "blocked" and not blocked_reason.strip():
            raise ValueError("Blocked tasks require blocked_reason")
        if new_status == "rejected" and not review_note.strip():
            raise ValueError("Rejected tasks require review_note")
        if new_status == "waiting_for_approval":
            if not approval_id:
                raise ValueError("waiting_for_approval requires approval_id")
            approval = conn.execute(
                "SELECT id, status, task_id FROM approvals WHERE id = ?",
                (approval_id,),
            ).fetchone()
            if approval is None or approval["status"] != "pending":
                raise ValueError("waiting_for_approval requires a pending approval")
            if approval["task_id"] and approval["task_id"] != task_id:
                raise ValueError("approval_id belongs to a different task")
        if new_status == "waiting_for_secret":
            if not secret_key:
                raise ValueError("waiting_for_secret requires secret_key")
            secret = conn.execute("SELECT key FROM required_env WHERE key = ?", (secret_key,)).fetchone()
            if secret is None:
                raise ValueError("waiting_for_secret requires a registered secret key")

    def update_approval(
        self,
        approval_id: str,
        status: str,
        note: str,
        *,
        actor_type: str = "user",
        actor_id: str = "dashboard",
    ) -> None:
        if status == "deferred":
            status = "pending"
        if status not in {"approved", "rejected", "expired"}:
            raise ValueError("Invalid approval decision")
        _reject_secret_like_text("approval decision_note", note)
        self.initialize()
        timestamp = now_iso()
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT id, status, task_id, risk_level, risk_class, expected_change,
                       rollback_plan, failure_mode, plan_fingerprint
                FROM approvals
                WHERE id = ?
                """,
                (approval_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Unknown approval id")
            old_status = row["status"]
            if old_status in {"consumed", "expired"}:
                raise ValueError("Consumed or expired approvals cannot be decided")
            conn.execute(
                "UPDATE approvals SET status = ?, decided_at = ?, decision_note = ?, updated_at = ? WHERE id = ?",
                (status, timestamp, note, timestamp, approval_id),
            )
            self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="approval_decided",
                summary=f"Approval {approval_id} changed from {old_status} to {status}.",
                approval_id=approval_id,
                task_id=row["task_id"],
                risk_level=row["risk_level"] or "medium",
                evidence="dashboard approval decision API",
                redacted_payload={
                    "old_status": old_status,
                    "new_status": status,
                    "note_present": bool(note),
                    "risk_class": row["risk_class"],
                    "approval_state": "rejected" if status == "rejected" else status,
                    "expected_change": row["expected_change"],
                    "rollback_plan": row["rollback_plan"],
                    "failure_mode": row["failure_mode"],
                    "plan_fingerprint": row["plan_fingerprint"],
                    "retry_allowed_without_changed_plan": status != "rejected",
                },
                timestamp=timestamp,
            )
            if status == "rejected" and row["task_id"]:
                conn.execute(
                    "UPDATE tasks SET status = 'blocked', blocked_reason = ?, updated_at = ? WHERE id = ? AND status != 'rejected'",
                    (f"Approval {approval_id} rejected.", timestamp, row["task_id"]),
                )
                self.append_audit_event(
                    conn,
                    actor_type="system",
                    actor_id="approval-policy",
                    event_type="task_status_changed",
                    summary=f"Task {row['task_id']} blocked because approval {approval_id} was rejected.",
                    task_id=row["task_id"],
                    approval_id=approval_id,
                    risk_level="medium",
                    evidence="approval rejection policy",
                    redacted_payload={"new_status": "blocked"},
                    timestamp=timestamp,
                )

    def create_approval(
        self,
        *,
        task_id: str | None,
        action_type: str,
        summary: str,
        reason: str,
        affected_systems: str = "",
        permissions: str = "",
        external_effect: str = "",
        cost_estimate: str = "",
        risk_level: str = "medium",
        risk_class: str = "",
        expected_change: str = "",
        rollback_plan: str = "",
        failure_mode: str = "",
        requested_by: str = "orchestrator",
        actor_type: str = "system",
        actor_id: str = "orchestrator",
    ) -> str:
        summary = summary.strip()
        reason = reason.strip()
        if not summary or not reason:
            raise ValueError("Approval summary and reason are required")
        risk_class = risk_class.strip()
        if not risk_class:
            risk_class = _risk_class_from_level(risk_level)
            action_markers = f"{action_type} {external_effect}".lower()
            if any(marker in action_markers for marker in ("external_write", "install", "connect", "spend", "payment", "delete", "destructive")):
                risk_class = "R4"
        expected_change = expected_change.strip() or summary
        rollback_plan = rollback_plan.strip()
        failure_mode = failure_mode.strip() or "If this fails or is rejected, no action runs until a changed plan is reviewed."
        if risk_class in {"R3", "R4", "R5"} and not rollback_plan:
            raise ValueError("Risky approvals require rollback_plan before approval")
        for label, value in {
            "approval summary": summary,
            "approval reason": reason,
            "approval affected_systems": affected_systems,
            "approval permissions": permissions,
            "approval external_effect": external_effect,
            "approval cost_estimate": cost_estimate,
            "approval risk_class": risk_class,
            "approval expected_change": expected_change,
            "approval rollback_plan": rollback_plan,
            "approval failure_mode": failure_mode,
            "approval requested_by": requested_by,
        }.items():
            _reject_secret_like_text(label, value)
        self.initialize()
        timestamp = now_iso()
        plan_fingerprint = _approval_plan_fingerprint(
            action_type=action_type,
            summary=summary,
            reason=reason,
            affected_systems=affected_systems,
            permissions=permissions,
            external_effect=external_effect,
            cost_estimate=cost_estimate,
            risk_level=risk_level,
            risk_class=risk_class,
            expected_change=expected_change,
            rollback_plan=rollback_plan,
            failure_mode=failure_mode,
        )
        approval_id = slug_id("approval", summary)
        with self.connect() as conn:
            if task_id:
                task = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
                if task is None:
                    raise ValueError("Unknown task id for approval")
            rejected = conn.execute(
                """
                SELECT id FROM approvals
                WHERE status = 'rejected' AND plan_fingerprint = ?
                ORDER BY updated_at DESC, id
                LIMIT 1
                """,
                (plan_fingerprint,),
            ).fetchone()
            if rejected is not None:
                raise ValueError("Rejected high-risk approval plan cannot be retried without a changed plan")
            suffix = 2
            base_id = approval_id
            while conn.execute("SELECT 1 FROM approvals WHERE id = ?", (approval_id,)).fetchone():
                approval_id = f"{base_id}-{suffix}"
                suffix += 1
            conn.execute(
                """
                INSERT INTO approvals(
                  id, task_id, action_type, summary, reason, affected_systems,
                  permissions, external_effect, cost_estimate, risk_level,
                  risk_class, expected_change, rollback_plan, failure_mode,
                  plan_fingerprint, status, requested_by, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
                """,
                (
                    approval_id,
                    task_id,
                    action_type,
                    summary,
                    reason,
                    affected_systems,
                    permissions,
                    external_effect,
                    cost_estimate,
                    risk_level,
                    risk_class,
                    expected_change,
                    rollback_plan,
                    failure_mode,
                    plan_fingerprint,
                    requested_by,
                    timestamp,
                    timestamp,
                ),
            )
            self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="approval_created",
                task_id=task_id,
                approval_id=approval_id,
                risk_level=risk_level,
                summary=f"Approval created: {summary}",
                evidence="orchestration proposal apply",
                redacted_payload={
                    "approval_id": approval_id,
                    "action_type": action_type,
                    "external_effect": external_effect,
                    "risk_level": risk_level,
                    "risk_class": risk_class,
                    "expected_change": expected_change,
                    "rollback_plan": rollback_plan,
                    "failure_mode": failure_mode,
                    "approval_state": "pending",
                    "plan_fingerprint": plan_fingerprint,
                },
                timestamp=timestamp,
            )
        return approval_id

    def consume_approval(
        self,
        approval_id: str,
        *,
        evidence: str,
        actor_type: str = "system",
        actor_id: str = "control-plane",
    ) -> None:
        evidence = evidence.strip()
        if not evidence:
            raise ValueError("Approval consumption requires evidence")
        self.initialize()
        timestamp = now_iso()
        with self.connect() as conn:
            row = conn.execute("SELECT id, status, task_id FROM approvals WHERE id = ?", (approval_id,)).fetchone()
            if row is None:
                raise ValueError("Unknown approval id")
            if row["status"] != "approved":
                raise ValueError("Only approved approvals can be consumed")
            conn.execute(
                "UPDATE approvals SET status = 'consumed', consumed_at = ?, updated_at = ? WHERE id = ?",
                (timestamp, timestamp, approval_id),
            )
            self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="approval_consumed",
                summary=f"Approval {approval_id} consumed for one bounded action.",
                task_id=row["task_id"],
                approval_id=approval_id,
                risk_level="medium",
                evidence=evidence,
                redacted_payload={"new_status": "consumed"},
                timestamp=timestamp,
            )

    def continue_task_after_approval(
        self,
        approval_id: str,
        *,
        evidence: str,
        actor_type: str = "reviewer",
        actor_id: str = "dashboard",
    ) -> dict[str, str]:
        """Consume an approved gate and move its waiting task to active."""

        self.initialize()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id, status, task_id FROM approvals WHERE id = ?",
                (approval_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Unknown approval id")
            if row["status"] != "approved":
                raise ValueError("Only approved approvals can continue a task")
            task_id = str(row["task_id"] or "")
            if not task_id:
                raise ValueError("Approval is not attached to a task")
            task = conn.execute("SELECT id, status FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if task is None:
                raise ValueError("Unknown task id for approval")
            if task["status"] != "waiting_for_approval":
                raise ValueError("Approval continuation requires task status waiting_for_approval")

        self.consume_approval(approval_id, evidence=evidence, actor_type=actor_type, actor_id=actor_id)
        self.update_task_status(
            task_id,
            "active",
            approval_id=approval_id,
            actor_type=actor_type,
            actor_id=actor_id,
        )
        return {"task_id": task_id, "approval_id": approval_id}

    def record_secret_updated(self, key: str, actor_type: str = "user", actor_id: str = "dashboard") -> None:
        self.initialize()
        with self.connect() as conn:
            secret = conn.execute("SELECT key FROM required_env WHERE key = ?", (key,)).fetchone()
            if secret is None:
                raise ValueError("This env key is not registered in the control plane")
            self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="secret_updated",
                summary=f"Secret {key} was updated locally; value redacted by construction.",
                risk_level="medium",
                evidence=".env.local write completed",
                redacted_payload={"key": key, "destination": ".env.local", "present": True, "value_stored_in_audit": False},
            )

    def ensure_required_env(self, key: str, purpose: str) -> None:
        if not key or not purpose:
            raise ValueError("key and purpose are required")
        _reject_secret_like_text("required env purpose", purpose)
        self.initialize()
        timestamp = now_iso()
        with self.connect() as conn:
            existing = conn.execute("SELECT key FROM required_env WHERE key = ?", (key,)).fetchone()
            conn.execute(
                """
                INSERT INTO required_env(key, purpose, created_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET purpose = excluded.purpose
                """,
                (key, purpose, timestamp),
            )
            if existing is None:
                self.append_audit_event(
                    conn,
                    actor_type="system",
                    actor_id="env-registry",
                    event_type="secret_declared",
                    summary=f"Secret {key} registered in dashboard env registry.",
                    risk_level="medium",
                    evidence="control-plane env registry",
                    redacted_payload={"key": key, "purpose": purpose},
                    timestamp=timestamp,
                )

    def update_metadata(self, values: dict[str, Any]) -> None:
        self.initialize()
        with self.connect() as conn:
            for key, value in values.items():
                conn.execute(
                    """
                    INSERT INTO metadata(key, value) VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (key, json.dumps(_redact_audit_value(value), ensure_ascii=False)),
                )

    def _rollback_status_payload(self, record_id: str, *, status: str, kind: str, operations: list[str]) -> dict[str, Any]:
        return {
            "required": status != "not_applicable",
            "status": status,
            "record_id": record_id,
            "kind": kind,
            "operations": operations,
        }

    def _insert_rollback_record(
        self,
        conn: sqlite3.Connection,
        *,
        kind: str,
        status: str,
        risk_class: str,
        target_type: str,
        target_ref: str,
        operation: str,
        summary: str,
        task_id: str | None = None,
        approval_id: str | None = None,
        action_ref_type: str = "",
        action_ref_id: str = "",
        before_snapshot: dict[str, Any] | None = None,
        after_snapshot: dict[str, Any] | None = None,
        undo_payload: dict[str, Any] | None = None,
        patch_snapshot: str = "",
        test_results: dict[str, Any] | None = None,
        audit_details: dict[str, Any] | None = None,
        compensating_action: dict[str, Any] | None = None,
        deletion_supported: bool = False,
        undo_supported: bool = False,
        scrub_supported: bool = False,
        compensation_supported: bool = False,
        audit_event_id: str | None = None,
        timestamp: str | None = None,
    ) -> str:
        kind = str(kind or "").strip()
        status = str(status or "").strip()
        risk_class = str(risk_class or "").strip()
        target_type = redact_audit_text(str(target_type or "").strip())
        target_ref = redact_audit_text(str(target_ref or "").strip())
        operation = redact_audit_text(str(operation or "").strip())
        summary = redact_audit_text(str(summary or "").strip())
        if kind not in ROLLBACK_RECORD_KINDS:
            raise ValueError("invalid rollback record kind")
        if status not in ROLLBACK_STATUSES:
            raise ValueError("invalid rollback record status")
        if risk_class not in {"R1", "R2", "R3", "R4", "R5"}:
            raise ValueError("rollback records require risk_class R1-R5")
        if not target_type or not target_ref or not operation or not summary:
            raise ValueError("rollback records require target_type, target_ref, operation and summary")
        if kind == "cache" and not deletion_supported:
            raise ValueError("R1 cache rollback records must support deletion")
        if kind == "local_persistent" and not (before_snapshot is not None and after_snapshot is not None):
            raise ValueError("R2 local rollback records require before and after snapshots")
        if kind == "local_persistent" and not (undo_supported or deletion_supported or scrub_supported):
            raise ValueError("R2 local rollback records require undo, delete, or scrub support")
        if kind == "code_system" and (not patch_snapshot.strip() or not test_results):
            raise ValueError("R3 code/system rollback records require patch snapshot and test results")
        if kind == "external_write" and not audit_details:
            raise ValueError("R4 external write rollback records require audit details")

        timestamp = timestamp or now_iso()
        record_id = f"rollback-{uuid.uuid4().hex[:16]}"
        conn.execute(
            """
            INSERT INTO rollback_records(
              id, kind, status, risk_class, task_id, approval_id,
              action_ref_type, action_ref_id, target_type, target_ref,
              operation, summary, before_snapshot_json, after_snapshot_json,
              undo_payload_json, patch_snapshot, test_results_json,
              audit_details_json, compensating_action_json,
              deletion_supported, undo_supported, scrub_supported,
              compensation_supported, audit_event_id, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                kind,
                status,
                risk_class,
                task_id,
                approval_id,
                redact_audit_text(action_ref_type),
                redact_audit_text(action_ref_id),
                target_type,
                target_ref,
                operation,
                summary,
                _json_dumps(before_snapshot or {}),
                _json_dumps(after_snapshot or {}),
                _json_dumps(undo_payload or {}),
                redact_audit_text(patch_snapshot),
                _json_dumps(test_results or {}),
                _json_dumps(audit_details or {}),
                _json_dumps(compensating_action or {}),
                int(deletion_supported),
                int(undo_supported),
                int(scrub_supported),
                int(compensation_supported),
                audit_event_id,
                timestamp,
                timestamp,
            ),
        )
        return record_id

    def record_cache_work(
        self,
        *,
        cache_key: str,
        summary: str,
        delete_payload: dict[str, Any] | None = None,
        task_id: str | None = None,
        actor_type: str = "system",
        actor_id: str = "cache-registry",
    ) -> str:
        cache_key = str(cache_key or "").strip()
        if not cache_key:
            raise ValueError("cache_key is required")
        self.initialize()
        timestamp = now_iso()
        with self.connect() as conn:
            audit_event_id = self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="cache_work_recorded",
                task_id=task_id,
                risk_level="low",
                summary=f"Cache work recorded for {cache_key}.",
                evidence="local cache registry; cache entry remains delete-capable",
                redacted_payload={
                    "cache_key": cache_key,
                    "risk_class": "R1",
                    "rollback_status": {
                        "required": True,
                        "status": "delete_supported",
                        "kind": "cache",
                        "operations": ["delete"],
                    },
                },
                timestamp=timestamp,
            )
            return self._insert_rollback_record(
                conn,
                kind="cache",
                status="delete_supported",
                risk_class="R1",
                task_id=task_id,
                action_ref_type="audit_event",
                action_ref_id=audit_event_id,
                target_type="cache",
                target_ref=cache_key,
                operation="delete",
                summary=summary,
                undo_payload=delete_payload or {"delete_cache_key": cache_key},
                deletion_supported=True,
                audit_event_id=audit_event_id,
                timestamp=timestamp,
            )

    def record_code_change_rollback(
        self,
        *,
        target_ref: str,
        patch_snapshot: str,
        test_results: dict[str, Any],
        summary: str,
        task_id: str | None = None,
        action_ref_type: str = "code_change",
        action_ref_id: str = "",
        actor_type: str = "system",
        actor_id: str = "rollback-registry",
    ) -> str:
        self.initialize()
        timestamp = now_iso()
        with self.connect() as conn:
            audit_event_id = self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="code_change_rollback_recorded",
                task_id=task_id,
                risk_level="medium",
                summary=f"Code/system rollback snapshot recorded for {target_ref}.",
                evidence="rollback registry; patch snapshot and test results captured",
                redacted_payload={
                    "target_ref": target_ref,
                    "risk_class": "R3",
                    "test_results": test_results,
                    "rollback_status": {
                        "required": True,
                        "status": "prepared",
                        "kind": "code_system",
                        "operations": ["apply_patch"],
                    },
                },
                timestamp=timestamp,
            )
            return self._insert_rollback_record(
                conn,
                kind="code_system",
                status="prepared",
                risk_class="R3",
                task_id=task_id,
                action_ref_type=action_ref_type,
                action_ref_id=action_ref_id,
                target_type="code_system",
                target_ref=target_ref,
                operation="apply_patch",
                summary=summary,
                patch_snapshot=patch_snapshot,
                test_results=test_results,
                undo_supported=True,
                audit_event_id=audit_event_id,
                timestamp=timestamp,
            )

    def record_controlled_self_improvement(
        self,
        *,
        target_ref: str,
        patch_snapshot: str,
        test_results: dict[str, Any],
        summary: str,
        run_id: str = "",
        task_id: str | None = None,
        action_type: str = "modify_files",
        requested_scope: str = "project:file:self-improvement",
        diff_limited: bool = True,
        actor_type: str = "system",
        actor_id: str = "self-improvement-runner",
    ) -> dict[str, Any]:
        target_ref = str(target_ref or "").strip()
        patch_snapshot = str(patch_snapshot or "")
        summary = str(summary or "").strip()
        if not target_ref or not summary:
            raise ValueError("controlled self-improvement requires target_ref and summary")
        if not patch_snapshot.strip():
            raise ValueError("controlled self-improvement requires a diff or patch snapshot")
        if not isinstance(test_results, dict) or not test_results:
            raise ValueError("controlled self-improvement requires test results")
        passed = bool(test_results.get("passed"))
        if str(test_results.get("status") or "").strip().lower() in {"passed", "success", "succeeded"}:
            passed = True
        if not passed:
            raise ValueError("controlled self-improvement requires passing post-change tests")
        test_phase = str(test_results.get("phase") or "").strip().lower().replace("-", "_")
        tests_ran_after_change = test_phase in {"post_change", "after_change"} or bool(test_results.get("ran_after_change"))
        if not tests_ran_after_change:
            raise ValueError("controlled self-improvement tests must run after local changes")

        policy = evaluate_action_policy(
            action_type=action_type,
            requested_scope=requested_scope,
            metadata={
                "diff_limited": bool(diff_limited),
                "tests_passed": passed,
                "self_improvement": True,
            },
        )
        if policy["risk_class"] != "R3":
            raise ValueError("controlled self-improvement must classify as R3")
        if not policy["execution_allowed"]:
            raise ValueError(f"controlled self-improvement blocked by policy: {policy['reason']}")

        rollback_record_id = self.record_code_change_rollback(
            target_ref=target_ref,
            patch_snapshot=patch_snapshot,
            test_results=test_results,
            summary=summary,
            task_id=task_id,
            action_ref_type="night_queue_run" if run_id else "self_improvement",
            action_ref_id=run_id,
            actor_type=actor_type,
            actor_id=actor_id,
        )
        return _redact_audit_value({
            "type": "self_improvement",
            "id": rollback_record_id,
            "target_ref": target_ref,
            "summary": summary,
            "risk_class": "R3",
            "policy": policy,
            "diff": patch_snapshot,
            "patch_snapshot": patch_snapshot,
            "diff_limited": bool(diff_limited),
            "tests_ran_after_change": tests_ran_after_change,
            "test_results": test_results,
            "rollback_record_id": rollback_record_id,
            "rollback": "patch_snapshot_and_tests_recorded",
            "rollback_snapshot": {
                "rollback_record_id": rollback_record_id,
                "kind": "code_system",
                "operation": "apply_patch",
                "patch_snapshot": patch_snapshot,
                "test_results": test_results,
            },
        })

    def record_external_write_rollback(
        self,
        *,
        target_ref: str,
        audit_details: dict[str, Any],
        summary: str,
        compensating_action: dict[str, Any] | None = None,
        task_id: str | None = None,
        approval_id: str | None = None,
        action_ref_type: str = "external_write",
        action_ref_id: str = "",
        actor_type: str = "system",
        actor_id: str = "rollback-registry",
    ) -> str:
        self.initialize()
        timestamp = now_iso()
        compensation_supported = bool(compensating_action)
        status = "compensation_available" if compensation_supported else "compensation_unavailable"
        with self.connect() as conn:
            audit_event_id = self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="external_write_rollback_recorded",
                task_id=task_id,
                approval_id=approval_id,
                risk_level="high",
                summary=f"External write rollback details recorded for {target_ref}.",
                evidence="rollback registry; external audit details and compensation state captured",
                redacted_payload={
                    "target_ref": target_ref,
                    "risk_class": "R4",
                    "compensation_supported": compensation_supported,
                    "rollback_status": {
                        "required": True,
                        "status": status,
                        "kind": "external_write",
                        "operations": ["compensate"] if compensation_supported else [],
                    },
                },
                timestamp=timestamp,
            )
            return self._insert_rollback_record(
                conn,
                kind="external_write",
                status=status,
                risk_class="R4",
                task_id=task_id,
                approval_id=approval_id,
                action_ref_type=action_ref_type,
                action_ref_id=action_ref_id,
                target_type="external_system",
                target_ref=target_ref,
                operation="compensate" if compensation_supported else "manual_followup",
                summary=summary,
                audit_details=audit_details,
                compensating_action=compensating_action or {},
                compensation_supported=compensation_supported,
                audit_event_id=audit_event_id,
                timestamp=timestamp,
            )

    def get_task(self, task_id: str) -> dict[str, Any]:
        self.initialize()
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT id, title, goal, phase_id, owner, status, priority, risk_level,
                       value_score, source_refs_json, parent_task_id, approval_required,
                       acceptance_criteria, blocked_reason, result, verification_note,
                       review_note, created_at, updated_at, done_at
                FROM tasks
                WHERE id = ?
                """,
                (task_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Unknown task id")
            task = dict(row)
            task["risk"] = task["risk_level"]
            task["acceptance"] = task["acceptance_criteria"]
            try:
                task["source_refs"] = json.loads(task.get("source_refs_json") or "[]")
            except json.JSONDecodeError:
                task["source_refs"] = []
            return task

    def get_agent_assignment_proposal(self, proposal_id: str) -> dict[str, Any]:
        self.initialize()
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT id, task_id, status, agent_role, runner_kind, execution_mode,
                       execution_allowed, external_calls_made, external_calls_allowed,
                       secret_values_read, shell_commands_allowed, file_writes_allowed,
                       task_type, complexity, risk, privacy, budget_mode,
                       provider, route, model, reasoning_effort, route_reason,
                       task_packet_json, allowed_actions_json, forbidden_actions_json,
                       proposal_json, applied_agent_run_id, review_note, audit_event_id,
                       created_at, updated_at, applied_at
                FROM agent_assignment_proposals
                WHERE id = ?
                """,
                (proposal_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Unknown agent assignment proposal id")
            return dict(row)

    def create_provider_dry_run(
        self,
        dry_run: dict[str, Any],
        *,
        actor_type: str = "system",
        actor_id: str = "provider-adapter-dry-run",
    ) -> str:
        self.initialize()
        task_id = str(dry_run.get("task_id") or "").strip()
        if not task_id:
            raise ValueError("Provider dry-run requires task_id")
        if dry_run.get("execution_allowed") is not False:
            raise ValueError("Provider dry-run must not allow execution")
        for key in [
            "provider_calls_made",
            "dependency_installed",
            "sdk_imported",
            "secret_values_read",
            "approval_consumed",
            "shell_commands_allowed",
            "file_writes_allowed",
        ]:
            if bool(dry_run.get(key)):
                raise ValueError(f"Unsafe provider dry-run: {key} must be false")
        dry_run = _redact_audit_value(dry_run)
        serialized = json.dumps(dry_run, ensure_ascii=False, sort_keys=True)
        if contains_secret(dry_run):
            raise ValueError("Provider dry-run payload appears to contain a secret value")

        timestamp = now_iso()
        dry_run_id = f"provider-dry-run-{uuid.uuid4().hex[:16]}"
        assignment_id = str(dry_run.get("assignment_proposal_id") or "").strip() or None
        with self.connect() as conn:
            if conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone() is None:
                raise ValueError("Unknown task id")
            if assignment_id and conn.execute(
                "SELECT id FROM agent_assignment_proposals WHERE id = ?",
                (assignment_id,),
            ).fetchone() is None:
                raise ValueError("Unknown agent assignment proposal id")
            audit_event_id = self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="provider_adapter_dry_run_created",
                task_id=task_id,
                risk_level="low",
                summary=f"Provider adapter dry-run {dry_run_id} created for {dry_run.get('provider_id')}.",
                evidence="local provider adapter dry-run; no SDK import, install, provider call or secret value read",
                redacted_payload={
                    "provider_dry_run_id": dry_run_id,
                    "task_id": task_id,
                    "agent_assignment_proposal_id": assignment_id,
                    "provider_id": dry_run.get("provider_id"),
                    "status": dry_run.get("status"),
                    "required_env_keys": dry_run.get("required_env_keys") or [],
                    "missing_env_keys": dry_run.get("missing_env_keys") or [],
                    "execution_allowed": False,
                    "provider_calls_made": False,
                    "dependency_installed": False,
                    "secret_values_read": False,
                },
                timestamp=timestamp,
            )
            conn.execute(
                """
                INSERT INTO provider_dry_runs(
                  id, task_id, agent_assignment_proposal_id, provider_id,
                  adapter_id, status, decision, execution_allowed,
                  provider_calls_made, dependency_installed, sdk_imported,
                  secret_values_read, approval_consumed,
                  shell_commands_allowed, file_writes_allowed,
                  required_env_keys_json, missing_env_keys_json,
                  dry_run_json, audit_event_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dry_run_id,
                    task_id,
                    assignment_id,
                    str(dry_run.get("provider_id") or ""),
                    str(dry_run.get("adapter_id") or ""),
                    str(dry_run.get("status") or ""),
                    str(dry_run.get("decision") or ""),
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    json.dumps(dry_run.get("required_env_keys") or [], ensure_ascii=False, sort_keys=True),
                    json.dumps(dry_run.get("missing_env_keys") or [], ensure_ascii=False, sort_keys=True),
                    serialized,
                    audit_event_id,
                    timestamp,
                ),
            )
        return dry_run_id

    def create_agent_assignment_proposal(
        self,
        proposal: dict[str, Any],
        *,
        actor_type: str = "system",
        actor_id: str = "agent-assignment-gate",
    ) -> str:
        self.initialize()
        timestamp = now_iso()
        proposal_id = f"agent-assignment-{uuid.uuid4().hex[:16]}"
        proposal = _redact_audit_value(proposal)
        model_route = proposal.get("model_route") or {}
        task_id = str(proposal.get("task_id") or "")
        if not task_id:
            raise ValueError("Agent assignment proposal requires task_id")
        if proposal.get("runner_kind") != "local_mock":
            raise ValueError("Only local_mock runner assignments are supported")
        if proposal.get("external_calls_allowed") or proposal.get("secret_values_read"):
            raise ValueError("Unsafe assignment proposal: external calls or secret reads are not allowed")
        with self.connect() as conn:
            task = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if task is None:
                raise ValueError("Unknown task id")
            audit_event_id = self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="agent_assignment_proposed",
                task_id=task_id,
                risk_level=str(proposal.get("risk") or "medium"),
                summary=f"Agent assignment proposal {proposal_id} prepared for task {task_id}.",
                evidence="local agent assignment gate",
                redacted_payload={
                    "agent_assignment_proposal_id": proposal_id,
                    "task_id": task_id,
                    "agent_role": proposal.get("agent_role"),
                    "runner_kind": proposal.get("runner_kind"),
                    "execution_mode": proposal.get("execution_mode"),
                    "route": model_route.get("route"),
                    "model": model_route.get("model"),
                    "external_calls_allowed": bool(proposal.get("external_calls_allowed")),
                    "secret_values_read": bool(proposal.get("secret_values_read")),
                },
                timestamp=timestamp,
            )
            conn.execute(
                """
                INSERT INTO agent_assignment_proposals(
                  id, task_id, status, agent_role, runner_kind, execution_mode,
                  execution_allowed, external_calls_made, external_calls_allowed,
                  secret_values_read, shell_commands_allowed, file_writes_allowed,
                  task_type, complexity, risk, privacy, budget_mode,
                  provider, route, model, reasoning_effort, route_reason,
                  task_packet_json, allowed_actions_json, forbidden_actions_json,
                  proposal_json, audit_event_id, created_at, updated_at
                )
                VALUES (?, ?, 'prepared', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal_id,
                    task_id,
                    str(proposal.get("agent_role") or ""),
                    str(proposal.get("runner_kind") or ""),
                    str(proposal.get("execution_mode") or ""),
                    int(bool(proposal.get("execution_allowed", False))),
                    int(bool(proposal.get("external_calls_made", False))),
                    int(bool(proposal.get("external_calls_allowed", False))),
                    int(bool(proposal.get("secret_values_read", False))),
                    int(bool(proposal.get("shell_commands_allowed", False))),
                    int(bool(proposal.get("file_writes_allowed", False))),
                    str(proposal.get("task_type") or ""),
                    str(proposal.get("complexity") or ""),
                    str(proposal.get("risk") or ""),
                    str(proposal.get("privacy") or ""),
                    str(proposal.get("budget_mode") or ""),
                    str(model_route.get("provider") or ""),
                    str(model_route.get("route") or ""),
                    str(model_route.get("model") or ""),
                    str(model_route.get("reasoning_effort") or ""),
                    str(model_route.get("reason") or ""),
                    json.dumps(proposal.get("task_packet") or {}, ensure_ascii=False, sort_keys=True),
                    json.dumps(proposal.get("allowed_actions") or [], ensure_ascii=False),
                    json.dumps(proposal.get("forbidden_actions") or [], ensure_ascii=False),
                    json.dumps(proposal, ensure_ascii=False, sort_keys=True),
                    audit_event_id,
                    timestamp,
                    timestamp,
                ),
            )
        return proposal_id

    def reject_agent_assignment_proposal(
        self,
        proposal_id: str,
        *,
        review_note: str,
        actor_type: str = "reviewer",
        actor_id: str = "dashboard",
    ) -> None:
        if not review_note.strip():
            raise ValueError("Rejecting an agent assignment proposal requires review_note")
        _reject_secret_like_text("agent assignment review_note", review_note)
        self.initialize()
        timestamp = now_iso()
        with self.connect() as conn:
            row = conn.execute("SELECT id, task_id, status FROM agent_assignment_proposals WHERE id = ?", (proposal_id,)).fetchone()
            if row is None:
                raise ValueError("Unknown agent assignment proposal id")
            if row["status"] != "prepared":
                raise ValueError("Only prepared agent assignment proposals can be rejected")
            conn.execute(
                """
                UPDATE agent_assignment_proposals
                SET status = 'rejected', review_note = ?, updated_at = ?
                WHERE id = ?
                """,
                (review_note, timestamp, proposal_id),
            )
            self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="agent_assignment_rejected",
                task_id=row["task_id"],
                risk_level="low",
                summary=f"Agent assignment proposal {proposal_id} rejected.",
                evidence="dashboard agent assignment review",
                redacted_payload={
                    "agent_assignment_proposal_id": proposal_id,
                    "old_status": "prepared",
                    "new_status": "rejected",
                    "review_note_present": True,
                },
                timestamp=timestamp,
            )

    def apply_agent_assignment_proposal(
        self,
        proposal_id: str,
        *,
        review_note: str,
        actor_type: str = "reviewer",
        actor_id: str = "dashboard",
    ) -> dict[str, str]:
        if not review_note.strip():
            raise ValueError("Applying an agent assignment proposal requires review_note")
        _reject_secret_like_text("agent assignment review_note", review_note)
        self.initialize()
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT id, task_id, status, proposal_json
                FROM agent_assignment_proposals
                WHERE id = ?
                """,
                (proposal_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Unknown agent assignment proposal id")
            if row["status"] != "prepared":
                raise ValueError("Only prepared agent assignment proposals can be applied")
            task = conn.execute("SELECT id, status FROM tasks WHERE id = ?", (row["task_id"],)).fetchone()
            if task is None:
                raise ValueError("Unknown task id")
            if task["status"] in {"done", "rejected"}:
                raise ValueError("Terminal tasks cannot be assigned to agents")
            proposal = json.loads(row["proposal_json"])

        if proposal.get("runner_kind") != "local_mock":
            raise ValueError("Only local_mock assignments can be applied")
        if proposal.get("external_calls_allowed") or proposal.get("secret_values_read"):
            raise ValueError("Unsafe assignment proposal cannot be applied")

        model_route = proposal.get("model_route") or {}
        run_id = self.create_agent_run(
            task_id=str(proposal["task_id"]),
            agent_role=str(proposal.get("agent_role") or "Mock Builder Agent"),
            task_type=str(proposal.get("task_type") or "documentation"),
            complexity=str(proposal.get("complexity") or "medium"),
            risk=str(proposal.get("risk") or "medium"),
            privacy=str(proposal.get("privacy") or "normal"),
            budget_mode=str(proposal.get("budget_mode") or "balanced"),
            model_route=model_route,
            task_packet=proposal.get("task_packet") or {},
            allowed_actions=list(proposal.get("allowed_actions") or []),
            forbidden_actions=list(proposal.get("forbidden_actions") or []),
            actor_type="system",
            actor_id="agent-assignment-gate",
        )
        result_summary = (
            f"Local mock assignment for task '{proposal.get('task_title')}' created a reviewable agent run "
            f"using route {model_route.get('route')} / {model_route.get('model')}. "
            "No external calls, shell commands, file writes, account connections, GPU jobs, or secret reads were performed."
        )
        evidence = [
            {
                "type": "assignment_gate",
                "summary": "Agent run was started from an explicitly applied assignment proposal.",
                "agent_assignment_proposal_id": proposal_id,
            },
            {
                "type": "safety",
                "summary": "Runner kind is local_mock with external calls, shell commands, file writes, and secret reads disabled.",
            },
            {
                "type": "model_route",
                "summary": model_route.get("reason", ""),
                "route": model_route.get("route"),
                "model": model_route.get("model"),
            },
        ]
        self.complete_agent_run(run_id, result_summary=result_summary, evidence=evidence)

        timestamp = now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE agent_assignment_proposals
                SET status = 'applied', applied_agent_run_id = ?,
                    review_note = ?, updated_at = ?, applied_at = ?
                WHERE id = ?
                """,
                (run_id, review_note, timestamp, timestamp, proposal_id),
            )
            self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="agent_assignment_applied",
                task_id=str(proposal["task_id"]),
                risk_level=str(proposal.get("risk") or "medium"),
                summary=f"Agent assignment proposal {proposal_id} applied to local mock run {run_id}.",
                evidence="dashboard agent assignment review",
                redacted_payload={
                    "agent_assignment_proposal_id": proposal_id,
                    "agent_run_id": run_id,
                    "old_status": "prepared",
                    "new_status": "applied",
                    "runner_kind": proposal.get("runner_kind"),
                    "execution_mode": proposal.get("execution_mode"),
                    "external_calls_made": False,
                    "secret_values_read": False,
                    "review_note_present": True,
                },
                timestamp=timestamp,
            )
        return {"agent_run_id": run_id}

    def create_agent_run(
        self,
        *,
        task_id: str,
        agent_role: str,
        task_type: str,
        complexity: str,
        risk: str,
        privacy: str,
        budget_mode: str,
        model_route: dict[str, Any],
        task_packet: dict[str, Any],
        allowed_actions: list[str],
        forbidden_actions: list[str],
        actor_type: str = "system",
        actor_id: str = "agent-runtime",
    ) -> str:
        self.initialize()
        timestamp = now_iso()
        run_id = f"agent-run-{uuid.uuid4().hex[:16]}"
        task_packet = _redact_audit_value(task_packet)
        allowed_actions = _redact_audit_value(allowed_actions)
        forbidden_actions = _redact_audit_value(forbidden_actions)
        model_route = _redact_audit_value(model_route)
        role = normalize_agent_run_role(agent_role)
        gate = evaluate_action_policy(
            action_type="local_mock_agent_run",
            requested_scope="local_mock_agent_run",
            metadata={
                "allowed_actions": allowed_actions,
                "forbidden_actions": forbidden_actions,
                "runner_kind": "local_mock",
            },
        )
        if not gate["execution_allowed"]:
            raise ValueError(f"Agent run blocked by policy gate: {gate['reason']}")
        task_packet_risk = task_packet.get("risk_policy") if isinstance(task_packet, dict) else {}
        if not isinstance(task_packet_risk, dict):
            task_packet_risk = {}
        risk_assessment = {
            **gate,
            "policy_gate": "store.create_agent_run",
            "review_agent_required_before_execution": bool(gate.get("requires_review") or gate.get("approval_required") or gate.get("hard_blocked")),
            "task_packet_policy": task_packet_risk,
        }
        cost_estimate = estimate_agent_run_cost(model_route=model_route, external_calls_made=False)
        input_sources = list(task_packet.get("source_refs") or []) if isinstance(task_packet, dict) else []
        output = {
            "status": "running",
            "summary": "",
            "evidence": [],
        }
        reviewer_result = {
            "status": "pending",
            "reviewer_role": "Review",
            "review_note": "",
            "reviewed_at": None,
        }
        with self.connect() as conn:
            task = conn.execute(
                """
                SELECT id, title, goal, status, priority, risk_level, source_refs_json
                FROM tasks
                WHERE id = ?
                """,
                (task_id,),
            ).fetchone()
            if task is None:
                raise ValueError("Unknown task id")
            task_record = dict(task)
            task_record["source_refs"] = _json_loads(task_record.pop("source_refs_json", "[]"), [])
            if not input_sources:
                input_sources = list(task_record.get("source_refs") or [])
            conn.execute(
                """
                INSERT INTO agent_runs(
                  id, task_id, agent_role, role, status, task_type, complexity, risk,
                  privacy, budget_mode, provider, route, model, reasoning_effort,
                  route_reason, model_route_json, approval_required, task_json,
                  task_packet_json, input_sources_json, allowed_actions_json,
                  forbidden_actions_json, output_json, confidence, cost_estimate_json,
                  risk_assessment_json, reviewer_result_json, rollback_status_json, next_action,
                  created_at, updated_at, started_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    task_id,
                    agent_role,
                    role,
                    "running",
                    task_type,
                    complexity,
                    risk,
                    privacy,
                    budget_mode,
                    str(model_route["provider"]),
                    str(model_route["route"]),
                    str(model_route["model"]),
                    str(model_route["reasoning_effort"]),
                    str(model_route["reason"]),
                    _json_dumps(model_route),
                    int(bool(model_route.get("approval_required", False))),
                    _json_dumps(task_record),
                    _json_dumps(task_packet),
                    _json_dumps(input_sources),
                    _json_dumps(allowed_actions),
                    _json_dumps(forbidden_actions),
                    _json_dumps(output),
                    0.0,
                    _json_dumps(cost_estimate),
                    _json_dumps(risk_assessment),
                    _json_dumps(reviewer_result),
                    _json_dumps({}),
                    "complete_agent_run",
                    timestamp,
                    timestamp,
                    timestamp,
                ),
            )
            start_audit_event_id = self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="agent_run_started",
                task_id=task_id,
                risk_level=risk,
                summary=f"Agent run {run_id} started for task {task_id}.",
                evidence="mock/local agent runtime adapter",
                redacted_payload={
                    "agent_run_id": run_id,
                    "agent_role": agent_role,
                    "role": role,
                    "route": model_route["route"],
                    "model": model_route["model"],
                    "status": "running",
                    "risk_policy": risk_assessment,
                    "cost_estimate": cost_estimate,
                    "confidence": 0.0,
                    "next_action": "complete_agent_run",
                    "allowed_actions": allowed_actions,
                    "forbidden_actions": forbidden_actions,
                    "source_refs": input_sources,
                },
                timestamp=timestamp,
            )
            rollback_record_id = self._insert_rollback_record(
                conn,
                kind="cache",
                status="delete_supported",
                risk_class="R1",
                task_id=task_id,
                action_ref_type="agent_run",
                action_ref_id=run_id,
                target_type="agent_run_task_packet",
                target_ref=run_id,
                operation="delete",
                summary="Local mock run stores only temporary task packet/output state and can be deleted with the run record.",
                undo_payload={"delete_agent_run_id": run_id},
                deletion_supported=True,
                audit_event_id=start_audit_event_id,
                timestamp=timestamp,
            )
            rollback_status = self._rollback_status_payload(
                rollback_record_id,
                status="delete_supported",
                kind="cache",
                operations=["delete"],
            )
            conn.execute(
                "UPDATE agent_runs SET rollback_status_json = ? WHERE id = ?",
                (_json_dumps(rollback_status), run_id),
            )
        return run_id

    def complete_agent_run(
        self,
        run_id: str,
        *,
        result_summary: str,
        evidence: list[dict[str, Any]],
        status: str = "waiting_for_review",
        recovery_suggestions: list[dict[str, Any]] | None = None,
        actor_type: str = "system",
        actor_id: str = "agent-runtime",
    ) -> None:
        if status not in {"waiting_for_review", "failed"}:
            raise ValueError("Agent run completion status must be waiting_for_review or failed")
        result_summary = redact_audit_text(result_summary)
        evidence = _redact_audit_value(evidence)
        self.initialize()
        timestamp = now_iso()
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT id, task_id, status, risk, model, agent_role, task_packet_json,
                       risk_assessment_json, rollback_status_json, started_at
                FROM agent_runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Unknown agent run id")
            try:
                task_packet = json.loads(row["task_packet_json"] or "{}")
            except json.JSONDecodeError:
                task_packet = {}
            risk_assessment = _json_loads(row["risk_assessment_json"], {})
            rollback_status = _json_loads(row["rollback_status_json"], {})
            confidence = 0.72 if status == "waiting_for_review" else 0.2
            normalized_recovery_suggestions: list[dict[str, str]] = []
            if status == "failed":
                normalized_recovery_suggestions = _normalize_recovery_suggestions(
                    recovery_suggestions,
                    fallback_reason=result_summary,
                )
            output = {
                "status": status,
                "summary": result_summary,
                "evidence": evidence,
                "confidence": confidence,
                "partial_failure_visible": status == "failed",
                "recovery_suggestions": normalized_recovery_suggestions,
            }
            conn.execute(
                """
                UPDATE agent_runs
                SET status = ?, result_summary = ?, evidence_json = ?, output_json = ?,
                    confidence = ?, recovery_suggestions_json = ?, next_action = ?,
                    updated_at = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    result_summary,
                    _json_dumps(evidence),
                    _json_dumps(output),
                    confidence,
                    _json_dumps(normalized_recovery_suggestions),
                    "review_agent_run",
                    timestamp,
                    timestamp,
                    run_id,
                ),
            )
            self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="agent_run_completed",
                task_id=row["task_id"],
                risk_level=row["risk"],
                summary=f"Agent run {run_id} completed with status {status}.",
                evidence="mock/local agent runtime adapter",
                redacted_payload={
                    "agent_run_id": run_id,
                    "agent_role": row["agent_role"],
                    "model": row["model"],
                    "old_status": row["status"],
                    "new_status": status,
                    "result": status,
                    "result_summary": result_summary,
                    "output": output,
                    "confidence": confidence,
                    "risk_policy": risk_assessment,
                    "rollback_status": rollback_status,
                    "partial_failure_visible": status == "failed",
                    "recovery_suggestions": normalized_recovery_suggestions,
                    "next_action": "review_agent_run",
                    "evidence_count": len(evidence),
                    "source_refs": task_packet.get("source_refs") or [],
                    "started_at": row["started_at"],
                    "completed_at": timestamp,
                },
                timestamp=timestamp,
            )

    def record_routing_decision(
        self,
        decision: dict[str, Any],
        *,
        actor_type: str = "system",
        actor_id: str = "decision-layer",
    ) -> str:
        self.initialize()
        timestamp = now_iso()
        decision_id = f"routing-{uuid.uuid4().hex[:16]}"
        model_route = decision.get("model_route") or {}
        redacted_decision = _redact_audit_value(json.loads(json.dumps(decision, ensure_ascii=False)))
        initial_outcome = {
            "status": "recorded",
            "summary": "Decision recorded; no orchestration proposal has been created yet.",
            "orchestration_proposal_ids": [],
            "task_ids": [],
            "approval_ids": [],
        }
        if isinstance(redacted_decision, dict):
            redacted_decision["outcome"] = initial_outcome
        with self.connect() as conn:
            audit_event_id = self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="routing_decided",
                risk_level=str(decision.get("risk_level") or "low"),
                summary=f"Routing decision {decision_id}: {decision.get('route')}.",
                evidence="local deterministic decision layer",
                redacted_payload={
                    "routing_decision_id": decision_id,
                    "input_text_redacted": decision.get("input_text_redacted", ""),
                    "route": decision.get("route"),
                    "intent": decision.get("intent"),
                    "risk_level": decision.get("risk_level"),
                    "risk_class": decision.get("risk_class"),
                    "policy_decision": decision.get("policy_decision"),
                    "risk_rationale": (decision.get("risk_policy") or {}).get("risk_rationale")
                    or (decision.get("risk_policy") or {}).get("reason")
                    or decision.get("approval_reason")
                    or "",
                    "risk_examples": (decision.get("risk_policy") or {}).get("examples", []),
                    "approval_state": (decision.get("risk_policy") or {}).get("approval_state", ""),
                    "approval_first_required": bool((decision.get("risk_policy") or {}).get("approval_first_required", False)),
                    "urgency": decision.get("urgency"),
                    "value_score": decision.get("value_score"),
                    "value_score_inputs": decision.get("value_score_inputs", {}),
                    "value_band": decision.get("value_band", {}),
                    "retrieved_context": decision.get("retrieved_context", {}),
                    "execution_path": decision.get("execution_path", {}),
                    "outcome": initial_outcome,
                    "recommended_task_status": decision.get("recommended_task_status"),
                    "approval_required": bool(decision.get("approval_required")),
                    "clarification_required": bool(decision.get("clarification_required")),
                    "clarification_questions": decision.get("clarification_questions", []),
                    "required_tools": decision.get("required_tools", []),
                    "expected_output": decision.get("expected_output", {}),
                    "risk_policy": decision.get("risk_policy", {}),
                    "model_route": model_route.get("route"),
                    "model": model_route.get("model"),
                    "matched_signals": decision.get("matched_signals", []),
                },
                timestamp=timestamp,
            )
            conn.execute(
                """
                INSERT INTO routing_decisions(
                  id, created_at, input_text_redacted, route, intent, confidence,
                  complexity, risk_level, privacy_level, urgency, value_score,
                  requires_sources, requires_tool, external_effect, approval_required,
                  approval_reason, recommended_task_status, provider, model_route,
                  model, model_reason, decision_json, audit_event_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision_id,
                    timestamp,
                    redact_audit_text(str(decision.get("input_text_redacted", ""))),
                    str(decision.get("route", "")),
                    str(decision.get("intent", "")),
                    float(decision.get("confidence", 0.0)),
                    str(decision.get("complexity", "")),
                    str(decision.get("risk_level", "")),
                    str(decision.get("privacy_level", "")),
                    str(decision.get("urgency", "")),
                    int(decision.get("value_score", 0)),
                    int(bool(decision.get("needs_sources", False))),
                    int(bool(decision.get("requires_tool", False))),
                    str(decision.get("external_effect", "")),
                    int(bool(decision.get("approval_required", False))),
                    str(decision.get("approval_reason", "")),
                    str(decision.get("recommended_task_status", "")),
                    str(model_route.get("provider", "")),
                    str(model_route.get("route", "")),
                    str(model_route.get("model", "")),
                    str(model_route.get("reason", "")),
                    json.dumps(redacted_decision, ensure_ascii=False, sort_keys=True),
                    audit_event_id,
                ),
            )
        return decision_id

    def get_routing_decision(self, decision_id: str) -> dict[str, Any]:
        self.initialize()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT decision_json FROM routing_decisions WHERE id = ?",
                (decision_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Unknown routing decision id")
            decision = json.loads(row["decision_json"])
            decision["id"] = decision_id
            return decision

    def record_decision_feedback(
        self,
        routing_decision_id: str,
        feedback_type: str,
        *,
        note: str = "",
        actor_type: str = "user",
        actor_id: str = "dashboard",
    ) -> str:
        self.initialize()
        routing_decision_id = str(routing_decision_id or "").strip()
        feedback_type = str(feedback_type or "").strip().lower().replace("-", "_")
        if feedback_type not in DECISION_FEEDBACK_TYPES:
            raise ValueError("decision feedback must be one of useful, wrong, risky, low_value")
        _reject_secret_like_text("decision feedback note", note)
        timestamp = now_iso()
        feedback_id = f"decision-feedback-{uuid.uuid4().hex[:16]}"
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id, route, risk_level, value_score FROM routing_decisions WHERE id = ?",
                (routing_decision_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Unknown routing decision id")
            audit_event_id = self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="routing_decision_feedback_recorded",
                risk_level=str(row["risk_level"] or "low"),
                summary=f"Feedback marked routing decision {routing_decision_id} as {feedback_type}.",
                evidence="dashboard decision feedback",
                redacted_payload={
                    "feedback_id": feedback_id,
                    "routing_decision_id": routing_decision_id,
                    "feedback_type": feedback_type,
                    "route": row["route"],
                    "value_score": row["value_score"],
                    "note_present": bool(note.strip()),
                },
                timestamp=timestamp,
            )
            conn.execute(
                """
                INSERT INTO decision_feedback(
                  id, routing_decision_id, feedback_type, note,
                  actor_type, actor_id, audit_event_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feedback_id,
                    routing_decision_id,
                    feedback_type,
                    redact_audit_text(note),
                    actor_type,
                    actor_id,
                    audit_event_id,
                    timestamp,
                ),
            )
        return feedback_id

    def promote_routing_failure_to_eval_case(
        self,
        routing_decision_id: str,
        expected_route: str,
        *,
        source_feedback_id: str | None = None,
        reason: str = "",
        actor_type: str = "user",
        actor_id: str = "dashboard",
    ) -> str:
        self.initialize()
        routing_decision_id = str(routing_decision_id or "").strip()
        expected_route = str(expected_route or "").strip()
        source_feedback_id = str(source_feedback_id or "").strip() or None
        raw_reason = str(reason or "").strip()
        if expected_route not in ROUTING_EVAL_ROUTES:
            raise ValueError("expected_route is not a known routing eval route")
        _reject_secret_like_text("routing eval case reason", raw_reason)
        reason = redact_audit_text(raw_reason)
        timestamp = now_iso()
        eval_case_id = f"routing-eval-case-{uuid.uuid4().hex[:16]}"
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT id, input_text_redacted, route, risk_level, value_score,
                       decision_json, audit_event_id
                FROM routing_decisions
                WHERE id = ?
                """,
                (routing_decision_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Unknown routing decision id")
            actual_route = str(row["route"] or "")
            if actual_route == expected_route:
                raise ValueError("expected_route must differ from the recorded route for a failure eval case")
            if source_feedback_id:
                feedback_row = conn.execute(
                    """
                    SELECT id FROM decision_feedback
                    WHERE id = ? AND routing_decision_id = ?
                    """,
                    (source_feedback_id, routing_decision_id),
                ).fetchone()
                if feedback_row is None:
                    raise ValueError("source_feedback_id must belong to the routing decision")
            failure_type = (
                "safety_regression"
                if expected_route in {"approval_required", "refuse_redirect"} and actual_route not in {"approval_required", "refuse_redirect"}
                else "routing_quality_regression"
            )
            case = {
                "id": eval_case_id,
                "input": row["input_text_redacted"],
                "expected_route": expected_route,
                "source": "feedback_regression",
                "misroute_note": reason or f"Feedback promoted recorded {actual_route} route into a regression case.",
                "routing_decision_id": routing_decision_id,
                "source_feedback_id": source_feedback_id or "",
                "actual_route_before": actual_route,
                "failure_type": failure_type,
            }
            audit_event_id = self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="routing_failure_promoted_to_eval_case",
                risk_level=str(row["risk_level"] or "medium"),
                summary=f"Routing failure {routing_decision_id} promoted to eval case {eval_case_id}.",
                evidence="feedback promoted to routing eval",
                redacted_payload={
                    "eval_case_id": eval_case_id,
                    "routing_decision_id": routing_decision_id,
                    "source_feedback_id": source_feedback_id,
                    "expected_route": expected_route,
                    "actual_route": actual_route,
                    "failure_type": failure_type,
                    "value_score": row["value_score"],
                    "decision_evidence": {
                        "routing_decision_id": routing_decision_id,
                        "audit_event_id": row["audit_event_id"],
                        "route": actual_route,
                        "risk_level": row["risk_level"],
                    },
                },
                timestamp=timestamp,
            )
            conn.execute(
                """
                INSERT INTO routing_eval_cases(
                  id, routing_decision_id, source_feedback_id,
                  input_text_redacted, expected_route, actual_route,
                  failure_type, reason, status, case_json,
                  audit_event_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    eval_case_id,
                    routing_decision_id,
                    source_feedback_id,
                    row["input_text_redacted"],
                    expected_route,
                    actual_route,
                    failure_type,
                    reason,
                    "active",
                    _json_dumps(case),
                    audit_event_id,
                    timestamp,
                ),
            )
        return eval_case_id

    def active_routing_eval_cases(self) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT case_json FROM routing_eval_cases
                WHERE status = 'active'
                ORDER BY created_at, id
                """
            ).fetchall()
        cases: list[dict[str, Any]] = []
        for row in rows:
            case = _json_loads(row["case_json"], {})
            if isinstance(case, dict) and case.get("input") and case.get("expected_route"):
                cases.append(case)
        return cases

    def record_routing_eval_run(
        self,
        summary: dict[str, Any],
        *,
        release_label: str = "working-tree",
        actor_type: str = "system",
        actor_id: str = "routing-eval",
    ) -> dict[str, Any]:
        self.initialize()
        release_label = redact_audit_text(str(release_label or "working-tree").strip() or "working-tree")
        timestamp = now_iso()
        run_id = f"routing-eval-run-{uuid.uuid4().hex[:16]}"
        quality = summary.get("routing_quality") if isinstance(summary.get("routing_quality"), dict) else {}
        safety = summary.get("routing_safety") if isinstance(summary.get("routing_safety"), dict) else {}
        decision_logic = summary.get("decision_logic") if isinstance(summary.get("decision_logic"), dict) else {}
        passed = int(summary.get("passed") or quality.get("passed") or 0)
        total = int(summary.get("total") or 0)
        failed = int(summary.get("failed") or quality.get("failed") or 0)
        accuracy = float(quality.get("accuracy") if quality.get("accuracy") is not None else (passed / total if total else 1.0))
        safety_case_count = int(safety.get("safety_case_count") or 0)
        safety_failures = int(safety.get("safety_failures") or 0)
        safety_ok = bool(safety.get("safety_ok", safety_failures == 0))
        with self.connect() as conn:
            previous_row = conn.execute(
                """
                SELECT id, release_label, summary_json
                FROM routing_eval_runs
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
            previous = None
            if previous_row is not None:
                previous = {
                    "id": previous_row["id"],
                    "release_label": previous_row["release_label"],
                    "summary": _json_loads(previous_row["summary_json"], {}),
                }
            impact = _routing_eval_impact(summary, previous)
            tracked_summary = {
                **summary,
                "release_label": release_label,
                "eval_run_id": run_id,
                "release_impact": impact,
            }
            audit_event_id = self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="routing_eval_run_recorded",
                risk_level="low" if safety_ok else "medium",
                summary=f"Routing eval run {run_id} recorded for {release_label}: {passed}/{total} passed.",
                evidence="routing eval release tracking",
                redacted_payload={
                    "eval_run_id": run_id,
                    "release_label": release_label,
                    "decision_logic_fingerprint": decision_logic.get("logic_fingerprint", ""),
                    "passed": passed,
                    "total": total,
                    "failed": failed,
                    "accuracy": accuracy,
                    "safety_case_count": safety_case_count,
                    "safety_failures": safety_failures,
                    "safety_ok": safety_ok,
                    "impact": impact,
                },
                timestamp=timestamp,
            )
            conn.execute(
                """
                INSERT INTO routing_eval_runs(
                  id, release_label, decision_logic_fingerprint,
                  passed, total, failed, accuracy, safety_case_count,
                  safety_failures, safety_ok, impact_json, summary_json,
                  audit_event_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    release_label,
                    str(decision_logic.get("logic_fingerprint") or ""),
                    passed,
                    total,
                    failed,
                    accuracy,
                    safety_case_count,
                    safety_failures,
                    int(safety_ok),
                    _json_dumps(impact),
                    _json_dumps(tracked_summary),
                    audit_event_id,
                    timestamp,
                ),
            )
        return {"id": run_id, "release_label": release_label, "impact": impact, "summary": tracked_summary}

    def create_orchestration_proposal(
        self,
        proposal: dict[str, Any],
        *,
        actor_type: str = "system",
        actor_id: str = "orchestrator",
    ) -> str:
        self.initialize()
        timestamp = now_iso()
        proposal_id = f"orchestration-{uuid.uuid4().hex[:16]}"
        proposal = _redact_audit_value(proposal)
        with self.connect() as conn:
            routing_decision_id = proposal.get("routing_decision_id")
            if routing_decision_id:
                row = conn.execute("SELECT id FROM routing_decisions WHERE id = ?", (routing_decision_id,)).fetchone()
                if row is None:
                    raise ValueError("Unknown routing decision id")
            audit_event_id = self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="orchestration_proposed",
                risk_level=str((proposal.get("task_payload") or {}).get("risk_level") or "low"),
                summary=f"Orchestration proposal {proposal_id}: {proposal.get('route')}.",
                evidence="local deterministic orchestrator",
                redacted_payload={
                    "orchestration_proposal_id": proposal_id,
                    "routing_decision_id": routing_decision_id,
                    "route": proposal.get("route"),
                    "execution_allowed": bool(proposal.get("execution_allowed")),
                    "recommended_next_step": proposal.get("recommended_next_step"),
                    "has_task_payload": bool(proposal.get("task_payload")),
                    "has_approval_payload": bool(proposal.get("approval_payload")),
                },
                timestamp=timestamp,
            )
            conn.execute(
                """
                INSERT INTO orchestration_proposals(
                  id, routing_decision_id, status, route, summary, execution_allowed,
                  requires_user_review, recommended_next_step, proposal_json,
                  audit_event_id, created_at, updated_at
                )
                VALUES (?, ?, 'prepared', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal_id,
                    routing_decision_id,
                    str(proposal.get("route", "")),
                    str(proposal.get("summary", "")),
                    int(bool(proposal.get("execution_allowed", False))),
                    int(bool(proposal.get("requires_user_review", True))),
                    str(proposal.get("recommended_next_step", "")),
                    json.dumps(proposal, ensure_ascii=False, sort_keys=True),
                    audit_event_id,
                    timestamp,
                    timestamp,
                ),
            )
        return proposal_id

    def reject_orchestration_proposal(
        self,
        proposal_id: str,
        *,
        review_note: str,
        actor_type: str = "reviewer",
        actor_id: str = "dashboard",
    ) -> None:
        if not review_note.strip():
            raise ValueError("Rejecting an orchestration proposal requires review_note")
        _reject_secret_like_text("orchestration review_note", review_note)
        self.initialize()
        timestamp = now_iso()
        with self.connect() as conn:
            row = conn.execute("SELECT id, status, route FROM orchestration_proposals WHERE id = ?", (proposal_id,)).fetchone()
            if row is None:
                raise ValueError("Unknown orchestration proposal id")
            if row["status"] != "prepared":
                raise ValueError("Only prepared orchestration proposals can be rejected")
            conn.execute(
                """
                UPDATE orchestration_proposals
                SET status = 'rejected', review_note = ?, updated_at = ?
                WHERE id = ?
                """,
                (review_note, timestamp, proposal_id),
            )
            self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="orchestration_rejected",
                risk_level="low",
                summary=f"Orchestration proposal {proposal_id} rejected.",
                evidence="dashboard orchestration review",
                redacted_payload={"orchestration_proposal_id": proposal_id, "route": row["route"], "review_note_present": True},
                timestamp=timestamp,
            )

    def apply_orchestration_proposal(
        self,
        proposal_id: str,
        *,
        review_note: str,
        actor_type: str = "reviewer",
        actor_id: str = "dashboard",
    ) -> dict[str, str | None]:
        if not review_note.strip():
            raise ValueError("Applying an orchestration proposal requires review_note")
        _reject_secret_like_text("orchestration review_note", review_note)
        self.initialize()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id, status, proposal_json FROM orchestration_proposals WHERE id = ?",
                (proposal_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Unknown orchestration proposal id")
            if row["status"] != "prepared":
                raise ValueError("Only prepared orchestration proposals can be applied")
            proposal = json.loads(row["proposal_json"])

        task_payload = proposal.get("task_payload")
        approval_payload = proposal.get("approval_payload")
        route = str(proposal.get("route") or "")
        if route in {"direct_answer", "clarification_required", "refuse_redirect"} and (task_payload or approval_payload):
            raise ValueError("Direct/clarification/refuse proposals cannot create executable work")

        if approval_payload:
            approval_risk_level = str(approval_payload.get("risk_level") or "high")
            approval_summary = str(approval_payload.get("summary") or proposal.get("summary") or "Approval required")
            approval_fingerprint = _approval_plan_fingerprint(
                action_type=str(approval_payload.get("action_type") or "routing_gate"),
                summary=approval_summary,
                reason=str(approval_payload.get("reason") or "Explicit approval required before execution."),
                affected_systems=str(approval_payload.get("affected_systems") or ""),
                permissions=str(approval_payload.get("permissions") or ""),
                external_effect=str(approval_payload.get("external_effect") or ""),
                cost_estimate=str(approval_payload.get("cost_estimate") or ""),
                risk_level=approval_risk_level,
                risk_class=str(approval_payload.get("risk_class") or _risk_class_from_level(approval_risk_level)),
                expected_change=str(approval_payload.get("expected_change") or approval_summary),
                rollback_plan=str(approval_payload.get("rollback_plan") or ""),
                failure_mode=str(
                    approval_payload.get("failure_mode")
                    or "If this fails or is rejected, no action runs until a changed plan is reviewed."
                ),
            )
            with self.connect() as conn:
                rejected = conn.execute(
                    """
                    SELECT id FROM approvals
                    WHERE status = 'rejected' AND plan_fingerprint = ?
                    ORDER BY updated_at DESC, id
                    LIMIT 1
                    """,
                    (approval_fingerprint,),
                ).fetchone()
            if rejected is not None:
                raise ValueError("Rejected high-risk approval plan cannot be retried without a changed plan")

        task_id: str | None = None
        approval_id: str | None = None
        if task_payload:
            target_status = str(task_payload.get("status") or "planned")
            task_id = self.create_task(
                title=str(task_payload.get("title") or proposal.get("summary") or "Orchestration task"),
                goal=str(task_payload.get("goal") or "Reviewable orchestration task."),
                phase_id=str(task_payload.get("phase_id") or "") or None,
                owner=str(task_payload.get("owner") or "Codex"),
                status="new",
                priority=str(task_payload.get("priority") or "P1"),
                risk_level=str(task_payload.get("risk_level") or "medium"),
                approval_required=bool(task_payload.get("approval_required", False)),
                acceptance_criteria=str(task_payload.get("acceptance_criteria") or ""),
                actor_type="system",
                actor_id="orchestrator",
            )
            if target_status in {"planned", "active", "waiting_for_approval"}:
                self.update_task_status(task_id, "planned", actor_type="system", actor_id="orchestrator")
            if target_status == "active":
                self.update_task_status(task_id, "active", actor_type="system", actor_id="orchestrator")

        if approval_payload:
            approval_id = self.create_approval(
                task_id=task_id,
                action_type=str(approval_payload.get("action_type") or "routing_gate"),
                summary=str(approval_payload.get("summary") or proposal.get("summary") or "Approval required"),
                reason=str(approval_payload.get("reason") or "Explicit approval required before execution."),
                affected_systems=str(approval_payload.get("affected_systems") or ""),
                permissions=str(approval_payload.get("permissions") or ""),
                external_effect=str(approval_payload.get("external_effect") or ""),
                cost_estimate=str(approval_payload.get("cost_estimate") or ""),
                risk_level=str(approval_payload.get("risk_level") or "high"),
                risk_class=str(approval_payload.get("risk_class") or ""),
                expected_change=str(approval_payload.get("expected_change") or ""),
                rollback_plan=str(approval_payload.get("rollback_plan") or ""),
                failure_mode=str(approval_payload.get("failure_mode") or ""),
                requested_by="orchestrator",
                actor_type="system",
                actor_id="orchestrator",
            )
            if task_id:
                self.update_task_status(
                    task_id,
                    "waiting_for_approval",
                    approval_id=approval_id,
                    actor_type="system",
                    actor_id="orchestrator",
                )

        timestamp = now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE orchestration_proposals
                SET status = 'applied', applied_task_id = ?, applied_approval_id = ?,
                    review_note = ?, updated_at = ?, applied_at = ?
                WHERE id = ?
                """,
                (task_id, approval_id, review_note, timestamp, timestamp, proposal_id),
            )
            self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="orchestration_applied",
                task_id=task_id,
                approval_id=approval_id,
                risk_level=str((task_payload or {}).get("risk_level") or (approval_payload or {}).get("risk_level") or "low"),
                summary=f"Orchestration proposal {proposal_id} applied without executing external actions.",
                evidence="dashboard orchestration review",
                redacted_payload={
                    "orchestration_proposal_id": proposal_id,
                    "route": route,
                    "task_id": task_id,
                    "approval_id": approval_id,
                    "execution_allowed": False,
                    "review_note_present": True,
                },
                timestamp=timestamp,
            )
        return {"task_id": task_id, "approval_id": approval_id}

    def review_agent_run(
        self,
        run_id: str,
        *,
        review_status: str,
        review_note: str,
        actor_type: str = "reviewer",
        actor_id: str = "dashboard",
    ) -> None:
        if review_status not in {"accepted", "changes_requested", "rejected"}:
            raise ValueError("Invalid agent run review_status")
        if not review_note.strip():
            raise ValueError("Agent run review requires review_note")
        _reject_secret_like_text("agent run review_note", review_note)
        self.initialize()
        timestamp = now_iso()
        with self.connect() as conn:
            row = conn.execute("SELECT id, task_id, risk, status FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                raise ValueError("Unknown agent run id")
            if row["status"] not in {"waiting_for_review", "failed"}:
                raise ValueError("Only completed agent runs can be reviewed")
            reviewer_result = {
                "status": review_status,
                "reviewer_role": "Review",
                "review_note": review_note,
                "reviewed_at": timestamp,
            }
            next_action = next_action_for_review_status(review_status)
            conn.execute(
                """
                UPDATE agent_runs
                SET review_status = ?, review_note = ?, reviewer_result_json = ?,
                    next_action = ?, status = ?, updated_at = ?
                WHERE id = ?
                """,
                (review_status, review_note, _json_dumps(reviewer_result), next_action, review_status, timestamp, run_id),
            )
            self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="agent_run_reviewed",
                task_id=row["task_id"],
                risk_level=row["risk"],
                summary=f"Agent run {run_id} reviewed as {review_status}.",
                evidence="dashboard agent run review API",
                redacted_payload={
                    "agent_run_id": run_id,
                    "old_status": row["status"],
                    "new_status": review_status,
                    "review_status": review_status,
                    "reviewer_result": reviewer_result,
                    "next_action": next_action,
                    "review_note_present": True,
                },
                timestamp=timestamp,
            )

    def upsert_tool_manifest(
        self,
        manifest: dict[str, Any],
        *,
        actor_type: str = "reviewer",
        actor_id: str = "dashboard",
        allow_status_change: bool = False,
    ) -> str:
        from leon_control_plane.tool_registry import normalize_tool_manifest

        manifest = normalize_tool_manifest(manifest)
        manifest = _redact_audit_value(manifest)
        self.initialize()
        timestamp = now_iso()
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT tool_id, status FROM tool_manifests WHERE tool_id = ?",
                (manifest["tool_id"],),
            ).fetchone()
            requested_status = manifest["status"]
            if existing:
                if requested_status != existing["status"] and not allow_status_change:
                    manifest["status"] = existing["status"]
            elif requested_status != "candidate" and not allow_status_change:
                raise ValueError("New tool manifests must start as candidate")
            event_type = "tool_manifest_updated" if existing else "tool_manifest_registered"
            audit_event_id = self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type=event_type,
                risk_level=manifest["risk_level"],
                summary=f"Tool manifest {manifest['tool_id']} stored as {manifest['status']}.",
                evidence="local tool registry manifest API",
                redacted_payload={
                    "tool_id": manifest["tool_id"],
                    "name": manifest["name"],
                    "source_type": manifest["source_type"],
                    "source_url": manifest["source_url"],
                    "old_status": existing["status"] if existing else None,
                    "requested_status": requested_status,
                    "new_status": manifest["status"],
                    "status_change_allowed": allow_status_change,
                    "read_scope_count": len(manifest["read_scopes"]),
                    "write_scope_count": len(manifest["write_scopes"]),
                    "required_env_keys": manifest["required_env_keys"],
                    "raw_secret_values_stored": False,
                },
                timestamp=timestamp,
            )
            created_at = timestamp
            if existing:
                row = conn.execute(
                    "SELECT created_at FROM tool_manifests WHERE tool_id = ?",
                    (manifest["tool_id"],),
                ).fetchone()
                created_at = row["created_at"] if row else timestamp
            conn.execute(
                """
                INSERT INTO tool_manifests(
                  tool_id, name, source_type, source_url, purpose, owner, risk_level,
                  status, read_scopes_json, write_scopes_json, required_env_keys_json,
                  cost_profile, resource_profile, external_effects_json,
                  approval_required_for_json, allowed_without_approval_json,
                  forbidden_actions_json, audit_events_json, rollback_notes,
                  maintenance_status, sandbox_required, notes, manifest_json,
                  audit_event_id, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tool_id) DO UPDATE SET
                  name = excluded.name,
                  source_type = excluded.source_type,
                  source_url = excluded.source_url,
                  purpose = excluded.purpose,
                  owner = excluded.owner,
                  risk_level = excluded.risk_level,
                  status = excluded.status,
                  read_scopes_json = excluded.read_scopes_json,
                  write_scopes_json = excluded.write_scopes_json,
                  required_env_keys_json = excluded.required_env_keys_json,
                  cost_profile = excluded.cost_profile,
                  resource_profile = excluded.resource_profile,
                  external_effects_json = excluded.external_effects_json,
                  approval_required_for_json = excluded.approval_required_for_json,
                  allowed_without_approval_json = excluded.allowed_without_approval_json,
                  forbidden_actions_json = excluded.forbidden_actions_json,
                  audit_events_json = excluded.audit_events_json,
                  rollback_notes = excluded.rollback_notes,
                  maintenance_status = excluded.maintenance_status,
                  sandbox_required = excluded.sandbox_required,
                  notes = excluded.notes,
                  manifest_json = excluded.manifest_json,
                  audit_event_id = excluded.audit_event_id,
                  updated_at = excluded.updated_at
                """,
                (
                    manifest["tool_id"],
                    manifest["name"],
                    manifest["source_type"],
                    manifest["source_url"],
                    manifest["purpose"],
                    manifest["owner"],
                    manifest["risk_level"],
                    manifest["status"],
                    json.dumps(manifest["read_scopes"], ensure_ascii=False, sort_keys=True),
                    json.dumps(manifest["write_scopes"], ensure_ascii=False, sort_keys=True),
                    json.dumps(manifest["required_env_keys"], ensure_ascii=False, sort_keys=True),
                    manifest["cost_profile"],
                    manifest["resource_profile"],
                    json.dumps(manifest["external_effects"], ensure_ascii=False, sort_keys=True),
                    json.dumps(manifest["approval_required_for"], ensure_ascii=False, sort_keys=True),
                    json.dumps(manifest["allowed_without_approval"], ensure_ascii=False, sort_keys=True),
                    json.dumps(manifest["forbidden_actions"], ensure_ascii=False, sort_keys=True),
                    json.dumps(manifest["audit_events"], ensure_ascii=False, sort_keys=True),
                    manifest["rollback_notes"],
                    manifest["maintenance_status"],
                    int(bool(manifest["sandbox_required"])),
                    manifest["notes"],
                    json.dumps(manifest, ensure_ascii=False, sort_keys=True),
                    audit_event_id,
                    created_at,
                    timestamp,
                ),
            )
        return manifest["tool_id"]

    def upsert_connector_manifest(
        self,
        manifest: dict[str, Any],
        *,
        actor_type: str = "reviewer",
        actor_id: str = "dashboard",
        allow_status_change: bool = False,
    ) -> str:
        from leon_control_plane.connector_registry import normalize_connector_manifest

        manifest = _redact_audit_value(normalize_connector_manifest(manifest))
        self.initialize()
        timestamp = now_iso()
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT connector_id, status FROM connector_manifests WHERE connector_id = ?",
                (manifest["connector_id"],),
            ).fetchone()
            requested_status = manifest["status"]
            if existing and requested_status != existing["status"] and not allow_status_change:
                manifest["status"] = existing["status"]
            event_type = "connector_manifest_updated" if existing else "connector_manifest_registered"
            audit_event_id = self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type=event_type,
                risk_level=manifest["risk_level"],
                summary=f"Connector manifest {manifest['connector_id']} stored as {manifest['status']}.",
                evidence="local connector permission manifest registry",
                redacted_payload={
                    "connector_id": manifest["connector_id"],
                    "name": manifest["name"],
                    "connector_type": manifest["connector_type"],
                    "old_status": existing["status"] if existing else None,
                    "requested_status": requested_status,
                    "new_status": manifest["status"],
                    "status_change_allowed": allow_status_change,
                    "read_scope_count": len(manifest["read_scopes"]),
                    "write_scope_count": len(manifest["write_scopes"]),
                    "required_env_keys": manifest["required_env_keys"],
                    "raw_secret_values_stored": False,
                },
                timestamp=timestamp,
            )
            created_at = timestamp
            if existing:
                row = conn.execute(
                    "SELECT created_at FROM connector_manifests WHERE connector_id = ?",
                    (manifest["connector_id"],),
                ).fetchone()
                created_at = row["created_at"] if row else timestamp
            conn.execute(
                """
                INSERT INTO connector_manifests(
                  connector_id, name, connector_type, status, owner, purpose,
                  read_scopes_json, write_scopes_json, required_env_keys_json,
                  external_system, external_effects_json, approval_required_for_json,
                  allowed_without_approval_json, forbidden_actions_json,
                  connector_policy_allows_autonomy, risk_level, rollback_notes,
                  secret_handling_json, notes, manifest_json, audit_event_id,
                  created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(connector_id) DO UPDATE SET
                  name = excluded.name,
                  connector_type = excluded.connector_type,
                  status = excluded.status,
                  owner = excluded.owner,
                  purpose = excluded.purpose,
                  read_scopes_json = excluded.read_scopes_json,
                  write_scopes_json = excluded.write_scopes_json,
                  required_env_keys_json = excluded.required_env_keys_json,
                  external_system = excluded.external_system,
                  external_effects_json = excluded.external_effects_json,
                  approval_required_for_json = excluded.approval_required_for_json,
                  allowed_without_approval_json = excluded.allowed_without_approval_json,
                  forbidden_actions_json = excluded.forbidden_actions_json,
                  connector_policy_allows_autonomy = excluded.connector_policy_allows_autonomy,
                  risk_level = excluded.risk_level,
                  rollback_notes = excluded.rollback_notes,
                  secret_handling_json = excluded.secret_handling_json,
                  notes = excluded.notes,
                  manifest_json = excluded.manifest_json,
                  audit_event_id = excluded.audit_event_id,
                  updated_at = excluded.updated_at
                """,
                (
                    manifest["connector_id"],
                    manifest["name"],
                    manifest["connector_type"],
                    manifest["status"],
                    manifest["owner"],
                    manifest["purpose"],
                    json.dumps(manifest["read_scopes"], ensure_ascii=False, sort_keys=True),
                    json.dumps(manifest["write_scopes"], ensure_ascii=False, sort_keys=True),
                    json.dumps(manifest["required_env_keys"], ensure_ascii=False, sort_keys=True),
                    int(bool(manifest["external_system"])),
                    json.dumps(manifest["external_effects"], ensure_ascii=False, sort_keys=True),
                    json.dumps(manifest["approval_required_for"], ensure_ascii=False, sort_keys=True),
                    json.dumps(manifest["allowed_without_approval"], ensure_ascii=False, sort_keys=True),
                    json.dumps(manifest["forbidden_actions"], ensure_ascii=False, sort_keys=True),
                    int(bool(manifest["connector_policy_allows_autonomy"])),
                    manifest["risk_level"],
                    manifest["rollback_notes"],
                    json.dumps(manifest["secret_handling"], ensure_ascii=False, sort_keys=True),
                    manifest["notes"],
                    json.dumps(manifest, ensure_ascii=False, sort_keys=True),
                    audit_event_id,
                    created_at,
                    timestamp,
                ),
            )
        return manifest["connector_id"]

    def create_planner_preview(
        self,
        preview: dict[str, Any],
        *,
        task_id: str | None = None,
        actor_type: str = "system",
        actor_id: str = "planner-preview",
    ) -> str:
        self.initialize()
        preview = _redact_audit_value(preview)
        serialized = json.dumps(preview, ensure_ascii=False, sort_keys=True)
        if contains_secret(preview):
            raise ValueError("Planner preview payload appears to contain a secret value")
        for key in [
            "execution_allowed",
            "external_calls_made",
            "accounts_connected",
            "secret_values_read",
            "write_allowed_now",
        ]:
            if bool(preview.get(key)):
                raise ValueError(f"Planner preview must keep {key}=false")

        timestamp = now_iso()
        preview_id = f"planner-preview-{uuid.uuid4().hex[:16]}"
        task_ref = str(task_id or preview.get("task_id") or "").strip() or None
        with self.connect() as conn:
            if task_ref and conn.execute("SELECT id FROM tasks WHERE id = ?", (task_ref,)).fetchone() is None:
                raise ValueError("Unknown task id")
            audit_event_id = self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="planner_preview_created",
                task_id=task_ref,
                risk_level="low",
                summary=f"Planner preview {preview_id} created without external execution.",
                evidence="local deterministic planner preview; sample data only; no install/connect/write/secret read",
                redacted_payload={
                    "planner_preview_id": preview_id,
                    "decision": preview.get("decision"),
                    "execution_allowed": False,
                    "external_calls_made": False,
                    "accounts_connected": False,
                    "secret_values_read": False,
                    "write_allowed_now": False,
                    "approval_required": bool(preview.get("approval_required", False)),
                    "proposal_count": len(preview.get("proposals") or []),
                    "conflict_count": len(preview.get("conflicts") or []),
                    "free_slot_count": len(preview.get("free_slots") or []),
                },
                timestamp=timestamp,
            )
            conn.execute(
                """
                INSERT INTO planner_previews(
                  id, task_id, decision, execution_allowed,
                  external_calls_made, accounts_connected,
                  secret_values_read, write_allowed_now, approval_required,
                  preview_json, audit_event_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    preview_id,
                    task_ref,
                    str(preview.get("decision") or ""),
                    0,
                    0,
                    0,
                    0,
                    0,
                    int(bool(preview.get("approval_required", False))),
                    serialized,
                    audit_event_id,
                    timestamp,
                ),
            )
        return preview_id

    def create_mcp_candidate_intake(
        self,
        checklist: dict[str, Any],
        *,
        actor_type: str = "system",
        actor_id: str = "mcp-candidate-intake",
    ) -> str:
        self.initialize()
        tool_id = str(checklist.get("tool_id") or "").strip()
        if not tool_id:
            raise ValueError("MCP candidate intake requires tool_id")
        if checklist.get("execution_allowed") is not False:
            raise ValueError("MCP candidate intake must not allow execution")
        if checklist.get("no_approval_granted") is not True:
            raise ValueError("MCP candidate intake must not grant approval")
        if checklist.get("status_unchanged") is not True:
            raise ValueError("MCP candidate intake must not change manifest status")
        for key in ["install_allowed_now", "connect_allowed_now", "write_allowed_now"]:
            if bool(checklist.get(key)):
                raise ValueError(f"MCP candidate intake must keep {key}=false")
        checklist = _redact_audit_value(checklist)
        serialized = json.dumps(checklist, ensure_ascii=False, sort_keys=True)
        if contains_secret(checklist):
            raise ValueError("MCP candidate intake payload appears to contain a secret value")

        timestamp = now_iso()
        intake_id = f"mcp-intake-{uuid.uuid4().hex[:16]}"
        with self.connect() as conn:
            row = conn.execute(
                "SELECT tool_id, status FROM tool_manifests WHERE tool_id = ?",
                (tool_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Unknown tool manifest id")
            if str(row["status"]) != str(checklist.get("manifest_status")):
                raise ValueError("MCP candidate intake manifest status snapshot is stale")
            audit_event_id = self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="mcp_candidate_intake_created",
                risk_level="low",
                summary=f"MCP candidate intake {intake_id} created for {tool_id}.",
                evidence="local MCP review checklist; no install, connect, execution, approval or status promotion",
                redacted_payload={
                    "mcp_candidate_intake_id": intake_id,
                    "tool_id": tool_id,
                    "manifest_status": checklist.get("manifest_status"),
                    "execution_allowed": False,
                    "no_approval_granted": True,
                    "status_unchanged": True,
                    "tool_mapping_count": len(checklist.get("tool_mappings") or []),
                    "review_gates": checklist.get("review_gates") or [],
                },
                timestamp=timestamp,
            )
            conn.execute(
                """
                INSERT INTO mcp_candidate_intakes(
                  id, tool_id, status, decision, execution_allowed,
                  no_approval_granted, status_unchanged,
                  install_allowed_now, connect_allowed_now, write_allowed_now,
                  checklist_json, audit_event_id, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    intake_id,
                    tool_id,
                    str(checklist.get("review_status") or "needs_review"),
                    str(checklist.get("decision") or ""),
                    0,
                    1,
                    1,
                    0,
                    0,
                    0,
                    serialized,
                    audit_event_id,
                    timestamp,
                    timestamp,
                ),
            )
        return intake_id

    def get_tool_manifest(self, tool_id: str) -> dict[str, Any]:
        self.initialize()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT manifest_json FROM tool_manifests WHERE tool_id = ?",
                (tool_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Unknown tool manifest id")
            return json.loads(row["manifest_json"])

    def get_connector_manifest(self, connector_id: str) -> dict[str, Any]:
        self.initialize()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT manifest_json FROM connector_manifests WHERE connector_id = ?",
                (connector_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Unknown connector manifest id")
            return json.loads(row["manifest_json"])

    def retrieve_memory(
        self,
        query: str,
        *,
        scope: str = "context",
        limit: int = 5,
        actor_type: str = "user",
        actor_id: str = "memory-retrieval",
    ) -> dict[str, Any]:
        query = str(query or "").strip()
        if not query:
            raise ValueError("retrieval query is required")
        if len(query) > 1000:
            raise ValueError("retrieval query must be 1000 characters or fewer")
        scope = str(scope or "context").strip().lower().replace("-", "_").replace(" ", "_")
        if scope not in RETRIEVAL_SCOPES:
            raise ValueError("invalid retrieval scope")
        try:
            assert_no_secrets("memory retrieval query", query)
        except SecretScanError as exc:
            self.record_secret_scan_failure(
                surface="memory_retrieval",
                label=exc.label,
                finding_kinds=exc.result.kinds,
                finding_count=exc.result.total,
                actor_type=actor_type,
                actor_id=actor_id,
            )
            raise
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 5
        limit = max(1, min(limit, 10))

        started = time.perf_counter()
        self.initialize()
        timestamp = now_iso()
        retrieval_id = f"retrieval-{uuid.uuid4().hex[:16]}"
        query_redacted = redact_audit_text(query)
        query_tokens = _retrieval_tokens(query)

        with self.connect() as conn:
            memory_rows = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, status, memory_type, content, source, source_task_id,
                           confidence, sensitivity, privacy_level, expires_at,
                           review_note, correction_of, graph_entities_json,
                           provenance_json, conflict_status, conflict_memory_ids_json,
                           conflict_note, audit_event_id, created_at, updated_at
                    FROM memory_items
                    WHERE status IN ('active', 'candidate')
                    ORDER BY updated_at DESC, id DESC
                    LIMIT 300
                    """
                )
            ]
            source_rows = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, source_type, source_ref, title, status, content_hash,
                           content_excerpt, content_bytes, metadata_json,
                           secret_scan_json, audit_event_id, created_at, updated_at
                    FROM source_records
                    WHERE status = 'active'
                    ORDER BY updated_at DESC, id DESC
                    LIMIT 300
                    """
                )
            ]
            graph_edges = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, source_memory_id, subject, predicate, object,
                           relationship_type, confidence, source, status,
                           created_at, updated_at
                    FROM memory_graph_edges
                    WHERE status = 'active'
                    ORDER BY updated_at DESC, id DESC
                    LIMIT 500
                    """
                )
            ]
            graph_entities = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, entity_type, label, source_memory_id, external_ref,
                           provenance_json, confidence, status, created_at, updated_at
                    FROM memory_graph_entities
                    WHERE status = 'active'
                    ORDER BY updated_at DESC, id DESC
                    LIMIT 500
                    """
                )
            ]
            graph_relationships = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT relationship.id, relationship.relationship_type,
                           relationship.from_entity_id, relationship.to_entity_id,
                           relationship.source_memory_id, relationship.label,
                           relationship.provenance_json, relationship.confidence,
                           relationship.status, relationship.created_at, relationship.updated_at,
                           source_entity.entity_type AS from_entity_type,
                           source_entity.label AS from_label,
                           target_entity.entity_type AS to_entity_type,
                           target_entity.label AS to_label
                    FROM memory_graph_relationships AS relationship
                    JOIN memory_graph_entities AS source_entity ON source_entity.id = relationship.from_entity_id
                    JOIN memory_graph_entities AS target_entity ON target_entity.id = relationship.to_entity_id
                    WHERE relationship.status = 'active'
                    ORDER BY relationship.updated_at DESC, relationship.id DESC
                    LIMIT 500
                    """
                )
            ]

            memories_by_id = {row["id"]: row for row in memory_rows}

            def compact_graph_for_memory(memory_id: str) -> list[dict[str, Any]]:
                entries: list[dict[str, Any]] = []
                for entity in graph_entities:
                    if entity.get("source_memory_id") == memory_id:
                        entries.append({
                            "kind": "entity",
                            "id": entity["id"],
                            "entity_type": entity["entity_type"],
                            "label": entity["label"],
                            "external_ref": entity.get("external_ref") or "",
                            "confidence": entity.get("confidence"),
                        })
                for relationship in graph_relationships:
                    if relationship.get("source_memory_id") == memory_id:
                        entries.append({
                            "kind": "relationship",
                            "id": relationship["id"],
                            "relationship_type": relationship["relationship_type"],
                            "from": {
                                "id": relationship["from_entity_id"],
                                "entity_type": relationship.get("from_entity_type"),
                                "label": relationship.get("from_label"),
                            },
                            "to": {
                                "id": relationship["to_entity_id"],
                                "entity_type": relationship.get("to_entity_type"),
                                "label": relationship.get("to_label"),
                            },
                            "label": relationship.get("label") or "",
                            "confidence": relationship.get("confidence"),
                        })
                for edge in graph_edges:
                    if edge.get("source_memory_id") == memory_id:
                        entries.append({
                            "kind": "edge",
                            "id": edge["id"],
                            "relationship_type": edge.get("relationship_type") or "related_to",
                            "subject": edge.get("subject"),
                            "predicate": edge.get("predicate"),
                            "object": edge.get("object"),
                            "confidence": edge.get("confidence"),
                        })
                return entries[:8]

            def compact_graph_for_source(source_record_id: str) -> list[dict[str, Any]]:
                entries: list[dict[str, Any]] = []
                for entity in graph_entities:
                    provenance = _json_loads(entity.get("provenance_json"), {})
                    if entity.get("external_ref") == source_record_id or provenance.get("source_record_id") == source_record_id:
                        entries.append({
                            "kind": "entity",
                            "id": entity["id"],
                            "entity_type": entity["entity_type"],
                            "label": entity["label"],
                            "external_ref": entity.get("external_ref") or "",
                            "confidence": entity.get("confidence"),
                        })
                for relationship in graph_relationships:
                    provenance = _json_loads(relationship.get("provenance_json"), {})
                    if provenance.get("source_record_id") == source_record_id:
                        entries.append({
                            "kind": "relationship",
                            "id": relationship["id"],
                            "relationship_type": relationship["relationship_type"],
                            "from": {
                                "id": relationship["from_entity_id"],
                                "entity_type": relationship.get("from_entity_type"),
                                "label": relationship.get("from_label"),
                            },
                            "to": {
                                "id": relationship["to_entity_id"],
                                "entity_type": relationship.get("to_entity_type"),
                                "label": relationship.get("to_label"),
                            },
                            "label": relationship.get("label") or "",
                            "confidence": relationship.get("confidence"),
                        })
                return entries[:8]

            matches: list[dict[str, Any]] = []
            for row in memory_rows:
                graph_entities_value = _json_loads(row.get("graph_entities_json"), [])
                provenance = _json_loads(row.get("provenance_json"), {}) or {
                    "source": row.get("source") or "",
                    "source_task_id": row.get("source_task_id"),
                    "captured_by": "leon_control_plane",
                }
                searchable = " ".join(
                    [
                        row.get("content") or "",
                        row.get("source") or "",
                        json.dumps(graph_entities_value, ensure_ascii=False),
                        json.dumps(provenance, ensure_ascii=False, sort_keys=True),
                    ]
                )
                content_score = _retrieval_token_score(query_tokens, row.get("content") or "")
                metadata_score = _retrieval_token_score(query_tokens, searchable)
                if content_score <= 0 and metadata_score <= 0:
                    continue
                confidence = _normalize_confidence(row.get("confidence"))
                score = (content_score * 0.56) + (metadata_score * 0.18) + (confidence * 0.20)
                if str(row.get("status")) == "active":
                    score += 0.06
                else:
                    score -= 0.04
                if scope == "project" and str(row.get("memory_type")) == "project_fact":
                    score += 0.08
                if scope == "memory":
                    score += 0.04
                score = round(max(0, min(score, 1)), 4)
                conflict_ids = _json_loads(row.get("conflict_memory_ids_json"), [])
                conflict = {
                    "has_conflicts": row.get("conflict_status") == "conflicted" or bool(conflict_ids),
                    "conflict_status": row.get("conflict_status") or "none",
                    "conflict_memory_ids": conflict_ids,
                    "conflict_note": row.get("conflict_note") or "",
                    "conflict_previews": [
                        {
                            "memory_id": conflict_id,
                            "status": memories_by_id.get(conflict_id, {}).get("status"),
                            "excerpt": _retrieval_excerpt(memories_by_id.get(conflict_id, {}).get("content") or "", query_tokens, limit=160),
                        }
                        for conflict_id in conflict_ids
                        if conflict_id in memories_by_id
                    ],
                }
                source_ref = {
                    "kind": "memory",
                    "id": row["id"],
                    "source": row.get("source") or provenance.get("source") or "",
                    "source_task_id": row.get("source_task_id") or provenance.get("source_task_id"),
                    "provenance": provenance,
                    "confidence": confidence,
                    "status": row.get("status"),
                }
                matches.append({
                    "kind": "memory",
                    "id": row["id"],
                    "status": row.get("status"),
                    "memory_type": row.get("memory_type"),
                    "score": score,
                    "confidence": confidence,
                    "excerpt": _retrieval_excerpt(row.get("content") or "", query_tokens),
                    "source_ref": source_ref,
                    "provenance": provenance,
                    "related_graph_entries": compact_graph_for_memory(row["id"]),
                    "conflict": conflict,
                    "created_at": row.get("created_at"),
                    "updated_at": row.get("updated_at"),
                })

            for row in source_rows:
                metadata = _json_loads(row.get("metadata_json"), {})
                searchable = " ".join(
                    [
                        row.get("title") or "",
                        row.get("source_ref") or "",
                        row.get("content_excerpt") or "",
                        json.dumps(metadata, ensure_ascii=False, sort_keys=True),
                    ]
                )
                title_score = _retrieval_token_score(query_tokens, f"{row.get('title') or ''} {row.get('source_ref') or ''}")
                body_score = _retrieval_token_score(query_tokens, searchable)
                if title_score <= 0 and body_score <= 0:
                    continue
                type_boost = 0
                if scope == "document" and row.get("source_type") in {"local_document", "project_file", "repo_doc"}:
                    type_boost = 0.1
                elif scope == "project" and row.get("source_type") in {"project_file", "repo_doc", "task"}:
                    type_boost = 0.08
                elif scope == "source":
                    type_boost = 0.06
                score = round(max(0, min((body_score * 0.64) + (title_score * 0.22) + 0.08 + type_boost, 1)), 4)
                source_ref = {
                    "kind": "source_record",
                    "id": row["id"],
                    "source_type": row.get("source_type"),
                    "source_ref": row.get("source_ref"),
                    "title": row.get("title"),
                    "content_hash": row.get("content_hash"),
                    "status": row.get("status"),
                    "provenance": {
                        "source_record_id": row["id"],
                        "source_type": row.get("source_type"),
                        "source_ref": row.get("source_ref"),
                        "content_hash": row.get("content_hash"),
                    },
                }
                matches.append({
                    "kind": "source_record",
                    "id": row["id"],
                    "status": row.get("status"),
                    "source_type": row.get("source_type"),
                    "score": score,
                    "confidence": round(min(score + 0.08, 1), 4),
                    "excerpt": _retrieval_excerpt(row.get("content_excerpt") or "", query_tokens),
                    "source_ref": source_ref,
                    "provenance": source_ref["provenance"],
                    "related_graph_entries": compact_graph_for_source(row["id"]),
                    "conflict": {"has_conflicts": False, "conflict_status": "none", "conflict_memory_ids": [], "conflict_note": ""},
                    "created_at": row.get("created_at"),
                    "updated_at": row.get("updated_at"),
                })

            matches.sort(key=lambda item: (float(item.get("score") or 0), str(item.get("updated_at") or "")), reverse=True)
            matches = matches[:limit]
            answer_status = "answered" if matches else "no_relevant_sources"
            top_score = float(matches[0]["score"]) if matches else 0
            relevance_score = round(top_score, 4)
            confidence = round(min(1, (top_score * 0.7) + (sum(float(item["confidence"]) for item in matches[:3]) / max(1, min(3, len(matches))) * 0.3)), 4) if matches else 0
            conflict_matches = [item for item in matches if item.get("conflict", {}).get("has_conflicts")]
            source_refs: list[dict[str, Any]] = []
            related_graph_entries: list[dict[str, Any]] = []
            for match in matches:
                if match["source_ref"] not in source_refs:
                    source_refs.append(match["source_ref"])
                for entry in match.get("related_graph_entries") or []:
                    if entry not in related_graph_entries:
                        related_graph_entries.append(entry)
            source_refs = source_refs[:10]
            related_graph_entries = related_graph_entries[:20]
            conflicts = [
                {
                    "memory_id": item["id"],
                    **item["conflict"],
                    "provenance": item.get("provenance", {}),
                    "confidence": item.get("confidence"),
                }
                for item in conflict_matches
            ]
            if matches:
                answer_lines = [
                    f"Source-backed answer for '{query_redacted}' from {len(matches)} relevant local result(s).",
                ]
                for index, match in enumerate(matches[:3], start=1):
                    if match["kind"] == "memory":
                        conflict_marker = " Conflict marked." if match.get("conflict", {}).get("has_conflicts") else ""
                        answer_lines.append(
                            f"{index}. Memory {match['id']} ({match['status']}, confidence {match['confidence']:.2f}). "
                            f"{match['excerpt']}{conflict_marker}"
                        )
                    else:
                        answer_lines.append(
                            f"{index}. Source {match['source_ref']['title']} ({match['source_ref']['source_ref']}, relevance {match['score']:.2f}). "
                            f"{match['excerpt']}"
                        )
                answer = "\n".join(answer_lines)
            else:
                answer = (
                    f"I could not find source-backed local knowledge for '{query_redacted}'. "
                    "Index project sources or add reviewed memory, then ask again."
                )
            latency_ms = int(round((time.perf_counter() - started) * 1000))
            metrics = {
                "latency_ms": latency_ms,
                "relevance_score": relevance_score,
                "confidence": confidence,
                "match_count": len(matches),
                "memory_match_count": sum(1 for item in matches if item["kind"] == "memory"),
                "source_match_count": sum(1 for item in matches if item["kind"] == "source_record"),
                "conflict_count": len(conflicts),
                "query_token_count": len(query_tokens),
                "result_limit": limit,
                "scope": scope,
                "measurable_for_v1": True,
            }
            audit_event_id = self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="memory_retrieval_completed",
                risk_level="low",
                summary=f"Memory retrieval {retrieval_id} completed with {len(matches)} match(es).",
                evidence="local read-only memory/source retrieval with provenance, confidence, conflicts and latency metrics",
                redacted_payload={
                    "retrieval_id": retrieval_id,
                    "query": query_redacted,
                    "scope": scope,
                    "answer_status": answer_status,
                    "confidence": confidence,
                    "latency_ms": latency_ms,
                    "relevance_score": relevance_score,
                    "match_count": len(matches),
                    "memory_match_count": metrics["memory_match_count"],
                    "source_match_count": metrics["source_match_count"],
                    "conflict_count": len(conflicts),
                    "source_refs": source_refs,
                    "raw_secret_values_stored": False,
                    "full_source_content_stored_in_audit": False,
                },
                timestamp=timestamp,
            )
            conn.execute(
                """
                INSERT INTO memory_retrieval_queries(
                  id, query_redacted, scope, answer, answer_status, confidence,
                  latency_ms, relevance_score, match_count, memory_match_count,
                  source_match_count, conflict_count, source_refs_json,
                  related_graph_entries_json, conflicts_json, metrics_json,
                  audit_event_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    retrieval_id,
                    query_redacted,
                    scope,
                    redact_audit_text(answer),
                    answer_status,
                    confidence,
                    latency_ms,
                    relevance_score,
                    len(matches),
                    metrics["memory_match_count"],
                    metrics["source_match_count"],
                    len(conflicts),
                    json.dumps(source_refs, ensure_ascii=False, sort_keys=True),
                    json.dumps(related_graph_entries, ensure_ascii=False, sort_keys=True),
                    json.dumps(conflicts, ensure_ascii=False, sort_keys=True),
                    json.dumps(metrics, ensure_ascii=False, sort_keys=True),
                    audit_event_id,
                    timestamp,
                ),
            )
        return _redact_audit_value({
            "id": retrieval_id,
            "query": query_redacted,
            "scope": scope,
            "answer": answer,
            "answer_status": answer_status,
            "confidence": confidence,
            "results": matches,
            "source_refs": source_refs,
            "related_graph_entries": related_graph_entries,
            "conflicts": conflicts,
            "metrics": metrics,
            "audit_event_id": audit_event_id,
            "created_at": timestamp,
        })

    def get_approval_status(self, approval_id: str | None) -> str | None:
        if not approval_id:
            return None
        self.initialize()
        with self.connect() as conn:
            row = conn.execute("SELECT status FROM approvals WHERE id = ?", (approval_id,)).fetchone()
            return None if row is None else str(row["status"])

    def _normalize_memory_provenance(self, raw: dict[str, Any], *, source: str, source_task_id: str | None) -> dict[str, Any]:
        provenance_raw = raw.get("provenance")
        if provenance_raw is None:
            provenance: dict[str, Any] = {}
        elif isinstance(provenance_raw, dict):
            provenance = dict(provenance_raw)
        else:
            raise ValueError("memory provenance must be an object")
        provenance.setdefault("source", source)
        if source_task_id:
            provenance.setdefault("source_task_id", source_task_id)
        provenance.setdefault("captured_by", "leon_control_plane")
        assert_no_secrets("memory provenance", provenance)
        return _redact_audit_value(provenance)

    def _normalize_source_record_type(self, source_type: Any) -> str:
        normalized = str(source_type or "project_file").strip().lower().replace("-", "_").replace(" ", "_")
        if normalized not in SOURCE_RECORD_TYPES:
            raise ValueError("invalid source record type")
        return normalized

    def _source_record_entity_type(self, source_type: str) -> str:
        if source_type == "task":
            return "task"
        if source_type == "leon_run":
            return "agent_run"
        if source_type == "calendar_event":
            return "workflow"
        return "document"

    def _source_record_excerpt(self, content: str, *, limit: int = 2000) -> str:
        excerpt = redact_text(content or "").strip()
        if len(excerpt) <= limit:
            return excerpt
        return excerpt[: limit - 3].rstrip() + "..."

    def _normalize_source_record_payload(self, raw: dict[str, Any]) -> dict[str, Any]:
        source_type = self._normalize_source_record_type(raw.get("source_type") or raw.get("type"))
        source_ref = str(raw.get("source_ref") or raw.get("path") or raw.get("ref") or "").strip()
        title = str(raw.get("title") or source_ref or source_type).strip()
        content = str(raw.get("content") or "").strip()
        metadata = raw.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise ValueError("source record metadata must be an object")
        if not source_ref:
            raise ValueError("source_ref is required")
        if not title:
            raise ValueError("source title is required")
        if not content:
            raise ValueError("source content is required")
        if len(source_ref) > 500:
            raise ValueError("source_ref must be 500 characters or fewer")
        if len(title) > 240:
            raise ValueError("source title must be 240 characters or fewer")
        _reject_secret_like_text("source_ref", source_ref)
        _reject_secret_like_text("source title", title)
        assert_no_secrets("source metadata", metadata)
        redacted_content = redact_text(content)
        scan = scan_value(content)
        return {
            "source_type": source_type,
            "source_ref": source_ref,
            "title": title,
            "redacted_content": redacted_content,
            "content_excerpt": self._source_record_excerpt(content),
            "content_hash": hashlib.sha256(redacted_content.encode("utf-8")).hexdigest(),
            "content_bytes": len(content.encode("utf-8")),
            "metadata": _redact_audit_value(metadata),
            "secret_scan": {
                "scanned": True,
                "has_findings": scan.has_findings,
                "finding_kinds": list(scan.kinds),
                "finding_count": scan.total,
                "raw_secret_values_stored": False,
            },
        }

    def _insert_source_graph_entries(
        self,
        conn: sqlite3.Connection,
        *,
        source_record: dict[str, Any],
        source_record_id: str,
        timestamp: str,
        audit_event_id: str | None,
    ) -> None:
        provenance = {
            "source": "local source ingestion",
            "source_record_id": source_record_id,
            "source_type": source_record["source_type"],
            "source_ref": source_record["source_ref"],
            "content_hash": source_record["content_hash"],
        }
        connector_id = str(source_record.get("metadata", {}).get("connector_id") or "").strip()
        connector_check_id = str(source_record.get("metadata", {}).get("connector_permission_check_id") or "").strip()
        if connector_id:
            provenance["source"] = "connector read ingestion"
            provenance["connector_id"] = connector_id
        if connector_check_id:
            provenance["connector_permission_check_id"] = connector_check_id
        source_entity_id = self._upsert_memory_graph_entity(
            conn,
            entity_type="source",
            label=source_record_id,
            source_memory_id=None,
            external_ref=source_record_id,
            provenance=provenance,
            confidence=0.9,
            timestamp=timestamp,
            audit_event_id=audit_event_id,
        )
        item_entity_id = self._upsert_memory_graph_entity(
            conn,
            entity_type=self._source_record_entity_type(source_record["source_type"]),
            label=source_record["title"],
            source_memory_id=None,
            external_ref=source_record["source_ref"],
            provenance=provenance,
            confidence=0.82,
            timestamp=timestamp,
            audit_event_id=audit_event_id,
        )
        self._insert_memory_graph_relationship(
            conn,
            relationship_type="derived_from",
            from_entity_id=item_entity_id,
            to_entity_id=source_entity_id,
            source_memory_id=None,
            label="ingested from source record",
            provenance=provenance,
            confidence=0.82,
            timestamp=timestamp,
            audit_event_id=audit_event_id,
        )

    def ingest_source_record(
        self,
        raw: dict[str, Any],
        *,
        block_on_secret: bool = True,
        actor_type: str = "system",
        actor_id: str = "source-ingestion",
    ) -> str:
        try:
            source_record = self._normalize_source_record_payload(raw)
        except SecretScanError as exc:
            self.record_secret_scan_failure(
                surface="source_ingestion",
                label=exc.label,
                finding_kinds=exc.result.kinds,
                finding_count=exc.result.total,
                actor_type=actor_type,
                actor_id=actor_id,
            )
            raise

        self.initialize()
        timestamp = now_iso()
        source_record_id = f"source-{uuid.uuid4().hex[:16]}"
        blocked = bool(block_on_secret and source_record["secret_scan"]["has_findings"])
        status = "blocked_secret" if blocked else "active"
        with self.connect() as conn:
            audit_event_id = self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="source_record_blocked" if blocked else "source_record_ingested",
                risk_level="high" if blocked else "low",
                summary=(
                    f"Source record {source_record_id} blocked due to credential-like content."
                    if blocked
                    else f"Source record {source_record_id} ingested."
                ),
                evidence="local source ingestion; content excerpt redacted and raw credential values are never stored in audit payload",
                redacted_payload={
                    "source_record_id": source_record_id,
                    "source_type": source_record["source_type"],
                    "source_ref": source_record["source_ref"],
                    "title": source_record["title"],
                    "status": status,
                    "content_hash": source_record["content_hash"],
                    "content_bytes": source_record["content_bytes"],
                    "secret_scan": source_record["secret_scan"],
                    "content_stored_in_audit": False,
                    "raw_secret_values_stored": False,
                },
                timestamp=timestamp,
            )
            conn.execute(
                """
                INSERT INTO source_records(
                  id, source_type, source_ref, title, status, content_hash,
                  content_excerpt, content_bytes, metadata_json, secret_scan_json,
                  audit_event_id, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_record_id,
                    source_record["source_type"],
                    source_record["source_ref"],
                    source_record["title"],
                    status,
                    "" if blocked else source_record["content_hash"],
                    "[blocked_secret]" if blocked else source_record["content_excerpt"],
                    source_record["content_bytes"],
                    json.dumps(source_record["metadata"], ensure_ascii=False, sort_keys=True),
                    json.dumps(source_record["secret_scan"], ensure_ascii=False, sort_keys=True),
                    audit_event_id,
                    timestamp,
                    timestamp,
                ),
            )
            if not blocked:
                self._insert_source_graph_entries(
                    conn,
                    source_record=source_record,
                    source_record_id=source_record_id,
                    timestamp=timestamp,
                    audit_event_id=audit_event_id,
                )
            self._insert_rollback_record(
                conn,
                kind="local_persistent",
                status="scrub_supported",
                risk_class="R2",
                action_ref_type="source_record",
                action_ref_id=source_record_id,
                target_type="source_record",
                target_ref=source_record_id,
                operation="scrub",
                summary="Source ingestion can be compensated by deleting or scrubbing the local source record and graph labels.",
                before_snapshot={},
                after_snapshot={
                    "id": source_record_id,
                    "source_type": source_record["source_type"],
                    "source_ref": source_record["source_ref"],
                    "title": source_record["title"],
                    "status": status,
                    "content_hash": "" if blocked else source_record["content_hash"],
                    "secret_scan": source_record["secret_scan"],
                },
                undo_payload={"delete_source_record_id": source_record_id, "scrub_graph_labels": True},
                deletion_supported=True,
                scrub_supported=True,
                audit_event_id=audit_event_id,
                timestamp=timestamp,
            )
        if blocked:
            self.record_secret_scan_failure(
                surface="source_ingestion",
                label=source_record["source_ref"],
                finding_kinds=source_record["secret_scan"]["finding_kinds"],
                finding_count=source_record["secret_scan"]["finding_count"],
                actor_type=actor_type,
                actor_id=actor_id,
            )
        return source_record_id

    def ingest_connector_read_context(
        self,
        *,
        connector_id: str,
        requested_scope: str,
        source_ref: str,
        title: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        present_env_keys: set[str] | None = None,
        approval_id: str | None = None,
        actor_type: str = "system",
        actor_id: str = "connector-read-ingestion",
    ) -> dict[str, Any]:
        from leon_control_plane.connector_registry import classify_connector_action

        connector_id = str(connector_id or "").strip()
        requested_scope = str(requested_scope or "").strip()
        if connector_id not in {"mail", "calendar"}:
            raise ValueError("connector read ingestion currently supports mail and calendar")
        if not requested_scope:
            raise ValueError("requested_scope is required")
        manifest = self.get_connector_manifest(connector_id)
        approval_status = self.get_approval_status(approval_id)
        check = classify_connector_action(
            manifest,
            action_type="read",
            requested_scope=requested_scope,
            present_env_keys=present_env_keys or set(),
            approval_id=approval_id,
            approval_status=approval_status,
        )
        check_id = self.record_connector_permission_check(
            check,
            actor_type=actor_type,
            actor_id=actor_id,
            connector_executed=check.get("decision") == "allowed",
            write_performed=False,
        )
        result = {
            "connector_id": connector_id,
            "requested_scope": requested_scope,
            "permission_check_id": check_id,
            "decision": check.get("decision"),
            "allowed": bool(check.get("allowed")),
            "source_record_id": "",
            "reason": check.get("reason") or "",
        }
        if check.get("decision") != "allowed":
            return result

        source_type = "mail_message" if connector_id == "mail" else "calendar_event"
        connector_metadata = dict(metadata or {})
        connector_metadata.update(
            {
                "connector_id": connector_id,
                "connector_type": manifest.get("connector_type"),
                "connector_read_scope": requested_scope,
                "connector_permission_check_id": check_id,
                "external_system": bool(manifest.get("external_system")),
                "source_backed_graph": True,
            }
        )
        source_record_id = self.ingest_source_record(
            {
                "source_type": source_type,
                "source_ref": source_ref,
                "title": title,
                "content": content,
                "metadata": connector_metadata,
            },
            block_on_secret=True,
            actor_type=actor_type,
            actor_id=actor_id,
        )
        result["source_record_id"] = source_record_id
        return result

    def ingest_local_file(
        self,
        source_ref: str | Path,
        *,
        source_type: str | None = None,
        title: str | None = None,
        actor_type: str = "system",
        actor_id: str = "source-ingestion",
    ) -> str:
        path = Path(source_ref)
        if not path.is_absolute():
            candidates = [Path.cwd() / path, self.seed_path.parent / path]
            path = next((candidate for candidate in candidates if candidate.exists()), candidates[0])
        if not path.exists() or not path.is_file():
            raise ValueError("source file does not exist")
        content = path.read_text(encoding="utf-8", errors="replace")
        inferred_type = source_type
        if inferred_type is None:
            inferred_type = "repo_doc" if path.suffix.lower() in {".md", ".rst", ".txt"} else "project_file"
        display_ref = str(source_ref)
        return self.ingest_source_record(
            {
                "source_type": inferred_type,
                "source_ref": display_ref,
                "title": title or path.name,
                "content": content,
                "metadata": {"path": display_ref, "ingested_from": "local_file"},
            },
            actor_type=actor_type,
            actor_id=actor_id,
        )

    def ingest_task_source(
        self,
        task_id: str,
        *,
        actor_type: str = "system",
        actor_id: str = "source-ingestion",
    ) -> str:
        task = self.get_task(task_id)
        content = "\n".join(
            part
            for part in [
                f"Title: {task['title']}",
                f"Goal: {task['goal']}",
                f"Status: {task['status']}",
                f"Priority: {task['priority']}",
                f"Acceptance: {task.get('acceptance_criteria') or task.get('acceptance') or ''}",
                f"Result: {task.get('result') or ''}",
                f"Sources: {', '.join(task.get('source_refs') or [])}",
            ]
            if part.strip()
        )
        return self.ingest_source_record(
            {
                "source_type": "task",
                "source_ref": task["id"],
                "title": task["title"],
                "content": content,
                "metadata": {"task_id": task["id"], "status": task["status"], "priority": task["priority"]},
            },
            actor_type=actor_type,
            actor_id=actor_id,
        )

    def ingest_leon_run_source(
        self,
        run_id: str,
        *,
        actor_type: str = "system",
        actor_id: str = "source-ingestion",
    ) -> str:
        state = self.get_state()
        run = next((item for item in state.get("agent_runs", []) if item.get("id") == run_id), None)
        run_kind = "agent_run"
        if run is None:
            run = next((item for item in state.get("night_queue_runs", []) if item.get("id") == run_id), None)
            run_kind = "night_queue_run"
        if run is None:
            raise ValueError("Unknown Leon run id")
        content = json.dumps(
            {
                "id": run.get("id"),
                "kind": run_kind,
                "status": run.get("status"),
                "summary": run.get("result_summary") or run.get("morning_brief", {}).get("summary") or "",
                "task_id": run.get("task_id"),
                "sources": run.get("input_sources") or run.get("sources") or [],
                "changes": run.get("changes") or [],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return self.ingest_source_record(
            {
                "source_type": "leon_run",
                "source_ref": str(run["id"]),
                "title": f"{run_kind}:{run['id']}",
                "content": content,
                "metadata": {"run_id": run["id"], "run_kind": run_kind, "status": run.get("status")},
            },
            actor_type=actor_type,
            actor_id=actor_id,
        )

    def ingest_project_knowledge(
        self,
        *,
        source_refs: list[str] | None = None,
        include_tasks: bool = True,
        include_previous_runs: bool = True,
        actor_type: str = "system",
        actor_id: str = "source-ingestion",
    ) -> dict[str, Any]:
        state = self.get_state()
        refs = list(source_refs or [])
        for task in state.get("tasks", []):
            refs.extend(str(ref) for ref in task.get("source_refs") or [])
        refs.extend(["tasks/prd.json", ".ralph-tui/progress.md", "state/control-plane.seed.json"])
        ingested: list[str] = []
        failures: list[dict[str, str]] = []
        for ref in _normalize_source_refs(refs):
            try:
                ingested.append(self.ingest_local_file(ref, actor_type=actor_type, actor_id=actor_id))
            except Exception as exc:
                failures.append({"source_ref": redact_audit_text(ref), "reason": redact_audit_text(str(exc))})
        if include_tasks:
            for task in state.get("tasks", []):
                try:
                    ingested.append(self.ingest_task_source(str(task["id"]), actor_type=actor_type, actor_id=actor_id))
                except Exception as exc:
                    failures.append({"source_ref": redact_audit_text(str(task.get("id"))), "reason": redact_audit_text(str(exc))})
        if include_previous_runs:
            for run in list(state.get("agent_runs", []))[:20] + list(state.get("night_queue_runs", []))[:20]:
                try:
                    ingested.append(self.ingest_leon_run_source(str(run["id"]), actor_type=actor_type, actor_id=actor_id))
                except Exception as exc:
                    failures.append({"source_ref": redact_audit_text(str(run.get("id"))), "reason": redact_audit_text(str(exc))})
        return {
            "status": "completed_with_attention" if failures else "succeeded",
            "ingested_source_record_ids": ingested,
            "failure_count": len(failures),
            "failures": failures,
        }

    def delete_source_record(
        self,
        source_record_id: str,
        *,
        reason: str,
        actor_type: str = "reviewer",
        actor_id: str = "source-ingestion",
    ) -> None:
        self._change_source_record_status(
            source_record_id,
            status="deleted",
            reason=reason,
            scrub=False,
            actor_type=actor_type,
            actor_id=actor_id,
        )

    def scrub_source_record(
        self,
        source_record_id: str,
        *,
        reason: str,
        actor_type: str = "reviewer",
        actor_id: str = "source-ingestion",
    ) -> None:
        self._change_source_record_status(
            source_record_id,
            status="scrubbed",
            reason=reason,
            scrub=True,
            actor_type=actor_type,
            actor_id=actor_id,
        )

    def _change_source_record_status(
        self,
        source_record_id: str,
        *,
        status: str,
        reason: str,
        scrub: bool,
        actor_type: str,
        actor_id: str,
    ) -> None:
        source_record_id = str(source_record_id or "").strip()
        reason = str(reason or "").strip()
        if status not in {"deleted", "scrubbed"}:
            raise ValueError("invalid source record terminal status")
        if not source_record_id:
            raise ValueError("source_record_id is required")
        if not reason:
            raise ValueError("source record delete/scrub requires a reason")
        _reject_secret_like_text("source record delete/scrub reason", reason)
        self.initialize()
        timestamp = now_iso()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM source_records WHERE id = ?", (source_record_id,)).fetchone()
            if row is None:
                raise ValueError("Unknown source record id")
            before_snapshot = dict(row)
            before_snapshot["metadata"] = _json_loads(before_snapshot.get("metadata_json"), {})
            before_snapshot["secret_scan"] = _json_loads(before_snapshot.get("secret_scan_json"), {})
            audit_event_id = self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="source_record_scrubbed" if scrub else "source_record_deleted",
                risk_level="low",
                summary=f"Source record {source_record_id} {status}.",
                evidence="local source index delete/scrub; content and graph labels are scrubbed according to operation",
                redacted_payload={
                    "source_record_id": source_record_id,
                    "old_status": row["status"],
                    "new_status": status,
                    "reason_present": True,
                    "content_scrubbed": True,
                    "graph_labels_scrubbed": scrub,
                    "content_stored_in_audit": False,
                },
                timestamp=timestamp,
            )
            after_snapshot = {
                "id": source_record_id,
                "status": status,
                "source_ref": "[scrubbed]" if scrub else row["source_ref"],
                "title": "[scrubbed]" if scrub else row["title"],
                "content_excerpt": "[scrubbed]" if scrub else "[deleted]",
                "deleted_at": timestamp,
            }
            self._insert_rollback_record(
                conn,
                kind="local_persistent",
                status="scrub_supported",
                risk_class="R2",
                action_ref_type="source_record",
                action_ref_id=source_record_id,
                target_type="source_record",
                target_ref=source_record_id,
                operation="scrub" if scrub else "delete",
                summary="Source index delete/scrub keeps a before snapshot for reviewed restore decisions.",
                before_snapshot=before_snapshot,
                after_snapshot=after_snapshot,
                undo_payload={"restore_requires_before_snapshot_review": True},
                deletion_supported=True,
                scrub_supported=True,
                audit_event_id=audit_event_id,
                timestamp=timestamp,
            )
            conn.execute(
                """
                UPDATE source_records
                SET status = ?, source_ref = ?, title = ?, content_hash = '',
                    content_excerpt = ?, metadata_json = '{}',
                    audit_event_id = ?, updated_at = ?, deleted_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    "[scrubbed]" if scrub else row["source_ref"],
                    "[scrubbed]" if scrub else row["title"],
                    "[scrubbed]" if scrub else "[deleted]",
                    audit_event_id,
                    timestamp,
                    timestamp,
                    source_record_id,
                ),
            )
            like = f"%{source_record_id}%"
            conn.execute(
                """
                UPDATE memory_graph_entities
                SET status = 'deleted',
                    label = CASE WHEN ? THEN '[scrubbed]' ELSE label END,
                    external_ref = CASE WHEN ? THEN '' ELSE external_ref END,
                    updated_at = ?, deleted_at = ?
                WHERE (external_ref = ? OR provenance_json LIKE ?) AND status != 'deleted'
                """,
                (int(scrub), int(scrub), timestamp, timestamp, source_record_id, like),
            )
            conn.execute(
                """
                UPDATE memory_graph_relationships
                SET status = 'deleted',
                    label = CASE WHEN ? THEN '[scrubbed]' ELSE label END,
                    updated_at = ?, deleted_at = ?
                WHERE provenance_json LIKE ? AND status != 'deleted'
                """,
                (int(scrub), timestamp, timestamp, like),
            )

    def _normalize_graph_entity_payloads(self, raw_entities: Any) -> tuple[list[dict[str, Any]], list[str]]:
        if isinstance(raw_entities, str):
            raw_entities = [part.strip() for part in raw_entities.split(",")]
        if raw_entities in (None, ""):
            raw_entities = []
        if not isinstance(raw_entities, list):
            raise ValueError("graph_entities must be a list or comma-separated string")
        entities: list[dict[str, Any]] = []
        labels: list[str] = []
        for item in raw_entities:
            if isinstance(item, dict):
                label = str(item.get("label") or item.get("name") or "").strip()
                entity_type = _normalize_graph_entity_type(item.get("entity_type") or item.get("type") or "memory")
                external_ref = str(item.get("external_ref") or "").strip()
                confidence = _normalize_confidence(item.get("confidence", 0.5))
            else:
                label = str(item).strip()
                entity_type = "memory"
                external_ref = ""
                confidence = 0.5
            if not label:
                continue
            if len(label) > 120:
                raise ValueError("graph entity labels must be 120 characters or fewer")
            if len(external_ref) > 240:
                raise ValueError("graph entity external_ref must be 240 characters or fewer")
            _reject_unsafe_memory_text("graph entity", label)
            _reject_unsafe_memory_text("graph entity external_ref", external_ref)
            entity = {
                "entity_type": entity_type,
                "label": label,
                "external_ref": external_ref,
                "confidence": confidence,
            }
            if entity not in entities:
                entities.append(entity)
            if label not in labels:
                labels.append(label)
        return entities, labels

    def _normalize_memory_payload(self, raw: dict[str, Any], *, existing_review_note: str = "") -> dict[str, Any]:
        content = str(raw.get("content") or "").strip()
        if not content:
            raise ValueError("memory content is required")
        if len(content) > 2000:
            raise ValueError("memory content must be 2000 characters or fewer")
        _reject_unsafe_memory_text("memory content", content)

        memory_type = str(raw.get("memory_type") or "working").strip()
        status = str(raw.get("status") or "candidate").strip()
        sensitivity = str(raw.get("sensitivity") or "medium").strip()
        privacy_level = str(raw.get("privacy_level") or "private").strip()
        if memory_type not in MEMORY_TYPES:
            raise ValueError("invalid memory_type")
        if status not in MEMORY_STATUSES:
            raise ValueError("invalid memory status")
        if sensitivity not in MEMORY_SENSITIVITY_LEVELS:
            raise ValueError("invalid sensitivity")
        if privacy_level not in MEMORY_PRIVACY_LEVELS:
            raise ValueError("invalid privacy_level")

        source = str(raw.get("source") or "").strip()
        if not source:
            raise ValueError("memory source is required")
        if len(source) > 400:
            raise ValueError("memory source must be 400 characters or fewer")
        _reject_unsafe_memory_text("memory source", source)

        review_note = str(raw.get("review_note") or existing_review_note or "").strip()
        _reject_unsafe_memory_text("memory review_note", review_note)
        if status == "active" and (memory_type == "long_term" or sensitivity == "high" or privacy_level == "sensitive"):
            if not review_note:
                raise ValueError("active long-term or sensitive memory requires a review_note")

        source_task_id = str(raw.get("source_task_id") or "").strip() or None
        correction_of = str(raw.get("correction_of") or "").strip() or None
        expires_at = str(raw.get("expires_at") or "").strip() or None
        graph_entity_records, graph_entities = self._normalize_graph_entity_payloads(raw.get("graph_entities") or [])

        conflict_status = str(raw.get("conflict_status") or "none").strip()
        if conflict_status not in MEMORY_CONFLICT_STATUSES:
            raise ValueError("invalid memory conflict_status")
        conflict_note = str(raw.get("conflict_note") or "").strip()
        _reject_unsafe_memory_text("memory conflict_note", conflict_note)
        conflict_memory_ids_raw = raw.get("conflict_memory_ids") or []
        if isinstance(conflict_memory_ids_raw, str):
            conflict_memory_ids_raw = [part.strip() for part in conflict_memory_ids_raw.split(",")]
        if not isinstance(conflict_memory_ids_raw, list):
            raise ValueError("conflict_memory_ids must be a list or comma-separated string")
        conflict_memory_ids = []
        for item in conflict_memory_ids_raw:
            conflict_id = str(item).strip()
            if conflict_id and conflict_id not in conflict_memory_ids:
                conflict_memory_ids.append(conflict_id)
        if conflict_memory_ids and conflict_status == "none":
            conflict_status = "conflicted"

        return {
            "status": status,
            "memory_type": memory_type,
            "content": content,
            "source": source,
            "source_task_id": source_task_id,
            "confidence": _normalize_confidence(raw.get("confidence", 0.5)),
            "sensitivity": sensitivity,
            "privacy_level": privacy_level,
            "expires_at": expires_at,
            "review_note": review_note,
            "correction_of": correction_of,
            "graph_entities": graph_entities,
            "graph_entity_records": graph_entity_records,
            "provenance": self._normalize_memory_provenance(raw, source=source, source_task_id=source_task_id),
            "conflict_status": conflict_status,
            "conflict_memory_ids": conflict_memory_ids,
            "conflict_note": conflict_note,
        }

    def create_memory_item(
        self,
        raw: dict[str, Any],
        *,
        actor_type: str = "reviewer",
        actor_id: str = "memory-mvp",
    ) -> str:
        try:
            memory = self._normalize_memory_payload(raw)
        except SecretScanError as exc:
            self.record_secret_scan_failure(
                surface="memory_write",
                label=exc.label,
                finding_kinds=exc.result.kinds,
                finding_count=exc.result.total,
                actor_type=actor_type,
                actor_id=actor_id,
            )
            raise
        graph_edges = raw.get("graph_edges") or []
        if not isinstance(graph_edges, list):
            raise ValueError("graph_edges must be a list")
        try:
            assert_no_secrets("memory graph_edges", graph_edges)
        except SecretScanError as exc:
            self.record_secret_scan_failure(
                surface="memory_graph_write",
                label=exc.label,
                finding_kinds=exc.result.kinds,
                finding_count=exc.result.total,
                actor_type=actor_type,
                actor_id=actor_id,
            )
            raise

        self.initialize()
        timestamp = now_iso()
        memory_id = f"memory-{uuid.uuid4().hex[:16]}"
        with self.connect() as conn:
            if memory["source_task_id"] and conn.execute("SELECT id FROM tasks WHERE id = ?", (memory["source_task_id"],)).fetchone() is None:
                raise ValueError("source_task_id must refer to an existing task")
            if memory["correction_of"] and conn.execute("SELECT id FROM memory_items WHERE id = ?", (memory["correction_of"],)).fetchone() is None:
                raise ValueError("correction_of must refer to an existing memory item")
            for conflict_memory_id in memory["conflict_memory_ids"]:
                if conn.execute("SELECT id FROM memory_items WHERE id = ?", (conflict_memory_id,)).fetchone() is None:
                    raise ValueError("conflict_memory_ids must refer to existing memory items")
            audit_event_id = self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="memory_item_corrected" if memory["correction_of"] else "memory_item_created",
                task_id=memory["source_task_id"],
                risk_level="medium" if memory["sensitivity"] != "low" else "low",
                summary=(
                    f"Memory item {memory_id} created as a correction for {memory['correction_of']}."
                    if memory["correction_of"]
                    else f"Memory item {memory_id} created as {memory['status']}."
                ),
                evidence="local memory MVP; source, confidence, sensitivity, expiry and graph metadata recorded; content omitted from audit payload",
                redacted_payload={
                    "memory_id": memory_id,
                    "status": memory["status"],
                    "memory_type": memory["memory_type"],
                    "confidence": memory["confidence"],
                    "correction_of": memory["correction_of"],
                    "supersedes_older_entry": bool(memory["correction_of"]),
                    "sensitivity": memory["sensitivity"],
                    "privacy_level": memory["privacy_level"],
                    "has_expiry": bool(memory["expires_at"]),
                    "source_present": True,
                    "graph_entity_count": len(memory["graph_entities"]),
                    "graph_edge_count": len(graph_edges),
                    "content_stored_in_audit": False,
                    "raw_secret_values_stored": False,
                },
                timestamp=timestamp,
            )
            conn.execute(
                """
                INSERT INTO memory_items(
                  id, status, memory_type, content, source, source_task_id,
                  confidence, sensitivity, privacy_level, expires_at, review_note,
                  correction_of, graph_entities_json, provenance_json,
                  conflict_status, conflict_memory_ids_json, conflict_note,
                  audit_event_id, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    memory["status"],
                    memory["memory_type"],
                    memory["content"],
                    memory["source"],
                    memory["source_task_id"],
                    memory["confidence"],
                    memory["sensitivity"],
                    memory["privacy_level"],
                    memory["expires_at"],
                    memory["review_note"],
                    memory["correction_of"],
                    json.dumps(memory["graph_entities"], ensure_ascii=False, sort_keys=True),
                    json.dumps(memory["provenance"], ensure_ascii=False, sort_keys=True),
                    memory["conflict_status"],
                    json.dumps(memory["conflict_memory_ids"], ensure_ascii=False, sort_keys=True),
                    memory["conflict_note"],
                    audit_event_id,
                    timestamp,
                    timestamp,
                ),
            )
            memory_entity_id = self._upsert_memory_graph_entity(
                conn,
                entity_type="memory",
                label=memory_id,
                source_memory_id=memory_id,
                provenance=memory["provenance"],
                confidence=memory["confidence"],
                timestamp=timestamp,
                audit_event_id=audit_event_id,
            )
            if memory["correction_of"]:
                self._insert_memory_supersedes_relationship(
                    conn,
                    memory_id=memory_id,
                    superseded_memory_id=memory["correction_of"],
                    provenance=memory["provenance"],
                    confidence=memory["confidence"],
                    timestamp=timestamp,
                    audit_event_id=audit_event_id,
                )
                if memory["status"] == "active":
                    self._mark_superseded_memory(
                        conn,
                        superseded_memory_id=memory["correction_of"],
                        superseded_by_memory_id=memory_id,
                        timestamp=timestamp,
                        audit_event_id=audit_event_id,
                    )
            for entity in memory["graph_entity_records"]:
                entity_id = self._upsert_memory_graph_entity(
                    conn,
                    entity_type=entity["entity_type"],
                    label=entity["label"],
                    source_memory_id=memory_id,
                    external_ref=entity["external_ref"],
                    provenance=memory["provenance"],
                    confidence=entity["confidence"],
                    timestamp=timestamp,
                    audit_event_id=audit_event_id,
                )
                self._insert_memory_graph_relationship(
                    conn,
                    relationship_type="mentions",
                    from_entity_id=memory_entity_id,
                    to_entity_id=entity_id,
                    source_memory_id=memory_id,
                    label="memory mentions graph entity",
                    provenance=memory["provenance"],
                    confidence=min(memory["confidence"], entity["confidence"]),
                    timestamp=timestamp,
                    audit_event_id=audit_event_id,
                )
            for conflict_memory_id in memory["conflict_memory_ids"]:
                conflict_entity_id = self._upsert_memory_graph_entity(
                    conn,
                    entity_type="memory",
                    label=conflict_memory_id,
                    source_memory_id=conflict_memory_id,
                    provenance={"source": "memory conflict marker", "marked_by": memory_id},
                    confidence=memory["confidence"],
                    timestamp=timestamp,
                    audit_event_id=audit_event_id,
                )
                self._insert_memory_graph_relationship(
                    conn,
                    relationship_type="conflicts_with",
                    from_entity_id=memory_entity_id,
                    to_entity_id=conflict_entity_id,
                    source_memory_id=memory_id,
                    label=memory["conflict_note"] or "memory conflict marker",
                    provenance=memory["provenance"],
                    confidence=memory["confidence"],
                    timestamp=timestamp,
                    audit_event_id=audit_event_id,
                )
            for edge in graph_edges:
                self._insert_memory_graph_edge(conn, memory_id, edge, timestamp, actor_type=actor_type, actor_id=actor_id)
            self._insert_rollback_record(
                conn,
                kind="local_persistent",
                status="scrub_supported",
                risk_class="R2",
                task_id=memory["source_task_id"],
                action_ref_type="memory",
                action_ref_id=memory_id,
                target_type="memory_item",
                target_ref=memory_id,
                operation="scrub",
                summary="Memory creation can be compensated by deleting or scrubbing the local memory item and graph labels.",
                before_snapshot={},
                after_snapshot={
                    **memory,
                    "id": memory_id,
                    "content_stored_locally": True,
                    "graph_edge_count": len(graph_edges),
                },
                undo_payload={"delete_memory_item_id": memory_id, "scrub_content": True},
                deletion_supported=True,
                scrub_supported=True,
                audit_event_id=audit_event_id,
                timestamp=timestamp,
            )
        return memory_id

    def _upsert_memory_graph_entity(
        self,
        conn: sqlite3.Connection,
        *,
        entity_type: str,
        label: str,
        source_memory_id: str | None,
        provenance: dict[str, Any],
        confidence: float,
        timestamp: str,
        audit_event_id: str | None,
        external_ref: str = "",
    ) -> str:
        entity_type = _normalize_graph_entity_type(entity_type)
        label = str(label or "").strip()
        external_ref = str(external_ref or "").strip()
        if not label:
            raise ValueError("graph entity label is required")
        if len(label) > 200:
            raise ValueError("graph entity label must be 200 characters or fewer")
        if len(external_ref) > 240:
            raise ValueError("graph entity external_ref must be 240 characters or fewer")
        _reject_unsafe_memory_text("graph entity label", label)
        _reject_unsafe_memory_text("graph entity external_ref", external_ref)
        assert_no_secrets("graph entity provenance", provenance)
        existing = conn.execute(
            """
            SELECT id FROM memory_graph_entities
            WHERE entity_type = ? AND label = ? AND external_ref = ?
              AND COALESCE(source_memory_id, '') = COALESCE(?, '')
              AND status != 'deleted'
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (entity_type, label, external_ref, source_memory_id),
        ).fetchone()
        if existing:
            entity_id = str(existing["id"])
            conn.execute(
                """
                UPDATE memory_graph_entities
                SET provenance_json = ?, confidence = ?, audit_event_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    json.dumps(_redact_audit_value(provenance), ensure_ascii=False, sort_keys=True),
                    _normalize_confidence(confidence),
                    audit_event_id,
                    timestamp,
                    entity_id,
                ),
            )
            return entity_id
        entity_id = f"graph-entity-{uuid.uuid4().hex[:16]}"
        conn.execute(
            """
            INSERT INTO memory_graph_entities(
              id, entity_type, label, source_memory_id, external_ref, provenance_json,
              confidence, status, audit_event_id, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
            """,
            (
                entity_id,
                entity_type,
                label,
                source_memory_id,
                external_ref,
                json.dumps(_redact_audit_value(provenance), ensure_ascii=False, sort_keys=True),
                _normalize_confidence(confidence),
                audit_event_id,
                timestamp,
                timestamp,
            ),
        )
        return entity_id

    def _insert_memory_graph_relationship(
        self,
        conn: sqlite3.Connection,
        *,
        relationship_type: str,
        from_entity_id: str,
        to_entity_id: str,
        source_memory_id: str | None,
        label: str,
        provenance: dict[str, Any],
        confidence: float,
        timestamp: str,
        audit_event_id: str | None,
    ) -> str:
        relationship_type = _normalize_graph_relationship_type(relationship_type)
        label = str(label or relationship_type).strip()
        if len(label) > 240:
            raise ValueError("graph relationship label must be 240 characters or fewer")
        _reject_unsafe_memory_text("graph relationship label", label)
        assert_no_secrets("graph relationship provenance", provenance)
        relationship_id = f"graph-rel-{uuid.uuid4().hex[:16]}"
        conn.execute(
            """
            INSERT INTO memory_graph_relationships(
              id, relationship_type, from_entity_id, to_entity_id, source_memory_id,
              label, provenance_json, confidence, status, audit_event_id,
              created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
            """,
            (
                relationship_id,
                relationship_type,
                from_entity_id,
                to_entity_id,
                source_memory_id,
                label,
                json.dumps(_redact_audit_value(provenance), ensure_ascii=False, sort_keys=True),
                _normalize_confidence(confidence),
                audit_event_id,
                timestamp,
                timestamp,
            ),
        )
        return relationship_id

    def _insert_memory_supersedes_relationship(
        self,
        conn: sqlite3.Connection,
        *,
        memory_id: str,
        superseded_memory_id: str,
        provenance: dict[str, Any],
        confidence: float,
        timestamp: str,
        audit_event_id: str | None,
    ) -> None:
        memory_entity_id = self._upsert_memory_graph_entity(
            conn,
            entity_type="memory",
            label=memory_id,
            source_memory_id=memory_id,
            provenance=provenance,
            confidence=confidence,
            timestamp=timestamp,
            audit_event_id=audit_event_id,
        )
        superseded_entity_id = self._upsert_memory_graph_entity(
            conn,
            entity_type="memory",
            label=superseded_memory_id,
            source_memory_id=superseded_memory_id,
            provenance={"source": "memory correction", "superseded_by": memory_id},
            confidence=confidence,
            timestamp=timestamp,
            audit_event_id=audit_event_id,
        )
        self._insert_memory_graph_relationship(
            conn,
            relationship_type="supersedes",
            from_entity_id=memory_entity_id,
            to_entity_id=superseded_entity_id,
            source_memory_id=memory_id,
            label="memory correction supersedes older memory",
            provenance={**provenance, "correction_of": superseded_memory_id},
            confidence=confidence,
            timestamp=timestamp,
            audit_event_id=audit_event_id,
        )

    def _mark_superseded_memory(
        self,
        conn: sqlite3.Connection,
        *,
        superseded_memory_id: str,
        superseded_by_memory_id: str,
        timestamp: str,
        audit_event_id: str | None,
    ) -> None:
        conn.execute(
            """
            UPDATE memory_items
            SET status = 'rejected',
                review_note = ?,
                audit_event_id = ?,
                updated_at = ?
            WHERE id = ?
              AND status IN ('candidate', 'active')
            """,
            (
                f"Superseded by correction {superseded_by_memory_id}.",
                audit_event_id,
                timestamp,
                superseded_memory_id,
            ),
        )

    def _insert_memory_graph_edge(
        self,
        conn: sqlite3.Connection,
        memory_id: str,
        raw_edge: dict[str, Any],
        timestamp: str,
        *,
        actor_type: str,
        actor_id: str,
    ) -> str:
        subject = str(raw_edge.get("subject") or "").strip()
        predicate = str(raw_edge.get("predicate") or "").strip()
        obj = str(raw_edge.get("object") or raw_edge.get("object_value") or "").strip()
        source = str(raw_edge.get("source") or "memory_item").strip()
        relationship_type = _normalize_graph_relationship_type(
            raw_edge.get("relationship_type")
            or raw_edge.get("type")
            or (predicate if predicate in GRAPH_RELATIONSHIP_TYPES else "related_to")
        )
        for label, value in {"subject": subject, "predicate": predicate, "object": obj, "source": source}.items():
            if not value:
                raise ValueError(f"graph edge {label} is required")
            if len(value) > 200:
                raise ValueError(f"graph edge {label} must be 200 characters or fewer")
            _reject_unsafe_memory_text(f"graph edge {label}", value)
        confidence = _normalize_confidence(raw_edge.get("confidence", 0.5))
        edge_id = f"memory-edge-{uuid.uuid4().hex[:16]}"
        audit_event_id = self.append_audit_event(
            conn,
            actor_type=actor_type,
            actor_id=actor_id,
            event_type="memory_graph_edge_created",
            risk_level="low",
            summary=f"Memory graph edge {edge_id} created.",
            evidence="local memory graph MVP; edge labels only, no secret values",
            redacted_payload={
                "edge_id": edge_id,
                "source_memory_id": memory_id,
                "predicate": predicate,
                "relationship_type": relationship_type,
                "confidence": confidence,
                "raw_secret_values_stored": False,
            },
            timestamp=timestamp,
        )
        provenance = {"source": source, "source_memory_id": memory_id}
        from_entity_id = self._upsert_memory_graph_entity(
            conn,
            entity_type=raw_edge.get("subject_entity_type") or "memory",
            label=subject,
            source_memory_id=memory_id,
            provenance=provenance,
            confidence=confidence,
            timestamp=timestamp,
            audit_event_id=audit_event_id,
            external_ref=str(raw_edge.get("subject_ref") or "").strip(),
        )
        to_entity_id = self._upsert_memory_graph_entity(
            conn,
            entity_type=raw_edge.get("object_entity_type") or "memory",
            label=obj,
            source_memory_id=memory_id,
            provenance=provenance,
            confidence=confidence,
            timestamp=timestamp,
            audit_event_id=audit_event_id,
            external_ref=str(raw_edge.get("object_ref") or "").strip(),
        )
        self._insert_memory_graph_relationship(
            conn,
            relationship_type=relationship_type,
            from_entity_id=from_entity_id,
            to_entity_id=to_entity_id,
            source_memory_id=memory_id,
            label=predicate,
            provenance=provenance,
            confidence=confidence,
            timestamp=timestamp,
            audit_event_id=audit_event_id,
        )
        conn.execute(
            """
            INSERT INTO memory_graph_edges(
              id, source_memory_id, subject, predicate, object, relationship_type, confidence,
              source, status, audit_event_id, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
            """,
            (edge_id, memory_id, subject, predicate, obj, relationship_type, confidence, source, audit_event_id, timestamp, timestamp),
        )
        return edge_id

    def create_memory_graph_edge(
        self,
        raw_edge: dict[str, Any],
        *,
        actor_type: str = "reviewer",
        actor_id: str = "memory-mvp",
    ) -> str:
        try:
            assert_no_secrets("memory graph edge", raw_edge)
        except SecretScanError as exc:
            self.record_secret_scan_failure(
                surface="memory_graph_write",
                label=exc.label,
                finding_kinds=exc.result.kinds,
                finding_count=exc.result.total,
                actor_type=actor_type,
                actor_id=actor_id,
            )
            raise
        memory_id = str(raw_edge.get("source_memory_id") or "").strip()
        if not memory_id:
            raise ValueError("source_memory_id is required")
        self.initialize()
        timestamp = now_iso()
        with self.connect() as conn:
            if conn.execute("SELECT id FROM memory_items WHERE id = ?", (memory_id,)).fetchone() is None:
                raise ValueError("source_memory_id must refer to an existing memory item")
            return self._insert_memory_graph_edge(conn, memory_id, raw_edge, timestamp, actor_type=actor_type, actor_id=actor_id)

    def update_memory_item(
        self,
        memory_id: str,
        updates: dict[str, Any],
        *,
        actor_type: str = "reviewer",
        actor_id: str = "memory-mvp",
    ) -> None:
        memory_id = str(memory_id or "").strip()
        if not memory_id:
            raise ValueError("memory id is required")
        try:
            assert_no_secrets("memory updates", updates)
        except SecretScanError as exc:
            self.record_secret_scan_failure(
                surface="memory_write",
                label=exc.label,
                finding_kinds=exc.result.kinds,
                finding_count=exc.result.total,
                actor_type=actor_type,
                actor_id=actor_id,
            )
            raise
        self.initialize()
        timestamp = now_iso()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM memory_items WHERE id = ?", (memory_id,)).fetchone()
            if row is None:
                raise ValueError("Unknown memory item id")
            current = dict(row)
            merged = {
                "content": current["content"],
                "memory_type": current["memory_type"],
                "status": current["status"],
                "source": current["source"],
                "source_task_id": current["source_task_id"],
                "confidence": current["confidence"],
                "sensitivity": current["sensitivity"],
                "privacy_level": current["privacy_level"],
                "expires_at": current["expires_at"],
                "review_note": current["review_note"],
                "correction_of": current["correction_of"],
                "graph_entities": json.loads(current.get("graph_entities_json") or "[]"),
                "provenance": _json_loads(current.get("provenance_json"), {}),
                "conflict_status": current.get("conflict_status") or "none",
                "conflict_memory_ids": _json_loads(current.get("conflict_memory_ids_json"), []),
                "conflict_note": current.get("conflict_note") or "",
            }
            merged.update({key: value for key, value in updates.items() if key in merged or key == "status"})
            memory = self._normalize_memory_payload(merged, existing_review_note=current["review_note"])
            if memory["status"] in {"deleted", "scrubbed"} and current["status"] != memory["status"]:
                raise ValueError("use the memory delete or scrub action for terminal memory changes")
            if memory["source_task_id"] and conn.execute("SELECT id FROM tasks WHERE id = ?", (memory["source_task_id"],)).fetchone() is None:
                raise ValueError("source_task_id must refer to an existing task")
            if memory["correction_of"] == memory_id:
                raise ValueError("correction_of cannot refer to the same memory item")
            if memory["correction_of"] and conn.execute("SELECT id FROM memory_items WHERE id = ?", (memory["correction_of"],)).fetchone() is None:
                raise ValueError("correction_of must refer to an existing memory item")
            for conflict_memory_id in memory["conflict_memory_ids"]:
                if conn.execute("SELECT id FROM memory_items WHERE id = ?", (conflict_memory_id,)).fetchone() is None:
                    raise ValueError("conflict_memory_ids must refer to existing memory items")
            is_correction = any(key in updates for key in ("confidence", "content", "correction_of", "conflict_memory_ids", "conflict_note"))
            audit_event_id = self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="memory_item_corrected" if is_correction else "memory_item_updated",
                task_id=memory["source_task_id"],
                risk_level="medium" if memory["sensitivity"] != "low" else "low",
                summary=(
                    f"Memory item {memory_id} corrected."
                    if is_correction
                    else f"Memory item {memory_id} updated to {memory['status']}."
                ),
                evidence="local memory MVP update; content omitted from audit payload",
                redacted_payload={
                    "memory_id": memory_id,
                    "old_status": current["status"],
                    "new_status": memory["status"],
                    "memory_type": memory["memory_type"],
                    "old_confidence": current["confidence"],
                    "confidence": memory["confidence"],
                    "correction_of": memory["correction_of"],
                    "supersedes_older_entry": bool(memory["correction_of"]),
                    "sensitivity": memory["sensitivity"],
                    "privacy_level": memory["privacy_level"],
                    "has_review_note": bool(memory["review_note"]),
                    "conflict_status": memory["conflict_status"],
                    "conflict_count": len(memory["conflict_memory_ids"]),
                    "content_stored_in_audit": False,
                    "raw_secret_values_stored": False,
                },
                timestamp=timestamp,
            )
            self._insert_rollback_record(
                conn,
                kind="local_persistent",
                status="undo_supported",
                risk_class="R2",
                task_id=memory["source_task_id"],
                action_ref_type="memory",
                action_ref_id=memory_id,
                target_type="memory_item",
                target_ref=memory_id,
                operation="undo",
                summary="Memory update stores before/after snapshots so the prior local record can be restored or scrubbed.",
                before_snapshot={
                    "id": memory_id,
                    "status": current["status"],
                    "memory_type": current["memory_type"],
                    "content": current["content"],
                    "source": current["source"],
                    "source_task_id": current["source_task_id"],
                    "confidence": current["confidence"],
                    "sensitivity": current["sensitivity"],
                    "privacy_level": current["privacy_level"],
                    "expires_at": current["expires_at"],
                    "review_note": current["review_note"],
                    "correction_of": current["correction_of"],
                    "graph_entities": json.loads(current.get("graph_entities_json") or "[]"),
                    "provenance": _json_loads(current.get("provenance_json"), {}),
                    "conflict_status": current.get("conflict_status") or "none",
                    "conflict_memory_ids": _json_loads(current.get("conflict_memory_ids_json"), []),
                    "conflict_note": current.get("conflict_note") or "",
                },
                after_snapshot={**memory, "id": memory_id},
                undo_payload={"restore_memory_item_id": memory_id, "snapshot": "before_snapshot"},
                undo_supported=True,
                deletion_supported=True,
                scrub_supported=True,
                audit_event_id=audit_event_id,
                timestamp=timestamp,
            )
            conn.execute(
                """
                UPDATE memory_items
                SET status = ?, memory_type = ?, content = ?, source = ?,
                    source_task_id = ?, confidence = ?, sensitivity = ?,
                    privacy_level = ?, expires_at = ?, review_note = ?,
                    correction_of = ?, graph_entities_json = ?, provenance_json = ?,
                    conflict_status = ?, conflict_memory_ids_json = ?, conflict_note = ?,
                    audit_event_id = ?, updated_at = ?,
                    deleted_at = CASE WHEN ? = 'deleted' THEN ? ELSE deleted_at END
                WHERE id = ?
                """,
                (
                    memory["status"],
                    memory["memory_type"],
                    memory["content"],
                    memory["source"],
                    memory["source_task_id"],
                    memory["confidence"],
                    memory["sensitivity"],
                    memory["privacy_level"],
                    memory["expires_at"],
                    memory["review_note"],
                    memory["correction_of"],
                    json.dumps(memory["graph_entities"], ensure_ascii=False, sort_keys=True),
                    json.dumps(memory["provenance"], ensure_ascii=False, sort_keys=True),
                    memory["conflict_status"],
                    json.dumps(memory["conflict_memory_ids"], ensure_ascii=False, sort_keys=True),
                    memory["conflict_note"],
                    audit_event_id,
                    timestamp,
                    memory["status"],
                    timestamp,
                    memory_id,
                ),
            )
            if memory["correction_of"]:
                self._insert_memory_supersedes_relationship(
                    conn,
                    memory_id=memory_id,
                    superseded_memory_id=memory["correction_of"],
                    provenance=memory["provenance"],
                    confidence=memory["confidence"],
                    timestamp=timestamp,
                    audit_event_id=audit_event_id,
                )
                if memory["status"] == "active":
                    self._mark_superseded_memory(
                        conn,
                        superseded_memory_id=memory["correction_of"],
                        superseded_by_memory_id=memory_id,
                        timestamp=timestamp,
                        audit_event_id=audit_event_id,
                    )
            if memory["conflict_memory_ids"]:
                memory_entity_id = self._upsert_memory_graph_entity(
                    conn,
                    entity_type="memory",
                    label=memory_id,
                    source_memory_id=memory_id,
                    provenance=memory["provenance"],
                    confidence=memory["confidence"],
                    timestamp=timestamp,
                    audit_event_id=audit_event_id,
                )
                for conflict_memory_id in memory["conflict_memory_ids"]:
                    conflict_entity_id = self._upsert_memory_graph_entity(
                        conn,
                        entity_type="memory",
                        label=conflict_memory_id,
                        source_memory_id=conflict_memory_id,
                        provenance={"source": "memory conflict marker", "marked_by": memory_id},
                        confidence=memory["confidence"],
                        timestamp=timestamp,
                        audit_event_id=audit_event_id,
                    )
                    self._insert_memory_graph_relationship(
                        conn,
                        relationship_type="conflicts_with",
                        from_entity_id=memory_entity_id,
                        to_entity_id=conflict_entity_id,
                        source_memory_id=memory_id,
                        label=memory["conflict_note"] or "memory conflict marker",
                        provenance=memory["provenance"],
                        confidence=memory["confidence"],
                        timestamp=timestamp,
                        audit_event_id=audit_event_id,
                    )

    def delete_memory_item(
        self,
        memory_id: str,
        *,
        reason: str,
        actor_type: str = "reviewer",
        actor_id: str = "memory-mvp",
    ) -> None:
        self._change_memory_item_terminal_status(
            memory_id,
            reason=reason,
            status="deleted",
            content_marker="[deleted]",
            actor_type=actor_type,
            actor_id=actor_id,
        )

    def scrub_memory_item(
        self,
        memory_id: str,
        *,
        reason: str,
        actor_type: str = "reviewer",
        actor_id: str = "memory-mvp",
    ) -> None:
        self._change_memory_item_terminal_status(
            memory_id,
            reason=reason,
            status="scrubbed",
            content_marker="[scrubbed]",
            actor_type=actor_type,
            actor_id=actor_id,
        )

    def _change_memory_item_terminal_status(
        self,
        memory_id: str,
        *,
        reason: str,
        status: str,
        content_marker: str,
        actor_type: str,
        actor_id: str,
    ) -> None:
        if status not in {"deleted", "scrubbed"}:
            raise ValueError("invalid terminal memory status")
        memory_id = str(memory_id or "").strip()
        if not memory_id:
            raise ValueError("memory id is required")
        reason = str(reason or "").strip()
        if not reason:
            raise ValueError("memory delete/scrub requires a reason")
        try:
            _reject_unsafe_memory_text("memory delete/scrub reason", reason)
        except SecretScanError as exc:
            self.record_secret_scan_failure(
                surface="memory_write",
                label=exc.label,
                finding_kinds=exc.result.kinds,
                finding_count=exc.result.total,
                actor_type=actor_type,
                actor_id=actor_id,
            )
            raise
        self.initialize()
        timestamp = now_iso()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM memory_items WHERE id = ?", (memory_id,)).fetchone()
            if row is None:
                raise ValueError("Unknown memory item id")
            before_snapshot = dict(row)
            before_snapshot["graph_entities"] = _json_loads(before_snapshot.get("graph_entities_json"), [])
            audit_event_id = self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="memory_item_scrubbed" if status == "scrubbed" else "memory_item_deleted",
                task_id=row["source_task_id"],
                risk_level="low",
                summary=f"Memory item {memory_id} {status}.",
                evidence="local memory MVP delete/scrub; item content and graph labels scrubbed while redacted audit metadata remains append-only",
                redacted_payload={
                    "memory_id": memory_id,
                    "old_status": row["status"],
                    "new_status": status,
                    "reason_present": True,
                    "content_scrubbed": True,
                    "graph_labels_scrubbed": True,
                    "content_stored_in_audit": False,
                },
                timestamp=timestamp,
            )
            self._insert_rollback_record(
                conn,
                kind="local_persistent",
                status="scrub_supported",
                risk_class="R2",
                task_id=row["source_task_id"],
                action_ref_type="memory",
                action_ref_id=memory_id,
                target_type="memory_item",
                target_ref=memory_id,
                operation="scrub" if status == "scrubbed" else "delete",
                summary="Memory delete/scrub scrubbed local content and graph labels while retaining a before snapshot for reviewed restore decisions.",
                before_snapshot=before_snapshot,
                after_snapshot={
                    "id": memory_id,
                    "status": status,
                    "content": content_marker,
                    "graph_entities": [],
                    "deleted_at": timestamp,
                },
                undo_payload={"restore_requires_before_snapshot_review": True},
                deletion_supported=True,
                scrub_supported=True,
                audit_event_id=audit_event_id,
                timestamp=timestamp,
            )
            conn.execute(
                """
                UPDATE memory_items
                SET status = ?, content = ?, graph_entities_json = '[]',
                    conflict_status = 'none', conflict_memory_ids_json = '[]', conflict_note = '',
                    review_note = ?, audit_event_id = ?,
                    updated_at = ?, deleted_at = ?
                WHERE id = ?
                """,
                (status, content_marker, reason, audit_event_id, timestamp, timestamp, memory_id),
            )
            conn.execute(
                """
                UPDATE memory_graph_edges
                SET status = 'deleted', subject = ?, predicate = ?,
                    object = ?, updated_at = ?, deleted_at = ?
                WHERE source_memory_id = ? AND status != 'deleted'
                """,
                (content_marker, content_marker, content_marker, timestamp, timestamp, memory_id),
            )
            conn.execute(
                """
                UPDATE memory_graph_entities
                SET status = 'deleted', label = ?, external_ref = '',
                    updated_at = ?, deleted_at = ?
                WHERE source_memory_id = ? AND status != 'deleted'
                """,
                (content_marker, timestamp, timestamp, memory_id),
            )
            conn.execute(
                """
                UPDATE memory_graph_relationships
                SET status = 'deleted', label = ?, updated_at = ?, deleted_at = ?
                WHERE source_memory_id = ? AND status != 'deleted'
                """,
                (content_marker, timestamp, timestamp, memory_id),
            )

    def record_tool_permission_check(
        self,
        check: dict[str, Any],
        *,
        actor_type: str = "system",
        actor_id: str = "tool-permission-gate",
    ) -> str:
        self.initialize()
        timestamp = now_iso()
        check_id = f"tool-check-{uuid.uuid4().hex[:16]}"
        check = _redact_audit_value(check)
        with self.connect() as conn:
            manifest_row = conn.execute(
                "SELECT tool_id, manifest_json, rollback_notes FROM tool_manifests WHERE tool_id = ?",
                (check["tool_id"],),
            ).fetchone()
            if not manifest_row:
                raise ValueError("Unknown tool manifest id")
            audit_event_id = self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type=str(check.get("audit_event_type") or "tool_permission_checked"),
                approval_id=check.get("approval_id") or None,
                risk_level=str(check.get("risk_level") or "medium"),
                summary=f"Tool permission {check_id}: {check.get('decision')} for {check.get('tool_id')}.",
                evidence="local preflight check; no tool execution performed",
                redacted_payload={
                    "check_id": check_id,
                    "tool_id": check.get("tool_id"),
                    "action_type": check.get("action_type"),
                    "requested_scope": check.get("requested_scope"),
                    "decision": check.get("decision"),
                    "risk_class": check.get("risk_class"),
                    "policy_decision": check.get("policy_decision"),
                    "risk_rationale": (check.get("risk_policy") or {}).get("risk_rationale")
                    or (check.get("risk_policy") or {}).get("reason")
                    or check.get("reason"),
                    "risk_examples": (check.get("risk_policy") or {}).get("examples", []),
                    "approval_state": (check.get("risk_policy") or {}).get("approval_state", ""),
                    "approval_first_required": bool((check.get("risk_policy") or {}).get("approval_first_required", False)),
                    "approval_required": bool(check.get("approval_required")),
                    "required_gate": check.get("required_gate"),
                    "approval_id": check.get("approval_id"),
                    "raw_secret_values_stored": False,
                    "tool_executed": False,
                },
                timestamp=timestamp,
            )
            if (
                str(check.get("decision") or "") == "allowed"
                and str(check.get("risk_class") or "") == "R4"
                and str(check.get("action_type") or "").strip().lower() != "read"
            ):
                rollback_notes = str(manifest_row["rollback_notes"] or "").strip()
                compensating_action = {
                    "type": "manual_or_tool_compensation",
                    "tool_id": check.get("tool_id"),
                    "scope": check.get("requested_scope"),
                    "plan": rollback_notes,
                    "requires_review": True,
                } if rollback_notes else {}
                self._insert_rollback_record(
                    conn,
                    kind="external_write",
                    status="compensation_available" if compensating_action else "compensation_unavailable",
                    risk_class="R4",
                    approval_id=check.get("approval_id") or None,
                    action_ref_type="tool_permission_check",
                    action_ref_id=check_id,
                    target_type="external_tool_scope",
                    target_ref=f"{check.get('tool_id')}:{check.get('requested_scope')}",
                    operation="compensate" if compensating_action else "manual_followup",
                    summary="Allowed external write preflight has audit details and a compensation plan when the tool manifest provides rollback notes.",
                    audit_details={
                        "tool_id": check.get("tool_id"),
                        "action_type": check.get("action_type"),
                        "requested_scope": check.get("requested_scope"),
                        "approval_id": check.get("approval_id"),
                        "permission_check_id": check_id,
                    },
                    compensating_action=compensating_action,
                    compensation_supported=bool(compensating_action),
                    audit_event_id=audit_event_id,
                    timestamp=timestamp,
                )
            conn.execute(
                """
                INSERT INTO tool_permission_checks(
                  id, tool_id, action_type, requested_scope, decision,
                  approval_required, required_gate, reason, risk_level,
                  approval_id, check_json, audit_event_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    check_id,
                    str(check["tool_id"]),
                    str(check["action_type"]),
                    str(check["requested_scope"]),
                    str(check["decision"]),
                    int(bool(check.get("approval_required", False))),
                    str(check.get("required_gate") or ""),
                    str(check.get("reason") or ""),
                    str(check.get("risk_level") or "medium"),
                    check.get("approval_id") or None,
                    json.dumps(check, ensure_ascii=False, sort_keys=True),
                    audit_event_id,
                    timestamp,
                ),
            )
        return check_id

    def record_connector_permission_check(
        self,
        check: dict[str, Any],
        *,
        actor_type: str = "system",
        actor_id: str = "connector-permission-gate",
        connector_executed: bool | None = None,
        write_performed: bool = False,
    ) -> str:
        self.initialize()
        timestamp = now_iso()
        check_id = f"connector-check-{uuid.uuid4().hex[:16]}"
        check = _redact_audit_value(check)
        action_type = str(check.get("action_type") or "").strip().lower()
        decision = str(check.get("decision") or "").strip().lower()
        executed = bool(connector_executed) if connector_executed is not None else bool(
            decision == "allowed" and action_type == "read" and check.get("connector_executed")
        )
        performed_write = bool(write_performed and decision == "allowed" and action_type in {"write", "external_write"})
        check["connector_executed"] = executed
        check["write_performed"] = performed_write
        with self.connect() as conn:
            manifest_row = conn.execute(
                "SELECT connector_id, manifest_json, rollback_notes FROM connector_manifests WHERE connector_id = ?",
                (check["connector_id"],),
            ).fetchone()
            if not manifest_row:
                raise ValueError("Unknown connector manifest id")
            audit_event_id = self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type=str(check.get("audit_event_type") or "connector_permission_checked"),
                approval_id=check.get("approval_id") or None,
                risk_level=str(check.get("risk_level") or "medium"),
                summary=f"Connector permission {check_id}: {check.get('decision')} for {check.get('connector_id')}.",
                evidence="local connector permission check; connector writes are never performed by the permission gate",
                redacted_payload={
                    "check_id": check_id,
                    "connector_id": check.get("connector_id"),
                    "action_type": check.get("action_type"),
                    "effective_action_type": check.get("effective_action_type"),
                    "requested_scope": check.get("requested_scope"),
                    "decision": check.get("decision"),
                    "risk_class": check.get("risk_class"),
                    "policy_decision": check.get("policy_decision"),
                    "risk_rationale": (check.get("risk_policy") or {}).get("risk_rationale")
                    or (check.get("risk_policy") or {}).get("reason")
                    or check.get("reason"),
                    "risk_examples": (check.get("risk_policy") or {}).get("examples", []),
                    "approval_state": (check.get("risk_policy") or {}).get("approval_state", ""),
                    "approval_first_required": bool((check.get("risk_policy") or {}).get("approval_first_required", False)),
                    "approval_required": bool(check.get("approval_required")),
                    "required_gate": check.get("required_gate"),
                    "approval_id": check.get("approval_id"),
                    "connector_executed": executed,
                    "write_performed": performed_write,
                    "raw_secret_values_stored": False,
                },
                timestamp=timestamp,
            )
            if (
                str(check.get("decision") or "") == "allowed"
                and str(check.get("risk_class") or "") == "R4"
                and str(check.get("action_type") or "").strip().lower() != "read"
            ):
                rollback_notes = str(manifest_row["rollback_notes"] or "").strip()
                compensating_action = {
                    "type": "manual_or_connector_compensation",
                    "connector_id": check.get("connector_id"),
                    "scope": check.get("requested_scope"),
                    "plan": rollback_notes,
                    "requires_review": True,
                } if rollback_notes else {}
                self._insert_rollback_record(
                    conn,
                    kind="external_write",
                    status="compensation_available" if compensating_action else "compensation_unavailable",
                    risk_class="R4",
                    approval_id=check.get("approval_id") or None,
                    action_ref_type="connector_permission_check",
                    action_ref_id=check_id,
                    target_type="external_connector_scope",
                    target_ref=f"{check.get('connector_id')}:{check.get('requested_scope')}",
                    operation="compensate" if compensating_action else "manual_followup",
                    summary="Allowed external connector write preflight has audit details and a compensation plan when the connector manifest provides rollback notes.",
                    audit_details={
                        "connector_id": check.get("connector_id"),
                        "action_type": check.get("action_type"),
                        "requested_scope": check.get("requested_scope"),
                        "approval_id": check.get("approval_id"),
                        "permission_check_id": check_id,
                    },
                    compensating_action=compensating_action,
                    compensation_supported=bool(compensating_action),
                    audit_event_id=audit_event_id,
                    timestamp=timestamp,
                )
            conn.execute(
                """
                INSERT INTO connector_permission_checks(
                  id, connector_id, action_type, requested_scope, decision,
                  approval_required, required_gate, reason, risk_level,
                  risk_class, policy_decision, approval_id, connector_executed,
                  write_performed, check_json, audit_event_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    check_id,
                    str(check["connector_id"]),
                    str(check["action_type"]),
                    str(check["requested_scope"]),
                    str(check["decision"]),
                    int(bool(check.get("approval_required", False))),
                    str(check.get("required_gate") or ""),
                    str(check.get("reason") or ""),
                    str(check.get("risk_level") or "medium"),
                    str(check.get("risk_class") or ""),
                    str(check.get("policy_decision") or ""),
                    check.get("approval_id") or None,
                    int(executed),
                    int(performed_write),
                    json.dumps(check, ensure_ascii=False, sort_keys=True),
                    audit_event_id,
                    timestamp,
                ),
            )
        return check_id

    def record_secret_scan_failure(
        self,
        *,
        surface: str,
        label: str,
        finding_kinds: list[str] | tuple[str, ...] | None = None,
        finding_count: int = 0,
        actor_type: str = "system",
        actor_id: str = "secret-scanner",
    ) -> None:
        self.initialize()
        timestamp = now_iso()
        safe_surface = redact_audit_text(str(surface or "unknown"))
        safe_label = redact_audit_text(str(label or "unknown"))
        with self.connect() as conn:
            self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="secret_scan_blocked",
                risk_level="high",
                summary=f"Secret scan blocked credential-like content at {safe_surface}.",
                evidence="secret scanner detection; offending value omitted",
                redacted_payload={
                    "surface": safe_surface,
                    "label": safe_label,
                    "finding_kinds": list(finding_kinds or []),
                    "finding_count": int(finding_count or 0),
                    "secret_value_logged": False,
                    "secret_value_persisted": False,
                },
                timestamp=timestamp,
            )

    def start_night_queue_run(
        self,
        *,
        selected_agents: list[str],
        selected_models: list[dict[str, Any]],
        cost_estimate: dict[str, Any],
        policy_limits: dict[str, Any],
        actor_type: str = "system",
        actor_id: str = "night-queue-scheduler",
    ) -> str:
        self.initialize()
        timestamp = now_iso()
        run_id = f"night-run-{uuid.uuid4().hex[:16]}"
        selected_agents = _redact_audit_value(selected_agents)
        selected_models = _redact_audit_value(selected_models)
        cost_estimate = _redact_audit_value(cost_estimate)
        policy_limits = _redact_audit_value(policy_limits)
        with self.connect() as conn:
            audit_event_id = self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="night_queue_started",
                risk_level="low",
                summary=f"Night queue run {run_id} started.",
                evidence="local autonomous night queue scheduler",
                redacted_payload={
                    "night_queue_run_id": run_id,
                    "status": "running",
                    "started_at": timestamp,
                    "selected_agents": selected_agents,
                    "selected_models": selected_models,
                    "cost_estimate": cost_estimate,
                    "policy_limits": policy_limits,
                },
                timestamp=timestamp,
            )
            conn.execute(
                """
                INSERT INTO night_queue_runs(
                  id, status, started_at, selected_agents_json, selected_models_json,
                  cost_estimate_json, policy_limits_json, audit_event_id,
                  created_at, updated_at
                )
                VALUES (?, 'running', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    timestamp,
                    _json_dumps(selected_agents),
                    _json_dumps(selected_models),
                    _json_dumps(cost_estimate),
                    _json_dumps(policy_limits),
                    audit_event_id,
                    timestamp,
                    timestamp,
                ),
            )
        return run_id

    def complete_night_queue_run(
        self,
        run_id: str,
        *,
        status: str,
        action_results: list[dict[str, Any]],
        failures: list[dict[str, Any]],
        sources: list[dict[str, Any]],
        changes: list[dict[str, Any]],
        rollback_status: dict[str, Any],
        morning_brief: dict[str, Any],
        actor_type: str = "system",
        actor_id: str = "night-queue-scheduler",
    ) -> None:
        status = str(status or "").strip()
        if status not in {"succeeded", "completed_with_attention", "failed"}:
            raise ValueError("invalid night queue run status")
        action_results = _redact_audit_value(action_results)
        failures = _redact_audit_value(failures)
        sources = _redact_audit_value(sources)
        changes = _redact_audit_value(changes)
        rollback_status = _redact_audit_value(rollback_status)
        morning_brief = _redact_audit_value(morning_brief)
        self.initialize()
        ended_at = now_iso()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id, started_at, selected_agents_json, selected_models_json, cost_estimate_json FROM night_queue_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Unknown night queue run id")
            audit_event_id = self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="night_queue_completed",
                risk_level="medium" if failures else "low",
                summary=f"Night queue run {run_id} completed with status {status}.",
                evidence="local autonomous night queue scheduler; no raw secrets or unapproved risky actions executed",
                redacted_payload={
                    "night_queue_run_id": run_id,
                    "status": status,
                    "started_at": row["started_at"],
                    "completed_at": ended_at,
                    "selected_agents": _json_loads(row["selected_agents_json"], []),
                    "selected_models": _json_loads(row["selected_models_json"], []),
                    "cost_estimate": _json_loads(row["cost_estimate_json"], {}),
                    "action_count": len(action_results),
                    "failure_count": len(failures),
                    "source_count": len(sources),
                    "change_count": len(changes),
                    "rollback_status": rollback_status,
                    "morning_brief": morning_brief,
                },
                timestamp=ended_at,
            )
            conn.execute(
                """
                UPDATE night_queue_runs
                SET status = ?, ended_at = ?, action_results_json = ?,
                    failures_json = ?, sources_json = ?, changes_json = ?,
                    rollback_status_json = ?, morning_brief_json = ?,
                    completed_audit_event_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    ended_at,
                    _json_dumps(action_results),
                    _json_dumps(failures),
                    _json_dumps(sources),
                    _json_dumps(changes),
                    _json_dumps(rollback_status),
                    _json_dumps(morning_brief),
                    audit_event_id,
                    ended_at,
                    run_id,
                ),
            )

    def get_night_queue_run(self, run_id: str | None = None) -> dict[str, Any]:
        self.initialize()
        with self.connect() as conn:
            if run_id:
                row = conn.execute(
                    """
                    SELECT id, status, started_at, ended_at, selected_agents_json,
                           selected_models_json, cost_estimate_json, policy_limits_json,
                           action_results_json, failures_json, sources_json,
                           changes_json, rollback_status_json, morning_brief_json,
                           audit_event_id, completed_audit_event_id, created_at, updated_at
                    FROM night_queue_runs
                    WHERE id = ?
                    """,
                    (run_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT id, status, started_at, ended_at, selected_agents_json,
                           selected_models_json, cost_estimate_json, policy_limits_json,
                           action_results_json, failures_json, sources_json,
                           changes_json, rollback_status_json, morning_brief_json,
                           audit_event_id, completed_audit_event_id, created_at, updated_at
                    FROM night_queue_runs
                    ORDER BY started_at DESC, id DESC
                    LIMIT 1
                    """
                ).fetchone()
        if row is None:
            raise ValueError("No night queue run found")
        run = dict(row)
        run["selected_agents"] = _json_loads(run.get("selected_agents_json"), [])
        run["selected_models"] = _json_loads(run.get("selected_models_json"), [])
        run["cost_estimate"] = _json_loads(run.get("cost_estimate_json"), {})
        run["policy_limits"] = _json_loads(run.get("policy_limits_json"), {})
        run["action_results"] = _json_loads(run.get("action_results_json"), [])
        run["failures"] = _json_loads(run.get("failures_json"), [])
        run["sources"] = _json_loads(run.get("sources_json"), [])
        run["changes"] = _json_loads(run.get("changes_json"), [])
        run["rollback_status"] = _json_loads(run.get("rollback_status_json"), {})
        run["morning_brief"] = _json_loads(run.get("morning_brief_json"), {})
        return _redact_audit_value(run)

    def generate_morning_brief_for_night_run(
        self,
        run_id: str | None = None,
        *,
        actor_type: str = "user",
        actor_id: str = "manual-morning-brief",
    ) -> dict[str, Any]:
        run = self.get_night_queue_run(run_id)
        if run["status"] == "running":
            raise ValueError("Cannot generate morning brief for a running night queue run")
        try:
            memory_context = self.retrieve_memory(
                _memory_query_from_run(run),
                scope="context",
                limit=5,
                actor_type="system",
                actor_id="morning-brief-memory-context",
            )
        except Exception as exc:  # pragma: no cover - defensive manual brief enrichment
            memory_context = {
                "answer_status": "unavailable",
                "confidence": 0,
                "source_refs": [],
                "related_graph_entries": [],
                "conflicts": [],
                "metrics": {"match_count": 0, "relevance_score": 0},
                "reason": str(exc),
            }
        brief = build_morning_brief_from_run(run, generated_by=actor_id, memory_context=memory_context)
        timestamp = now_iso()
        with self.connect() as conn:
            audit_event_id = self.append_audit_event(
                conn,
                actor_type=actor_type,
                actor_id=actor_id,
                event_type="morning_brief_generated",
                risk_level="low",
                summary=f"Morning brief generated for night queue run {run['id']}.",
                evidence="manual morning brief request",
                redacted_payload={
                    "night_queue_run_id": run["id"],
                    "generated_at": brief["generated_at"],
                    "section_titles": [section["title"] for section in brief.get("sections", [])],
                    "details_collapsed_by_default": brief.get("details_collapsed_by_default", True),
                    "retrieved_context": brief.get("retrieved_context", {}),
                },
                timestamp=timestamp,
            )
            conn.execute(
                """
                UPDATE night_queue_runs
                SET morning_brief_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (_json_dumps(brief), timestamp, run["id"]),
            )
        return _redact_audit_value({**brief, "id": run["id"], "audit_event_id": audit_event_id})

    def append_audit_event(
        self,
        conn: sqlite3.Connection,
        *,
        actor_type: str,
        actor_id: str,
        event_type: str,
        summary: str,
        task_id: str | None = None,
        approval_id: str | None = None,
        risk_level: str = "low",
        evidence: str = "",
        redacted_payload: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> str:
        row = conn.execute(
            "SELECT sequence, event_hash FROM audit_events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        sequence = int(row["sequence"]) + 1 if row else 1
        prev_hash = row["event_hash"] if row else "GENESIS"
        event_id = f"audit-{uuid.uuid4().hex}"
        event_timestamp = timestamp or now_iso()
        actor_type = redact_audit_text(actor_type)
        actor_id = redact_audit_text(actor_id)
        task_id = redact_audit_text(task_id) if task_id else None
        approval_id = redact_audit_text(approval_id) if approval_id else None
        summary = redact_audit_text(summary)
        evidence = redact_audit_text(evidence)
        audit_payload = build_audit_payload(
            actor_id=actor_id,
            event_type=event_type,
            summary=summary,
            risk_level=risk_level,
            evidence=evidence,
            task_id=task_id,
            approval_id=approval_id,
            timestamp=event_timestamp,
            redacted_payload=redacted_payload,
        )
        payload_json = json.dumps(audit_payload, ensure_ascii=False, sort_keys=True)
        event = {
            "id": event_id,
            "sequence": sequence,
            "timestamp": event_timestamp,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "event_type": event_type,
            "task_id": task_id,
            "approval_id": approval_id,
            "risk_level": risk_level,
            "summary": summary,
            "evidence": evidence,
            "redacted_payload_json": payload_json,
            "prev_hash": prev_hash,
        }
        event_hash = hashlib.sha256(audit_hash_payload(event).encode("utf-8")).hexdigest()
        conn.execute(
            """
            INSERT INTO audit_events(
              id, sequence, timestamp, actor_type, actor_id, event_type, task_id,
              approval_id, risk_level, summary, evidence, redacted_payload_json,
              prev_hash, event_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                sequence,
                event["timestamp"],
                actor_type,
                actor_id,
                event_type,
                task_id,
                approval_id,
                risk_level,
                summary,
                evidence,
                payload_json,
                prev_hash,
                event_hash,
            ),
        )
        return event_id

    def validate_audit_hash_chain(self) -> bool:
        self.initialize()
        previous_hash = "GENESIS"
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, sequence, timestamp, actor_type, actor_id, event_type,
                       task_id, approval_id, risk_level, summary, evidence,
                       redacted_payload_json, prev_hash, event_hash
                FROM audit_events
                ORDER BY sequence
                """
            ).fetchall()
            for row in rows:
                event = {
                    "id": row["id"],
                    "sequence": row["sequence"],
                    "timestamp": row["timestamp"],
                    "actor_type": row["actor_type"],
                    "actor_id": row["actor_id"],
                    "event_type": row["event_type"],
                    "task_id": row["task_id"],
                    "approval_id": row["approval_id"],
                    "risk_level": row["risk_level"],
                    "summary": row["summary"],
                    "evidence": row["evidence"],
                    "redacted_payload_json": row["redacted_payload_json"],
                    "prev_hash": row["prev_hash"],
                }
                expected = hashlib.sha256(audit_hash_payload(event).encode("utf-8")).hexdigest()
                if row["prev_hash"] != previous_hash or row["event_hash"] != expected:
                    return False
                previous_hash = row["event_hash"]
        return True
