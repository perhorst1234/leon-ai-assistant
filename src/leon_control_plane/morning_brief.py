from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from leon_control_plane.secret_scanner import redact_value
from leon_control_plane.transparency import TRANSPARENCY_INSPECTOR_GROUPS, build_transparency_inspectors


MORNING_BRIEF_SECTIONS = [
    ("important_today", "Important Today"),
    ("new_knowledge", "New Knowledge"),
    ("completed_improvements", "Completed Improvements"),
    ("proposals", "Proposals"),
    ("risks_and_attention", "Risks and Attention"),
    ("costs_and_models", "Costs and Models"),
    ("sources_and_logs", "Sources and Logs"),
]

DETAIL_GROUPS = TRANSPARENCY_INSPECTOR_GROUPS


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [value]


def _decision_evidence_for(item: dict[str, Any], *, run_id: str, section_id: str) -> dict[str, Any]:
    existing = item.get("decision_evidence") if isinstance(item.get("decision_evidence"), dict) else {}
    routing_decision_id = str(item.get("routing_decision_id") or existing.get("routing_decision_id") or "").strip()
    audit_event_id = str(item.get("routing_audit_event_id") or existing.get("audit_event_id") or "").strip()
    if routing_decision_id:
        return {
            **existing,
            "status": "linked",
            "routing_decision_id": routing_decision_id,
            "evidence_ref": f"routing_decisions:{routing_decision_id}",
            "audit_event_id": audit_event_id,
            "provenance_required": True,
        }
    return {
        **existing,
        "status": existing.get("status") or "not_routed",
        "routing_decision_id": "",
        "evidence_ref": existing.get("evidence_ref") or f"morning_brief:{run_id}:{section_id}",
        "reason": existing.get("reason") or "This brief item was generated from night queue state, logs, memory, or local records without a routing decision id.",
        "provenance_required": True,
    }


def _attach_decision_evidence(items: Any, *, run_id: str, section_id: str) -> Any:
    if isinstance(items, list):
        output: list[Any] = []
        for item in items:
            if isinstance(item, dict):
                enriched = dict(item)
                enriched["decision_evidence"] = _decision_evidence_for(enriched, run_id=run_id, section_id=section_id)
                output.append(enriched)
            else:
                output.append(item)
        return output
    if isinstance(items, dict):
        enriched = dict(items)
        enriched["decision_evidence"] = _decision_evidence_for(enriched, run_id=run_id, section_id=section_id)
        return enriched
    return items


def _count_text(count: int, noun: str) -> str:
    suffix = "" if count == 1 else "s"
    return f"{count} {noun}{suffix}"


def compact_retrieved_context(memory_context: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(memory_context, dict):
        return {
            "applied": False,
            "query_id": "",
            "answer_status": "not_requested",
            "confidence": 0,
            "relevance_score": 0,
            "match_count": 0,
            "source_refs": [],
            "related_graph_entries": [],
            "conflicts": [],
            "provenance_required": True,
        }
    metrics = memory_context.get("metrics") if isinstance(memory_context.get("metrics"), dict) else {}
    try:
        relevance_score = float(metrics.get("relevance_score", memory_context.get("relevance_score") or 0))
    except (TypeError, ValueError):
        relevance_score = 0
    try:
        confidence = float(memory_context.get("confidence") or metrics.get("confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0
    try:
        match_count = int(metrics.get("match_count", memory_context.get("match_count") or 0))
    except (TypeError, ValueError):
        match_count = 0
    source_refs = memory_context.get("source_refs") if isinstance(memory_context.get("source_refs"), list) else []
    related_graph_entries = (
        memory_context.get("related_graph_entries") if isinstance(memory_context.get("related_graph_entries"), list) else []
    )
    conflicts = memory_context.get("conflicts") if isinstance(memory_context.get("conflicts"), list) else []
    return {
        "applied": str(memory_context.get("answer_status") or "") == "answered" and bool(source_refs) and match_count > 0,
        "query_id": str(memory_context.get("id") or ""),
        "answer_status": str(memory_context.get("answer_status") or ""),
        "confidence": round(max(0, min(confidence, 1)), 4),
        "relevance_score": round(max(0, min(relevance_score, 1)), 4),
        "match_count": match_count,
        "memory_match_count": int(metrics.get("memory_match_count") or 0),
        "source_match_count": int(metrics.get("source_match_count") or 0),
        "source_refs": source_refs[:8],
        "related_graph_entries": related_graph_entries[:10],
        "conflicts": conflicts[:5],
        "provenance_required": True,
    }


def _summary_for(section_id: str, items: Any) -> str:
    if section_id == "important_today":
        return "Quiet overview of what happened overnight."
    if section_id == "new_knowledge":
        return f"{_count_text(len(_list(items)), 'knowledge update')} prepared for review."
    if section_id == "completed_improvements":
        return f"{_count_text(len(_list(items)), 'local improvement')} completed or recorded."
    if section_id == "proposals":
        return f"{_count_text(len(_list(items)), 'proposal')} waiting for owner review."
    if section_id == "risks_and_attention":
        return f"{_count_text(len(_list(items)), 'attention item')} found."
    if section_id == "costs_and_models":
        cost = items.get("cost_estimate", {}) if isinstance(items, dict) else {}
        return (
            f"Projected {cost.get('currency', 'USD')} "
            f"{cost.get('estimated_min', '0')}-{cost.get('estimated_max', '0')}; no provider calls metered."
        )
    if section_id == "sources_and_logs":
        if isinstance(items, dict):
            return (
                f"{_count_text(len(_list(items.get('sources'))), 'source')} and "
                f"{_count_text(len(_list(items.get('action_results'))), 'log entry')} attached."
            )
        return "Sources and logs attached for inspection."
    return "No summary available."


def _detail_groups(
    *,
    sources: list[dict[str, Any]],
    action_results: list[dict[str, Any]],
    selected_models: list[dict[str, Any]],
    cost_estimate: dict[str, Any],
    changes: list[dict[str, Any]],
    rollback_status: dict[str, Any],
) -> list[dict[str, Any]]:
    def _failure_reason(result: dict[str, Any]) -> Any:
        failure = result.get("failure")
        if isinstance(failure, dict):
            return failure.get("reason")
        return failure

    policies = [
        {
            "action_id": result.get("action_id"),
            "policy": result.get("policy"),
            "failure": result.get("failure"),
        }
        for result in action_results
        if isinstance(result, dict) and (result.get("policy") or result.get("failure"))
    ]
    diffs = [
        change
        for change in changes
        if isinstance(change, dict)
        and (
            change.get("diff")
            or change.get("patch")
            or change.get("patch_snapshot")
            or change.get("type") in {"task", "memory_item", "cache", "self_improvement", "code_system"}
        )
    ]
    payloads = {
        "sources": sources,
        "model_choices": selected_models,
        "costs": cost_estimate,
        "prompts_or_summaries": {
            "action_summaries": [
                {
                    "action_id": result.get("action_id"),
                    "status": result.get("status"),
                    "summary": result.get("summary") or _failure_reason(result),
                }
                for result in action_results
                if isinstance(result, dict)
            ],
            "raw_prompts_exposed": False,
        },
        "logs": action_results,
        "diffs": diffs,
        "graph_updates": [
            change
            for change in changes
            if isinstance(change, dict) and change.get("type") in {"memory_item", "source_record", "graph_entity", "graph_relationship"}
        ],
        "policy_decisions": policies,
        "rollback_data": rollback_status,
    }
    return [
        {
            "id": group_id,
            "title": title,
            "collapsed": True,
            "default_expanded": False,
            "content": redact_value(payloads[group_id]),
        }
        for group_id, title in DETAIL_GROUPS
    ]


def _missing_ui_capabilities(
    *,
    action_results: list[dict[str, Any]],
    changes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for change in changes:
        if isinstance(change, dict) and change.get("type") == "missing_component":
            records.append(change)
    for result in action_results:
        if not isinstance(result, dict):
            continue
        for item in _list(result.get("missing_components")):
            if isinstance(item, dict):
                records.append(item)

    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for record in records:
        key = str(record.get("id") or record.get("missing_component_record_id") or record.get("requested_component") or "")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        output.append(record)
    return output


def build_morning_brief(
    *,
    run_id: str,
    status: str,
    action_results: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    changes: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
    selected_models: list[dict[str, Any]],
    cost_estimate: dict[str, Any],
    rollback_status: dict[str, Any],
    memory_context: dict[str, Any] | None = None,
    started_at: str = "",
    ended_at: str = "",
    generated_by: str = "night_queue",
) -> dict[str, Any]:
    completed_count = len([item for item in action_results if item.get("status") == "succeeded"])
    missing_ui_capabilities = _missing_ui_capabilities(action_results=action_results, changes=changes)
    retrieved_context = compact_retrieved_context(memory_context)
    brief_sources = list(sources)
    memory_context_item = None
    if retrieved_context["applied"]:
        memory_context_item = {
            "type": "retrieved_context",
            "title": "Relevant stored context",
            "retrieval_id": retrieved_context["query_id"],
            "confidence": retrieved_context["confidence"],
            "relevance_score": retrieved_context["relevance_score"],
            "source_refs": retrieved_context["source_refs"],
            "related_graph_entry_count": len(retrieved_context["related_graph_entries"]),
            "conflict_count": len(retrieved_context["conflicts"]),
            "provenance_required": True,
        }
        brief_sources.append(
            {
                "type": "memory_context",
                "retrieval_id": retrieved_context["query_id"],
                "source_refs": retrieved_context["source_refs"],
                "provenance_required": True,
            }
        )
    proposal_items = list(proposals) + [
        {
            "type": "missing_ui_capability",
            "title": f"Implement UI capability: {item.get('requested_component') or item.get('id')}",
            "task_id": item.get("task_id"),
            "missing_component_record_id": item.get("id") or item.get("missing_component_record_id"),
            "fallback_component_ids": item.get("fallback_component_ids") or [],
            "requires_review": True,
        }
        for item in missing_ui_capabilities
    ]
    raw_sections: dict[str, Any] = {
        "important_today": [
            f"{completed_count} night queue action(s) completed.",
            f"{len(failures)} action(s) need review or retry.",
            f"{len(proposal_items)} proposal(s) are ready for review.",
            f"{len(missing_ui_capabilities)} missing UI capability need(s) were recorded.",
        ],
        "new_knowledge": (
            ([memory_context_item] if memory_context_item else [])
            + [change for change in changes if change.get("type") == "memory_item"]
        ),
        "completed_improvements": [
            change
            for change in changes
            if change.get("type") in {"cache", "task", "self_improvement", "code_system"}
        ],
        "proposals": proposal_items,
        "risks_and_attention": failures,
        "costs_and_models": {
            "cost_estimate": cost_estimate,
            "selected_models": selected_models,
        },
        "sources_and_logs": {
            "sources": brief_sources,
            "action_results": action_results,
            "retrieved_context": retrieved_context,
        },
        "missing_ui_capabilities": missing_ui_capabilities,
    }
    legacy_sections = {
        section_id: _attach_decision_evidence(items, run_id=run_id, section_id=section_id)
        for section_id, items in raw_sections.items()
    }
    recovery_suggestions = []
    seen_recovery: set[tuple[str, str]] = set()
    for failure in failures:
        if not isinstance(failure, dict):
            continue
        for suggestion in failure.get("recovery_suggestions") or []:
            if not isinstance(suggestion, dict):
                continue
            key = (str(suggestion.get("action") or ""), str(suggestion.get("summary") or ""))
            if not key[1] or key in seen_recovery:
                continue
            seen_recovery.add(key)
            recovery_suggestions.append({"action": key[0] or "review_failure", "summary": key[1]})
    partial_failure_disclosure = {
        "visible_to_user": True,
        "has_partial_failure": bool(failures),
        "status": status,
        "failure_count": len(failures),
        "recovery_suggestions": recovery_suggestions[:6],
    }
    details = _detail_groups(
        sources=brief_sources,
        action_results=action_results,
        selected_models=selected_models,
        cost_estimate=cost_estimate,
        changes=changes,
        rollback_status=rollback_status,
    )
    sections = [
        {
            "id": section_id,
            "title": title,
            "summary": _summary_for(section_id, legacy_sections[section_id]),
            "items": redact_value(legacy_sections[section_id]),
            "details_collapsed": True,
            "detail_group_ids": [group["id"] for group in details],
        }
        for section_id, title in MORNING_BRIEF_SECTIONS
    ]
    brief = {
        "run_id": run_id,
        "status": status,
        "started_at": started_at,
        "ended_at": ended_at,
        "generated_at": now_iso(),
        "generated_by": generated_by,
        "details_collapsed_by_default": True,
        "sections": sections,
        "expandable_details": details,
        "partial_failure_disclosure": partial_failure_disclosure,
        "retrieved_context": retrieved_context,
        "rollback": rollback_status,
        **legacy_sections,
    }
    transparency = build_transparency_inspectors(surface="morning_brief", record=brief)
    brief["transparency"] = transparency
    brief["inspectors"] = transparency["inspectors"]
    brief["default_view"] = transparency["default_view"]
    return redact_value(brief)


def build_morning_brief_from_run(
    run: dict[str, Any],
    *,
    generated_by: str = "manual",
    memory_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_morning_brief(
        run_id=str(run.get("id") or run.get("run_id") or ""),
        status=str(run.get("status") or ""),
        action_results=_list(run.get("action_results")),
        failures=_list(run.get("failures")),
        sources=_list(run.get("sources")),
        changes=_list(run.get("changes")),
        proposals=_collect_proposals(_list(run.get("action_results")), run.get("morning_brief")),
        selected_models=_list(run.get("selected_models")),
        cost_estimate=run.get("cost_estimate") if isinstance(run.get("cost_estimate"), dict) else {},
        rollback_status=run.get("rollback_status") if isinstance(run.get("rollback_status"), dict) else {},
        memory_context=memory_context,
        started_at=str(run.get("started_at") or ""),
        ended_at=str(run.get("ended_at") or ""),
        generated_by=generated_by,
    )


def _collect_proposals(action_results: list[Any], existing_brief: Any) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    for result in action_results:
        if isinstance(result, dict):
            proposals.extend(item for item in _list(result.get("proposals")) if isinstance(item, dict))
    if not proposals and isinstance(existing_brief, dict):
        proposals.extend(item for item in _list(existing_brief.get("proposals")) if isinstance(item, dict))
    return proposals
