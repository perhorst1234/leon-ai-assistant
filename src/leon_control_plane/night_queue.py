from __future__ import annotations

from typing import TYPE_CHECKING, Any

from leon_control_plane.morning_brief import build_morning_brief
from leon_control_plane.model_policy import choose_route
from leon_control_plane.risk_policy import evaluate_action_policy
from leon_control_plane.secret_scanner import redact_value
from leon_control_plane.ui_composition import compose_ui

if TYPE_CHECKING:
    from leon_control_plane.store import ControlPlaneStore


DEFAULT_ALLOWED_RISK_CLASSES = ["R1", "R2"]


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if text and text not in seen:
            seen.add(text)
            output.append(text)
    return output


def _recovery_suggestions(*, reason: str, risk_class: str, policy_decision: str = "") -> list[dict[str, str]]:
    suggestions = [
        {
            "action": "review_failure",
            "summary": f"Review the action log and policy details for: {reason}",
        },
        {
            "action": "retry_after_scope_fix",
            "summary": "Retry only after narrowing scope, correcting the blocker, or moving the action out of autonomous execution.",
        },
    ]
    if risk_class not in DEFAULT_ALLOWED_RISK_CLASSES or policy_decision in {"needs_review", "blocked"}:
        suggestions.append(
            {
                "action": "create_review_or_approval",
                "summary": "Create a reviewable proposal or approval-gated task instead of retrying this action autonomously.",
            }
        )
    return suggestions


def _default_sources(state: dict[str, Any]) -> list[dict[str, str]]:
    refs: list[str] = []
    for task in state.get("tasks", []):
        refs.extend(str(ref) for ref in task.get("source_refs") or [])
    refs.extend(["tasks/prd.json", ".ralph-tui/progress.md", "state/control-plane.seed.json"])
    return [{"type": "local_source", "ref": ref} for ref in _unique(refs)[:20]]


def _estimate_queue_cost(action_specs: list[dict[str, Any]]) -> dict[str, Any]:
    selected_models = [spec["model_route"] for spec in action_specs]
    mins = []
    maxes = []
    for route in selected_models:
        estimate = route.get("estimated_cost") if isinstance(route.get("estimated_cost"), dict) else {}
        try:
            mins.append(float(estimate.get("estimated_min") or 0))
            maxes.append(float(estimate.get("estimated_max") or 0))
        except (TypeError, ValueError):
            continue
    return {
        "currency": "USD",
        "estimated_min": round(sum(mins), 4),
        "estimated_max": round(sum(maxes), 4),
        "estimation_status": "projected_no_provider_calls",
        "basis": "Sum of selected model-route estimates for one bounded night queue pass; current scheduler records local deterministic work only.",
        "provider_calls_made": False,
    }


def _brief_memory_query(
    *,
    action_results: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    changes: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
) -> str:
    parts: list[str] = []
    for collection in (action_results, failures, sources, changes, proposals):
        for item in collection[:8]:
            if not isinstance(item, dict):
                continue
            for key in ("action_id", "title", "summary", "reason", "objective", "source_ref", "ref", "type"):
                value = str(item.get(key) or "").strip()
                if value:
                    parts.append(value)
    return " ".join(_unique(parts))[:1000] or "night queue morning brief context"


def build_night_queue_actions(*, budget_mode: str = "economy", local_gpu_ready: bool = False) -> list[dict[str, Any]]:
    raw_actions = [
        {
            "id": "index_new_sources",
            "agent": "Research",
            "task_type": "extraction",
            "complexity": "low",
            "risk": "low",
            "privacy": "private",
            "action_type": "source_review",
            "requested_scope": "project:docs",
            "objective": "Index new local project sources and previous run context.",
        },
        {
            "id": "enrich_graph",
            "agent": "Memory",
            "task_type": "schema_transform",
            "complexity": "low",
            "risk": "medium",
            "privacy": "private",
            "action_type": "graph_node_add",
            "requested_scope": "graph:night-queue",
            "objective": "Create local knowledge graph enrichment candidates from indexed sources.",
        },
        {
            "id": "update_project_context",
            "agent": "Memory",
            "task_type": "small_summary",
            "complexity": "low",
            "risk": "medium",
            "privacy": "private",
            "action_type": "memory_store",
            "requested_scope": "memory:project-context",
            "objective": "Update local project context as reviewable memory.",
        },
        {
            "id": "detect_missing_components",
            "agent": "Planner",
            "task_type": "housekeeping",
            "complexity": "low",
            "risk": "medium",
            "privacy": "normal",
            "action_type": "task_create",
            "requested_scope": "task:missing-components",
            "objective": "Detect missing Leon components and record reviewable local tasks.",
        },
        {
            "id": "collect_opportunities",
            "agent": "Tool/Connector",
            "task_type": "housekeeping",
            "complexity": "low",
            "risk": "low",
            "privacy": "normal",
            "action_type": "cache_build",
            "requested_scope": "cache:opportunities",
            "objective": "Collect opportunities into a delete-capable local queue cache.",
        },
        {
            "id": "apply_controlled_self_improvement",
            "agent": "Code/Improvement",
            "task_type": "coding",
            "complexity": "medium",
            "risk": "medium",
            "privacy": "private",
            "action_type": "modify_files",
            "requested_scope": "project:file:self-improvement",
            "objective": "Review a local script improvement; patch execution and measured test evidence are not implemented.",
            "policy_metadata": {
                "diff_limited": False,
                "tests_passed": False,
                "self_improvement": True,
            },
        },
        {
            "id": "prepare_risky_proposals",
            "agent": "Safety/Governance",
            "task_type": "safety_governance",
            "complexity": "medium",
            "risk": "medium",
            "privacy": "private",
            "action_type": "task_create",
            "requested_scope": "task:risky-proposals",
            "objective": "Prepare reviewable proposals for risky night improvements without executing them.",
            "proposed_risky_actions": [
                {
                    "id": "night_improvement_patch",
                    "action_type": "modify_files",
                    "requested_scope": "project:file:night-improvement",
                    "risk_class": "R3",
                    "summary": "Prepare a bounded local improvement patch after tests are known to pass.",
                },
                {
                    "id": "external_research_connector_write",
                    "action_type": "external_write",
                    "requested_scope": "external:connector:write",
                    "risk_class": "R4",
                    "summary": "Promote connector-sourced opportunity data into an external system.",
                },
                {
                    "id": "model_download",
                    "action_type": "install",
                    "requested_scope": "package:model-download",
                    "risk_class": "R5",
                    "summary": "Download or install a large local model for overnight work.",
                },
            ],
        },
    ]
    actions: list[dict[str, Any]] = []
    for action in raw_actions:
        route = choose_route(
            task_type=action["task_type"],
            complexity=action["complexity"],
            risk=action["risk"],
            privacy=action["privacy"],
            budget_mode=budget_mode,
            local_gpu_ready=local_gpu_ready,
        )
        actions.append({**action, "model_route": route})
    return actions


class NightQueueScheduler:
    def __init__(self, store: ControlPlaneStore):
        self.store = store

    def run_once(
        self,
        *,
        allowed_risk_classes: list[str] | None = None,
        requested_actions: list[str] | None = None,
        budget_mode: str = "economy",
        local_gpu_ready: bool = False,
    ) -> dict[str, Any]:
        allowed = set(allowed_risk_classes or DEFAULT_ALLOWED_RISK_CLASSES)
        actions = build_night_queue_actions(budget_mode=budget_mode, local_gpu_ready=local_gpu_ready)
        requested = set(requested_actions or [])
        if requested:
            actions = [action for action in actions if action["id"] in requested]
        selected_agents = _unique([str(action["agent"]) for action in actions])
        selected_models = [
            {
                "action_id": action["id"],
                "agent": action["agent"],
                "provider": action["model_route"]["provider"],
                "route": action["model_route"]["route"],
                "model": action["model_route"]["model"],
                "reason": action["model_route"]["reason"],
                "estimated_cost": action["model_route"].get("estimated_cost", {}),
            }
            for action in actions
        ]
        policy_limits = {
            "allowed_risk_classes": sorted(allowed),
            "default_allowed_risk_classes": DEFAULT_ALLOWED_RISK_CLASSES,
            "disallowed_behavior": "record_failure_and_prepare_reviewable_proposal",
        }
        run_id = self.store.start_night_queue_run(
            selected_agents=selected_agents,
            selected_models=selected_models,
            cost_estimate=_estimate_queue_cost(actions),
            policy_limits=policy_limits,
        )

        action_results: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        sources: list[dict[str, Any]] = []
        changes: list[dict[str, Any]] = []
        proposals: list[dict[str, Any]] = []
        state = self.store.get_state()
        indexed_sources = _default_sources(state)

        for action in actions:
            policy = evaluate_action_policy(
                action_type=action["action_type"],
                requested_scope=action["requested_scope"],
                metadata=action.get("policy_metadata") if isinstance(action.get("policy_metadata"), dict) else None,
            )
            if policy["risk_class"] not in allowed:
                result = self._policy_block(action, policy, run_id, reason="risk_class_not_allowed_for_night_queue")
                action_results.append(result)
                failures.append(result["failure"])
                proposals.extend(result.get("proposals", []))
                continue
            if not policy["execution_allowed"]:
                result = self._policy_block(action, policy, run_id, reason="risk_policy_did_not_allow_autonomous_execution")
                action_results.append(result)
                failures.append(result["failure"])
                proposals.extend(result.get("proposals", []))
                continue
            try:
                result = self._execute_action(action, run_id=run_id, state=state, indexed_sources=indexed_sources)
                result["policy"] = policy
                action_results.append(result)
                sources.extend(result.get("sources", []))
                changes.extend(result.get("changes", []))
                proposals.extend(result.get("proposals", []))
            except Exception as exc:  # pragma: no cover - defensive queue bookkeeping
                failure = {
                    "action_id": action["id"],
                    "status": "failed",
                    "reason": str(exc),
                    "risk_class": policy["risk_class"],
                    "recovery_suggestions": _recovery_suggestions(
                        reason=str(exc),
                        risk_class=str(policy["risk_class"]),
                        policy_decision=str(policy.get("decision") or ""),
                    ),
                }
                action_results.append({"action_id": action["id"], "status": "failed", "failure": failure, "policy": policy})
                failures.append(failure)

        rollback_status = self._summarize_rollback(changes)
        final_status = "succeeded"
        if failures:
            final_status = "completed_with_attention" if len(failures) < len(actions) else "failed"
        elif proposals:
            final_status = "completed_with_attention"
        try:
            memory_context = self.store.retrieve_memory(
                _brief_memory_query(
                    action_results=action_results,
                    failures=failures,
                    sources=sources,
                    changes=changes,
                    proposals=proposals,
                ),
                scope="context",
                limit=5,
                actor_type="system",
                actor_id="night-queue-brief-memory-context",
            )
        except Exception as exc:  # pragma: no cover - defensive brief enrichment
            memory_context = {
                "answer_status": "unavailable",
                "confidence": 0,
                "source_refs": [],
                "related_graph_entries": [],
                "conflicts": [],
                "metrics": {"match_count": 0, "relevance_score": 0},
                "reason": str(exc),
            }
        morning_brief = build_morning_brief(
            run_id=run_id,
            status=final_status,
            action_results=action_results,
            failures=failures,
            sources=sources,
            changes=changes,
            proposals=proposals,
            selected_models=selected_models,
            cost_estimate=_estimate_queue_cost(actions),
            rollback_status=rollback_status,
            memory_context=memory_context,
            generated_by="night_queue",
        )
        self.store.complete_night_queue_run(
            run_id,
            status=final_status,
            action_results=action_results,
            failures=failures,
            sources=sources,
            changes=changes,
            rollback_status=rollback_status,
            morning_brief=morning_brief,
        )
        return redact_value({**morning_brief, "id": run_id})

    def _policy_block(self, action: dict[str, Any], policy: dict[str, Any], run_id: str, *, reason: str) -> dict[str, Any]:
        failure = {
            "action_id": action["id"],
            "status": "blocked_by_policy",
            "reason": reason,
            "risk_class": policy["risk_class"],
            "policy_decision": policy["decision"],
            "policy_reason": policy["reason"],
            "recovery_suggestions": _recovery_suggestions(
                reason=reason,
                risk_class=str(policy["risk_class"]),
                policy_decision=str(policy["decision"]),
            ),
        }
        proposal = {
            "id": f"{run_id}:{action['id']}",
            "title": f"Review night queue action: {action['objective']}",
            "risk_class": policy["risk_class"],
            "policy_decision": policy["decision"],
            "requires_review": True,
            "execution_allowed": False,
        }
        return {
            "action_id": action["id"],
            "agent": action["agent"],
            "status": "blocked_by_policy",
            "policy": policy,
            "failure": failure,
            "proposals": [proposal],
            "changes": [],
            "sources": [],
        }

    def _execute_action(
        self,
        action: dict[str, Any],
        *,
        run_id: str,
        state: dict[str, Any],
        indexed_sources: list[dict[str, str]],
    ) -> dict[str, Any]:
        if action["id"] == "index_new_sources":
            return {
                "action_id": action["id"],
                "agent": action["agent"],
                "status": "succeeded",
                "summary": f"Indexed {len(indexed_sources)} source reference(s) for the night queue.",
                "sources": indexed_sources,
                "changes": [],
            }
        if action["id"] == "enrich_graph":
            memory_id = self.store.create_memory_item(
                {
                    "status": "candidate",
                    "memory_type": "project_fact",
                    "content": f"Night queue {run_id} indexed local project sources and prepared graph enrichment candidates.",
                    "source": f"night_queue:{run_id}:enrich_graph",
                    "confidence": 0.62,
                    "sensitivity": "low",
                    "privacy_level": "private",
                    "graph_entities": ["Leon Night Queue", "Project Sources"],
                    "graph_edges": [
                        {
                            "subject": "Leon Night Queue",
                            "predicate": "indexed",
                            "object": "Project Sources",
                            "confidence": 0.62,
                            "source": f"night_queue:{run_id}",
                        }
                    ],
                },
                actor_type="system",
                actor_id="night-queue-scheduler",
            )
            return {
                "action_id": action["id"],
                "agent": action["agent"],
                "status": "succeeded",
                "summary": "Created reviewable memory and graph enrichment candidate.",
                "sources": indexed_sources[:5],
                "changes": [{"type": "memory_item", "id": memory_id, "rollback": "scrub_supported"}],
            }
        if action["id"] == "update_project_context":
            open_tasks = [task for task in state.get("tasks", []) if task.get("status") not in {"done", "rejected"}]
            memory_id = self.store.create_memory_item(
                {
                    "status": "candidate",
                    "memory_type": "working",
                    "content": (
                        f"Night queue project context snapshot: {len(open_tasks)} open task(s), "
                        f"{len(state.get('approvals', []))} approval record(s), "
                        f"{len(state.get('memory_items', []))} existing memory item(s)."
                    ),
                    "source": f"night_queue:{run_id}:update_project_context",
                    "confidence": 0.68,
                    "sensitivity": "low",
                    "privacy_level": "private",
                    "graph_entities": ["Leon Project Context", "Night Queue"],
                },
                actor_type="system",
                actor_id="night-queue-scheduler",
            )
            return {
                "action_id": action["id"],
                "agent": action["agent"],
                "status": "succeeded",
                "summary": "Created reviewable project context memory.",
                "sources": indexed_sources[:5],
                "changes": [{"type": "memory_item", "id": memory_id, "rollback": "scrub_supported"}],
            }
        if action["id"] == "detect_missing_components":
            preview = compose_ui(
                route="morning_brief",
                component_need="MorningBriefSection",
                risk_level="medium",
            )
            missing_record = (preview.get("missing_component_records") or [{}])[0]
            registered = self.store.register_missing_component_need(
                requested_component=str(missing_record.get("requested_component") or "MorningBriefSection"),
                requested_capability=(
                    "Render generated morning brief sections, expandable details, missing UI capability notes, "
                    "sources, logs, policy decisions, costs, and rollback data."
                ),
                route=str(missing_record.get("route") or "morning_brief"),
                space=str(missing_record.get("space") or preview.get("space") or "home"),
                task_status=str(missing_record.get("task_status") or ""),
                risk_level=str(missing_record.get("risk_level") or "medium"),
                fallback_component_ids=missing_record.get("fallback_component_ids") or preview.get("component_ids") or [],
                context={
                    "source": "night_queue.detect_missing_components",
                    "composition": preview,
                    "acceptance_story": "US-021",
                    "related_prd_refs": ["tasks/prd.json#US-009", "tasks/prd.json#US-020", "tasks/prd.json#US-021"],
                    "temporary_alternative": preview.get("temporary_alternative") or {},
                },
                source_ref="tasks/prd.json#US-021",
                run_id=run_id,
                actor_type="system",
                actor_id="night-queue-scheduler",
            )
            change = {
                "type": "missing_component",
                "id": registered["id"],
                "requested_component": registered["requested_component"],
                "requested_capability": registered["requested_capability"],
                "fallback_component_ids": registered["fallback_component_ids"],
                "task_id": registered["task_id"],
                "status": registered["status"],
                "run_id": run_id,
                "rollback": "local_task_review_or_delete",
            }
            return {
                "action_id": action["id"],
                "agent": action["agent"],
                "status": "succeeded",
                "summary": "Detected missing morning brief UI capability and registered a local development task.",
                "sources": [{"type": "prd", "ref": "tasks/prd.json#US-021"}],
                "missing_components": [registered],
                "changes": [change],
            }
        if action["id"] == "collect_opportunities":
            rollback_id = self.store.record_cache_work(
                cache_key=f"night_queue:{run_id}:opportunities",
                summary="Night queue opportunity cache can be deleted without durable external effects.",
                delete_payload={"delete_cache_key": f"night_queue:{run_id}:opportunities"},
                actor_type="system",
                actor_id="night-queue-scheduler",
            )
            return {
                "action_id": action["id"],
                "agent": action["agent"],
                "status": "succeeded",
                "summary": "Collected local opportunity candidates into delete-capable cache metadata.",
                "sources": indexed_sources[:5],
                "changes": [{"type": "cache", "id": f"night_queue:{run_id}:opportunities", "rollback_record_id": rollback_id, "rollback": "delete_supported"}],
            }
        if action["id"] == "apply_controlled_self_improvement":
            # Do not let a future policy/config change revive synthetic success.
            # A real executor must apply a bounded patch and capture test evidence.
            raise NotImplementedError(
                "Controlled self-improvement execution is unavailable: "
                "no patch was applied and no tests were run."
            )
        if action["id"] == "prepare_risky_proposals":
            proposals = []
            phase_ids = {str(phase.get("id") or "") for phase in state.get("phases", [])}
            phase_id = "phase-6" if "phase-6" in phase_ids else None
            for proposed in action.get("proposed_risky_actions", []):
                proposed_policy = evaluate_action_policy(
                    action_type=str(proposed.get("action_type") or ""),
                    requested_scope=str(proposed.get("requested_scope") or ""),
                    risk_class=str(proposed.get("risk_class") or "") or None,
                )
                proposals.append({
                    **proposed,
                    "policy": proposed_policy,
                    "execution_allowed": False,
                    "requires_review": True,
                })
            task_id = self.store.create_task(
                title="Review risky night queue proposals",
                goal="Review R3-R5 night queue proposals before any code, external write, install, model download, account, secret, public, or money action occurs.",
                phase_id=phase_id,
                owner="Safety/Governance",
                status="new",
                priority="P1",
                risk_level="medium",
                approval_required=True,
                acceptance_criteria="Every proposed risky action has risk class, policy decision, expected effect, and rollback or compensation requirement before execution.",
                source_refs=[f"night_queue:{run_id}", "config/autonomy-policy.json"],
                actor_type="system",
                actor_id="night-queue-scheduler",
            )
            return {
                "action_id": action["id"],
                "agent": action["agent"],
                "status": "succeeded",
                "summary": "Prepared risky proposals for review without executing them.",
                "sources": [{"type": "policy", "ref": "config/autonomy-policy.json"}],
                "changes": [{"type": "task", "id": task_id, "rollback": "local_task_review_or_delete"}],
                "proposals": proposals,
            }
        raise ValueError(f"Unsupported night queue action: {action['id']}")

    def _summarize_rollback(self, changes: list[dict[str, Any]]) -> dict[str, Any]:
        statuses = _unique([str(change.get("rollback") or "") for change in changes])
        return {
            "recorded": True,
            "change_count": len(changes),
            "statuses": statuses,
            "requires_attention": any(status in {"missing", "compensation_unavailable"} for status in statuses),
        }
