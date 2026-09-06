from __future__ import annotations

from typing import Any

from leon_control_plane.secret_scanner import redact_value


TRANSPARENCY_INSPECTOR_GROUPS = [
    ("sources", "Sources"),
    ("model_choices", "Model choice"),
    ("costs", "Cost"),
    ("prompts_or_summaries", "Prompts or summaries"),
    ("logs", "Logs"),
    ("diffs", "Diffs"),
    ("graph_updates", "Graph updates"),
    ("policy_decisions", "Policy decisions"),
    ("rollback_data", "Rollback data"),
]


def _list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [value]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _first_non_empty(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def _compact_rollback_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for record in records:
        item: dict[str, Any] = {
            "id": record.get("id"),
            "kind": record.get("kind"),
            "status": record.get("status"),
            "risk_class": record.get("risk_class"),
            "target_type": record.get("target_type"),
            "target_ref": record.get("target_ref"),
            "operation": record.get("operation"),
            "summary": record.get("summary"),
            "deletion_supported": bool(record.get("deletion_supported")),
            "undo_supported": bool(record.get("undo_supported")),
            "scrub_supported": bool(record.get("scrub_supported")),
            "compensation_supported": bool(record.get("compensation_supported")),
        }
        if record.get("patch_snapshot"):
            item["patch_snapshot"] = record.get("patch_snapshot")
        if record.get("test_results"):
            item["test_results"] = record.get("test_results")
        if record.get("audit_details"):
            item["audit_details"] = record.get("audit_details")
        if record.get("compensating_action"):
            item["compensating_action"] = record.get("compensating_action")
        if record.get("before_snapshot"):
            item["before_snapshot"] = record.get("before_snapshot")
        if record.get("after_snapshot"):
            item["after_snapshot"] = record.get("after_snapshot")
        compact.append(item)
    return compact


def _inspector(group_id: str, title: str, content: Any) -> dict[str, Any]:
    return {
        "id": group_id,
        "title": title,
        "collapsed": True,
        "default_expanded": False,
        "content": redact_value(content),
    }


def build_transparency_inspectors(
    *,
    surface: str,
    record: dict[str, Any],
    audit_events: list[dict[str, Any]] | None = None,
    rollback_records: list[dict[str, Any]] | None = None,
    graph_entities: list[dict[str, Any]] | None = None,
    graph_relationships: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    audit_events = _list(audit_events)
    rollback_records = [item for item in _list(rollback_records) if isinstance(item, dict)]
    graph_entities = [item for item in _list(graph_entities) if isinstance(item, dict)]
    graph_relationships = [item for item in _list(graph_relationships) if isinstance(item, dict)]

    if surface == "agent_run":
        payloads = _agent_run_payloads(record, audit_events, rollback_records, graph_entities, graph_relationships)
    elif surface == "source_record":
        payloads = _source_record_payloads(record, audit_events, rollback_records, graph_entities, graph_relationships)
    elif surface == "approval":
        payloads = _approval_payloads(record, audit_events, rollback_records, graph_entities, graph_relationships)
    elif surface == "morning_brief":
        payloads = _morning_brief_payloads(record, audit_events, rollback_records, graph_entities, graph_relationships)
    else:
        payloads = _generic_payloads(record, audit_events, rollback_records, graph_entities, graph_relationships)

    default_view = redact_value(payloads.pop("default_view"))
    inspectors = [
        _inspector(group_id, title, payloads.get(group_id, {}))
        for group_id, title in TRANSPARENCY_INSPECTOR_GROUPS
    ]
    return {
        "surface": surface,
        "details_collapsed_by_default": True,
        "default_view": default_view,
        "inspectors": inspectors,
    }


def _agent_run_payloads(
    record: dict[str, Any],
    audit_events: list[dict[str, Any]],
    rollback_records: list[dict[str, Any]],
    graph_entities: list[dict[str, Any]],
    graph_relationships: list[dict[str, Any]],
) -> dict[str, Any]:
    model_route = record.get("model_route") if isinstance(record.get("model_route"), dict) else {}
    cost = record.get("cost_estimate") if isinstance(record.get("cost_estimate"), dict) else {}
    risk = record.get("risk_assessment") if isinstance(record.get("risk_assessment"), dict) else {}
    output = record.get("output") if isinstance(record.get("output"), dict) else {}
    rollback_status = record.get("rollback_status") if isinstance(record.get("rollback_status"), dict) else {}
    warning = (
        cost.get("cost_warning")
        if isinstance(cost.get("cost_warning"), dict)
        else model_route.get("cost_warning") if isinstance(model_route.get("cost_warning"), dict) else {}
    )
    attention = []
    if record.get("status") in {"waiting_for_review", "failed"}:
        attention.append(_text(record.get("next_action") or "review_agent_run"))
    if warning.get("required"):
        attention.append(_text(warning.get("message") or "cost warning required"))
    if rollback_status.get("status") in {"missing", "compensation_unavailable"}:
        attention.append(f"rollback:{rollback_status.get('status')}")
    return {
        "default_view": {
            "status": record.get("status"),
            "progress": _run_progress(record),
            "final_result": _first_non_empty(record.get("result_summary"), output.get("summary"), "No final result yet."),
            "risk_or_attention_signals": [item for item in attention if item],
        },
        "sources": {
            "input_sources": record.get("input_sources") or [],
            "evidence": record.get("evidence") or output.get("evidence") or [],
        },
        "model_choices": {
            "provider": model_route.get("provider") or record.get("provider"),
            "route": model_route.get("route") or record.get("route"),
            "model": model_route.get("model") or record.get("model"),
            "reasoning_effort": model_route.get("reasoning_effort") or record.get("reasoning_effort"),
            "reason": model_route.get("user_visible_reason") or model_route.get("reason") or record.get("route_reason"),
            "cost_warning": warning,
        },
        "costs": cost,
        "prompts_or_summaries": {
            "task": record.get("task"),
            "task_type": record.get("task_type"),
            "complexity": record.get("complexity"),
            "result_summary": record.get("result_summary"),
            "output_summary": output.get("summary"),
            "reviewer_result": record.get("reviewer_result"),
        },
        "logs": audit_events,
        "diffs": [item for item in _compact_rollback_records(rollback_records) if item.get("patch_snapshot") or item.get("before_snapshot") or item.get("after_snapshot")],
        "graph_updates": {"entities": graph_entities, "relationships": graph_relationships},
        "policy_decisions": {
            "risk_assessment": risk,
            "review_status": record.get("review_status"),
            "approval_required": bool(record.get("approval_required")),
            "allowed_actions": record.get("allowed_actions_json"),
            "forbidden_actions": record.get("forbidden_actions_json"),
        },
        "rollback_data": {
            "status": rollback_status,
            "records": _compact_rollback_records(rollback_records),
        },
    }


def _source_record_payloads(
    record: dict[str, Any],
    audit_events: list[dict[str, Any]],
    rollback_records: list[dict[str, Any]],
    graph_entities: list[dict[str, Any]],
    graph_relationships: list[dict[str, Any]],
) -> dict[str, Any]:
    secret_scan = record.get("secret_scan") if isinstance(record.get("secret_scan"), dict) else {}
    attention = []
    if record.get("status") == "blocked_secret":
        attention.append("blocked_secret")
    if secret_scan.get("has_findings"):
        attention.append("credential-like content blocked or redacted")
    return {
        "default_view": {
            "status": record.get("status"),
            "progress": "indexed" if record.get("status") == "active" else record.get("status"),
            "final_result": record.get("content_excerpt") or record.get("title"),
            "risk_or_attention_signals": attention,
        },
        "sources": {
            "source_type": record.get("source_type"),
            "source_ref": record.get("source_ref"),
            "title": record.get("title"),
            "content_hash": record.get("content_hash"),
            "content_bytes": record.get("content_bytes"),
            "metadata": record.get("metadata"),
            "content_excerpt_only": record.get("content_excerpt"),
        },
        "model_choices": {},
        "costs": {},
        "prompts_or_summaries": {
            "summary": record.get("content_excerpt"),
            "raw_full_content_exposed": False,
        },
        "logs": audit_events,
        "diffs": [item for item in _compact_rollback_records(rollback_records) if item.get("before_snapshot") or item.get("after_snapshot")],
        "graph_updates": {"entities": graph_entities, "relationships": graph_relationships},
        "policy_decisions": {"secret_scan": secret_scan, "status": record.get("status")},
        "rollback_data": {"records": _compact_rollback_records(rollback_records)},
    }


def _approval_payloads(
    record: dict[str, Any],
    audit_events: list[dict[str, Any]],
    rollback_records: list[dict[str, Any]],
    graph_entities: list[dict[str, Any]],
    graph_relationships: list[dict[str, Any]],
) -> dict[str, Any]:
    attention = []
    if record.get("status") == "pending":
        attention.append("waiting_for_owner_decision")
    if record.get("risk_level") in {"high", "critical"}:
        attention.append(f"risk:{record.get('risk_level')}")
    return {
        "default_view": {
            "status": record.get("status"),
            "progress": "waiting" if record.get("status") == "pending" else "decided",
            "final_result": record.get("decision_note") or record.get("summary"),
            "risk_or_attention_signals": attention,
        },
        "sources": {
            "task_id": record.get("task_id"),
            "requested_by": record.get("requested_by"),
        },
        "model_choices": {},
        "costs": {"cost_estimate": record.get("cost_estimate")},
        "prompts_or_summaries": {
            "summary": record.get("summary"),
            "reason": record.get("reason"),
            "external_effect": record.get("external_effect"),
        },
        "logs": audit_events,
        "diffs": [],
        "graph_updates": {"entities": graph_entities, "relationships": graph_relationships},
        "policy_decisions": {
            "action_type": record.get("action_type"),
            "risk_level": record.get("risk_level"),
            "permissions": record.get("permissions"),
            "affected_systems": record.get("affected_systems"),
            "status": record.get("status"),
            "decided_at": record.get("decided_at"),
            "consumed_at": record.get("consumed_at"),
        },
        "rollback_data": {
            "rollback_plan": record.get("rollback_plan"),
            "records": _compact_rollback_records(rollback_records),
        },
    }


def _morning_brief_payloads(
    record: dict[str, Any],
    audit_events: list[dict[str, Any]],
    rollback_records: list[dict[str, Any]],
    graph_entities: list[dict[str, Any]],
    graph_relationships: list[dict[str, Any]],
) -> dict[str, Any]:
    sections = record.get("sections") if isinstance(record.get("sections"), list) else []
    return {
        "default_view": {
            "status": record.get("status"),
            "progress": f"{len(sections)} section(s)",
            "final_result": "Morning brief generated." if sections else "No morning brief generated yet.",
            "risk_or_attention_signals": record.get("risks_and_attention") or [],
        },
        "sources": (record.get("sources_and_logs") or {}).get("sources") if isinstance(record.get("sources_and_logs"), dict) else record.get("sources"),
        "model_choices": (record.get("costs_and_models") or {}).get("selected_models") if isinstance(record.get("costs_and_models"), dict) else record.get("selected_models"),
        "costs": (record.get("costs_and_models") or {}).get("cost_estimate") if isinstance(record.get("costs_and_models"), dict) else record.get("cost_estimate"),
        "prompts_or_summaries": {"sections": sections, "important_today": record.get("important_today")},
        "logs": audit_events or ((record.get("sources_and_logs") or {}).get("action_results") if isinstance(record.get("sources_and_logs"), dict) else []),
        "diffs": record.get("completed_improvements"),
        "graph_updates": {"entities": graph_entities, "relationships": graph_relationships},
        "policy_decisions": record.get("risks_and_attention"),
        "rollback_data": record.get("rollback") or {"records": _compact_rollback_records(rollback_records)},
    }


def _generic_payloads(
    record: dict[str, Any],
    audit_events: list[dict[str, Any]],
    rollback_records: list[dict[str, Any]],
    graph_entities: list[dict[str, Any]],
    graph_relationships: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "default_view": {
            "status": record.get("status"),
            "progress": record.get("progress") or record.get("updated_at") or "",
            "final_result": _first_non_empty(record.get("summary"), record.get("result"), record.get("title")),
            "risk_or_attention_signals": record.get("attention") or [],
        },
        "sources": record.get("sources") or record.get("source_refs") or [],
        "model_choices": record.get("model_route") or {},
        "costs": record.get("cost_estimate") or {},
        "prompts_or_summaries": record,
        "logs": audit_events,
        "diffs": [],
        "graph_updates": {"entities": graph_entities, "relationships": graph_relationships},
        "policy_decisions": record.get("policy") or {},
        "rollback_data": {"records": _compact_rollback_records(rollback_records)},
    }


def _run_progress(record: dict[str, Any]) -> dict[str, str]:
    return {
        "created_at": _text(record.get("created_at")),
        "started_at": _text(record.get("started_at")),
        "completed_at": _text(record.get("completed_at")),
        "updated_at": _text(record.get("updated_at")),
    }
