from __future__ import annotations

from typing import Any


def _short_title(prefix: str, text: str) -> str:
    clean = " ".join(text.strip().split())
    if len(clean) > 72:
        clean = clean[:69].rstrip() + "..."
    return f"{prefix}: {clean}"


def _priority(value_score: int, risk_level: str) -> str:
    if risk_level == "high":
        return "P0"
    if value_score >= 65:
        return "P0"
    if value_score >= 45:
        return "P1"
    return "P2"


def build_orchestration_proposal(
    *,
    decision: dict[str, Any],
    routing_decision_id: str | None = None,
) -> dict[str, Any]:
    """Turn a routing decision into a reviewable local proposal.

    This function is deterministic and side-effect free. It never executes
    tools, agents, installs, account connections, OpenAI calls, or external
    writes. Persistence/audit is handled by ControlPlaneStore.
    """

    route = str(decision["route"])
    text = str(decision.get("input_text_redacted") or "")
    value_score = int(decision.get("value_score") or 0)
    value_score_inputs = decision.get("value_score_inputs") if isinstance(decision.get("value_score_inputs"), dict) else {}
    value_band = decision.get("value_band") if isinstance(decision.get("value_band"), dict) else {}
    retrieved_context = decision.get("retrieved_context") if isinstance(decision.get("retrieved_context"), dict) else {}
    risk_level = str(decision.get("risk_level") or "low")
    model_route = decision.get("model_route") or {}
    execution_path = decision.get("execution_path") if isinstance(decision.get("execution_path"), dict) else {}
    value_context = {
        "decision_value_score": value_score,
        "value_score_inputs": value_score_inputs,
        "value_band": value_band,
        "retrieved_context": retrieved_context,
        "execution_path": execution_path,
    }
    base = {
        "routing_decision_id": routing_decision_id,
        "route": route,
        "summary": _short_title("Route", text),
        **value_context,
        "execution_allowed": False,
        "external_calls_made": False,
        "secret_values_read": False,
        "requires_user_review": route in {
            "clarification_required",
            "memory_retrieval",
            "shell_agent_flow",
            "research_agent",
            "task_queue",
            "approval_required",
        },
        "safety_notes": [
            "Proposal generation does not execute tools, agents, external calls, installs, or writes.",
            "Secrets remain redacted; only input_text_redacted is used.",
            "Any future execution must pass task/approval gates and create its own audit events.",
        ],
        "model_route": {
            "provider": model_route.get("provider"),
            "route": model_route.get("route"),
            "model": model_route.get("model"),
            "reason": model_route.get("reason"),
        },
        "task_payload": None,
        "approval_payload": None,
        "proposed_tasks": [],
        "proposed_approvals": [],
        "safe_redirect": None,
        "safe_response": None,
        "recommended_next_step": "review_only",
    }

    if route == "direct_answer":
        base.update(
            {
                "summary": _short_title("Direct antwoord", text),
                "requires_user_review": False,
                "recommended_next_step": "answer_in_chat",
                "safe_redirect": "Handle as a normal direct response. No task or approval card is needed.",
                "safe_response": "Deze vraag kan direct in chat worden beantwoord zonder task, tool of approval.",
            }
        )
        return base

    if route == "clarification_required":
        base.update(
            {
                "summary": _short_title("Clarify", text),
                "requires_user_review": False,
                "recommended_next_step": "ask_clarification",
                "safe_redirect": "Ask for the missing context, scope, target, or desired output before creating executable work.",
                "safe_response": "Stel eerst een verduidelijkingsvraag. Maak nog geen taak, approval of agent-run.",
                "clarification_questions": decision.get("clarification_questions") or [],
                "ambiguity_reasons": decision.get("ambiguity_reasons") or [],
            }
        )
        return base

    if route == "quick_tool_use":
        task_payload = {
            "title": _short_title("Local tool check", text),
            "goal": "Voer alleen een bounded lokale/read-only check uit en toon resultaat; geen externe write of secretwaarde tonen.",
            "phase_id": "phase-2",
            "owner": "Tool/Backend Agent",
            "status": "planned",
            "priority": _priority(value_score, risk_level),
            "risk_level": risk_level,
            "approval_required": False,
            **value_context,
            "allowed_actions": ["read_control_plane_state", "validate_local_metadata", "produce_result"],
            "forbidden_actions": ["read_raw_secrets", "external_api_calls", "write_external_systems", "start_agent_run"],
            "acceptance_criteria": "Toolactie is read-only of lokale control-plane metadata; output bevat geen secrets; audit blijft valide.",
        }
        base.update(
            {
                "summary": _short_title("Read-only/local tool voorstel", text),
                "requires_user_review": True,
                "recommended_next_step": "bounded_local_tool_preview",
                "task_payload": task_payload,
                "proposed_tasks": [task_payload],
            }
        )
        return base

    if route == "memory_retrieval":
        task_payload = {
            "title": _short_title("Memory lookup", text),
            "goal": "Haal alleen reviewed memory/source context op, toon provenance en conflicts, en verberg secretachtige waarden.",
            "phase_id": "phase-6",
            "owner": "Memory Agent",
            "status": "planned",
            "priority": _priority(value_score, risk_level),
            "risk_level": risk_level,
            "approval_required": False,
            **value_context,
            "allowed_actions": ["retrieve_reviewed_memory", "show_source_refs", "summarize_conflicts"],
            "forbidden_actions": ["write_memory_without_review", "read_raw_secrets", "external_api_calls", "start_shell_commands"],
            "acceptance_criteria": "Antwoord bevat memory/source provenance, conflictmelding waar relevant, en geen raw secrets.",
        }
        base.update(
            {
                "summary": _short_title("Memory retrieval voorstel", text),
                "recommended_next_step": "create_memory_retrieval_task",
                "task_payload": task_payload,
                "proposed_tasks": [task_payload],
            }
        )
        return base

    if route == "shell_agent_flow":
        task_payload = {
            "title": _short_title("Agent flow", text),
            "goal": "Maak een bounded lokale shell/agent taak met scope, verificatie en forbidden actions; voer nog geen shellcommando's uit.",
            "phase_id": "phase-2",
            "owner": "Code/Improvement Agent",
            "status": "planned",
            "priority": _priority(value_score, risk_level),
            "risk_level": risk_level,
            "approval_required": False,
            **value_context,
            "allowed_actions": ["read_workspace", "prepare_patch_plan", "propose_tests", "produce_reviewable_task"],
            "forbidden_actions": ["execute_shell_commands_from_router", "install_dependencies", "external_api_calls", "read_raw_secrets", "write_external_systems"],
            "acceptance_criteria": "Task beschrijft scope, expected files, verification commands, rollback expectations en safety gates voordat agent execution start.",
        }
        base.update(
            {
                "summary": _short_title("Shell/agent flow voorstel", text),
                "recommended_next_step": "create_shell_agent_task",
                "task_payload": task_payload,
                "proposed_tasks": [task_payload],
            }
        )
        return base

    if route == "research_agent":
        task_payload = {
            "title": _short_title("Research", text),
            "goal": "Onderzoek de vraag met bronnen, trade-offs, risico's en een concreet advies. Geen installs of accountkoppelingen.",
            "phase_id": "phase-6",
            "owner": "Research Agent",
            "status": "planned",
            "priority": _priority(value_score, risk_level),
            "risk_level": risk_level,
            "approval_required": False,
            **value_context,
            "allowed_actions": ["read_project_context", "perform_source_review", "produce_research_report"],
            "forbidden_actions": ["install_dependencies", "connect_accounts", "write_external_systems", "spend_money", "start_gpu_jobs"],
            "acceptance_criteria": "Resultaat bevat bronnen, datum gecontroleerd, onzekerheden, risico's en aanbevolen vervolgstap; geen externe write-acties.",
        }
        base.update(
            {
                "summary": _short_title("Research taak voorstel", text),
                "recommended_next_step": "create_research_task",
                "task_payload": task_payload,
                "proposed_tasks": [task_payload],
            }
        )
        return base

    if route == "task_queue":
        task_payload = {
            "title": _short_title("Queued", text),
            "goal": "Zet dit werk als geplande lokale taak klaar; voer niets automatisch uit zonder eigen route/approval check.",
            "phase_id": "phase-6",
            "owner": "Queue Agent",
            "status": "planned",
            "priority": _priority(value_score, risk_level),
            "risk_level": risk_level,
            "approval_required": False,
            **value_context,
            "allowed_actions": ["create_backlog_item", "wait_for_schedule", "produce_status_update"],
            "forbidden_actions": ["execute_task_automatically", "external_api_calls", "read_raw_secrets", "write_external_systems"],
            "acceptance_criteria": "Taak is zichtbaar in backlog met owner, risico, doel, acceptatiecriteria en audit trail.",
        }
        base.update(
            {
                "summary": _short_title("Queue taak voorstel", text),
                "recommended_next_step": "create_queued_task",
                "task_payload": task_payload,
                "proposed_tasks": [task_payload],
            }
        )
        return base

    if route == "approval_required":
        approval_payload = dict(decision.get("approval_payload") or {})
        approval_payload.setdefault("action_type", "routing_gate")
        approval_payload.setdefault("summary", _short_title("Approval", text))
        approval_payload.setdefault("reason", decision.get("approval_reason") or "High-impact route requires explicit approval.")
        approval_payload.setdefault("affected_systems", "Unknown until reviewed")
        approval_payload.setdefault("permissions", "No execution permission granted yet")
        approval_payload.setdefault("external_effect", decision.get("external_effect") or "write")
        approval_payload.setdefault("cost_estimate", "unknown until reviewed")
        approval_payload.setdefault("risk_level", risk_level)
        approval_payload.setdefault("risk_class", decision.get("risk_class") or "R4")
        approval_payload.setdefault("expected_change", f"Prepare a bounded execution plan for: {text}")
        approval_payload.setdefault("rollback_plan", "No action has been executed. Reject or revise the execution plan.")
        approval_payload.setdefault("failure_mode", "If approval is rejected or expires, no action runs; the plan must be revised before retry.")
        task_payload = {
            "title": _short_title("Approval gated", text),
            "goal": "Maak een uitvoeringsplan voor deze high-impact actie, maar wacht op expliciete approval voor uitvoering.",
            "phase_id": "phase-5",
            "owner": "Codex/User",
            "status": "waiting_for_approval",
            "priority": "P0",
            "risk_level": risk_level,
            "approval_required": True,
            **value_context,
            "allowed_actions": ["write_execution_plan", "request_approval", "produce_preview"],
            "forbidden_actions": ["execute_external_action", "consume_approval", "read_raw_secrets", "spend_money", "connect_accounts_without_approval"],
            "acceptance_criteria": "Geen uitvoering zonder consumed approval-id; plan bevat scope, risico, kosten, rollback en verificatie.",
        }
        base.update(
            {
                "summary": _short_title("Approval gate voorstel", text),
                "recommended_next_step": "create_task_and_approval_card",
                "task_payload": task_payload,
                "approval_payload": approval_payload,
                "proposed_tasks": [task_payload],
                "proposed_approvals": [approval_payload],
            }
        )
        return base

    if route == "refuse_redirect":
        base.update(
            {
                "summary": _short_title("Weiger veilig", text),
                "requires_user_review": False,
                "recommended_next_step": "refuse_and_redirect",
                "safe_redirect": "Refuse the unsafe request and offer a safe, bounded alternative. Do not create executable work.",
                "safe_response": "Weiger dit verzoek en bied alleen een veilige, toegestane variant aan.",
            }
        )
        return base

    raise ValueError(f"Unsupported route for orchestration proposal: {route}")
