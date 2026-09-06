from __future__ import annotations

from typing import Any


SUPPORTED_AGENT_RUN_ROLES = [
    "Planner",
    "Research",
    "Memory",
    "Code/Improvement",
    "Review",
    "Tool/Connector",
    "UI Composition",
    "Safety/Governance",
]

ROLE_ALIASES = {
    "planner agent": "Planner",
    "research agent": "Research",
    "memory agent": "Memory",
    "builder agent": "Code/Improvement",
    "backend agent": "Code/Improvement",
    "code agent": "Code/Improvement",
    "code/improvement": "Code/Improvement",
    "mock builder agent": "Code/Improvement",
    "review agent": "Review",
    "reviewer agent": "Review",
    "qa agent": "Review",
    "tool agent": "Tool/Connector",
    "connector agent": "Tool/Connector",
    "tool/connector": "Tool/Connector",
    "ui agent": "UI Composition",
    "frontend agent": "UI Composition",
    "ui composition": "UI Composition",
    "safety agent": "Safety/Governance",
    "security agent": "Safety/Governance",
    "governance agent": "Safety/Governance",
    "safety/governance": "Safety/Governance",
}


def normalize_agent_run_role(agent_role: str) -> str:
    role = str(agent_role or "").strip()
    if role in SUPPORTED_AGENT_RUN_ROLES:
        return role
    lowered = role.lower()
    if lowered in ROLE_ALIASES:
        return ROLE_ALIASES[lowered]
    for marker, supported in ROLE_ALIASES.items():
        if marker in lowered:
            return supported
    return "Code/Improvement"


def estimate_agent_run_cost(*, model_route: dict[str, Any], external_calls_made: bool = False) -> dict[str, Any]:
    provider = str(model_route.get("provider") or "unknown")
    route = str(model_route.get("route") or "unknown")
    model = str(model_route.get("model") or "unknown")
    projected = model_route.get("estimated_cost") if isinstance(model_route.get("estimated_cost"), dict) else {}
    projected_cost = {
        "currency": str(projected.get("currency") or "USD"),
        "estimated_min": projected.get("estimated_min"),
        "estimated_max": projected.get("estimated_max"),
        "basis": str(projected.get("basis") or "No route-level cost estimate configured."),
        "relative_cost": str(model_route.get("relative_cost") or "unknown"),
        "provider": provider,
        "route": route,
        "model": model,
    }
    if not external_calls_made:
        return {
            "currency": "USD",
            "estimated_min": 0,
            "estimated_max": 0,
            "estimation_status": "not_metered",
            "basis": "Local mock runner records the selected model route but makes no provider calls.",
            "provider": provider,
            "route": route,
            "model": model,
            "model_choice": projected_cost,
            "projected_provider_call": projected_cost,
            "cost_warning": model_route.get("cost_warning") or {},
        }
    return {
        "currency": projected_cost["currency"],
        "estimated_min": projected_cost["estimated_min"],
        "estimated_max": projected_cost["estimated_max"],
        "estimation_status": "estimated_until_metered",
        "basis": projected_cost["basis"],
        "provider": provider,
        "route": route,
        "model": model,
        "model_choice": projected_cost,
        "projected_provider_call": projected_cost,
        "cost_warning": model_route.get("cost_warning") or {},
    }


def next_action_for_review_status(review_status: str) -> str:
    if review_status == "accepted":
        return "task_can_move_to_review_or_done"
    if review_status == "changes_requested":
        return "revise_agent_run_output"
    if review_status == "rejected":
        return "choose_new_agent_or_task_plan"
    return "review_agent_run"
