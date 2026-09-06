from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from leon_control_plane.local_gpu_validation import normalize_local_gpu_policy


REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = REPO_ROOT / "config" / "model-routing.json"

LOW_COST_TASK_TYPES = {
    "classification",
    "extraction",
    "housekeeping",
    "schema_transform",
    "small_summary",
    "simple_summary",
}

BALANCED_TASK_TYPES = {
    "tool_making",
    "debugging",
    "coding",
    "documentation",
    "routine_research",
}

PREMIUM_TASK_TYPES = {
    "architecture",
    "complex_planning",
    "code_review",
    "security_review",
    "high_value_decision",
    "sensitive_decision",
    "safety_governance",
}

DEFAULT_COST_POLICY = {
    "currency": "USD",
    "basis": "Planning estimate for one bounded Leon agent/model call before exact token metering is available.",
    "warning_threshold_estimated_max": 0.08,
}

DEFAULT_ROUTE_COSTS = {
    "cheap": {"relative_cost": "low", "estimated_min": 0.001, "estimated_max": 0.015},
    "balanced": {"relative_cost": "medium", "estimated_min": 0.01, "estimated_max": 0.08},
    "premium": {"relative_cost": "high", "estimated_min": 0.05, "estimated_max": 0.35},
    "local_gpu": {"relative_cost": "local_resource", "estimated_min": 0, "estimated_max": 0},
}

DEFAULT_LOCAL_GPU_RUNTIME_POLICY = {
    "max_latency_ms": 3500,
    "fallback_on": ["local_failure", "latency_exceeds_threshold"],
}

LOCAL_FAILURE_STATUSES = {"failed", "failure", "error", "unhealthy", "timeout", "too_slow"}


def load_policy() -> dict[str, Any]:
    with POLICY_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _coarse_risk(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"high", "r4", "r5"}:
        return "high"
    if normalized in {"medium", "r2", "r3"}:
        return "medium"
    return "low"


def _cost_policy(policy: dict[str, Any]) -> dict[str, Any]:
    configured = policy.get("cost_policy") if isinstance(policy.get("cost_policy"), dict) else {}
    return {**DEFAULT_COST_POLICY, **configured}


def _route_cost_profile(policy: dict[str, Any], route: str) -> dict[str, Any]:
    model = (policy.get("cloud_models") or {}).get(route, {})
    configured_estimate = model.get("default_run_estimate") if isinstance(model.get("default_run_estimate"), dict) else {}
    fallback = DEFAULT_ROUTE_COSTS.get(route, DEFAULT_ROUTE_COSTS["balanced"])
    cost_policy = _cost_policy(policy)
    estimated_min = configured_estimate.get("estimated_min", fallback["estimated_min"])
    estimated_max = configured_estimate.get("estimated_max", fallback["estimated_max"])
    try:
        estimated_min = round(float(estimated_min), 4)
    except (TypeError, ValueError):
        estimated_min = float(fallback["estimated_min"])
    try:
        estimated_max = round(float(estimated_max), 4)
    except (TypeError, ValueError):
        estimated_max = float(fallback["estimated_max"])
    return {
        "currency": str(cost_policy["currency"]),
        "relative_cost": str(model.get("relative_cost") or fallback["relative_cost"]),
        "estimated_min": estimated_min,
        "estimated_max": estimated_max,
        "basis": str(cost_policy["basis"]),
        "warning_threshold_estimated_max": float(cost_policy["warning_threshold_estimated_max"]),
    }


def _cost_warning(*, route: str, reason: str, cost_profile: dict[str, Any]) -> dict[str, Any]:
    estimated_max = float(cost_profile.get("estimated_max") or 0)
    threshold = float(cost_profile.get("warning_threshold_estimated_max") or 0)
    warning_required = route == "premium" or estimated_max > threshold
    if not warning_required:
        return {
            "required": False,
            "severity": "none",
            "message": "No premium cost warning required for this route.",
            "reason": reason,
        }
    return {
        "required": True,
        "severity": "attention",
        "message": (
            f"Premium/expensive route selected. Estimated provider cost for a bounded run: "
            f"{cost_profile['currency']} {cost_profile['estimated_min']:.3f}-"
            f"{cost_profile['estimated_max']:.3f}. Review before execution."
        ),
        "reason": reason,
    }


def _route_decision(
    *,
    selected_runtime: str,
    primary_route: str,
    final_route: str,
    reason: str,
    fallback_active: bool,
    local_route_allowed: bool,
    local_attempted: bool,
) -> dict[str, Any]:
    if fallback_active:
        label = "API fallback"
    elif selected_runtime == "local_gpu":
        label = "Local M40/GPU"
    else:
        label = "API route"
    return {
        "label": label,
        "selected_runtime": selected_runtime,
        "primary_route": primary_route,
        "final_route": final_route,
        "reason": reason,
        "user_visible": True,
        "fallback_active": fallback_active,
        "local_route_allowed": local_route_allowed,
        "local_attempted": local_attempted,
    }


def _runtime_policy(local_gpu_policy: dict[str, Any]) -> dict[str, Any]:
    configured = local_gpu_policy.get("runtime_policy") if isinstance(local_gpu_policy.get("runtime_policy"), dict) else {}
    output = {**DEFAULT_LOCAL_GPU_RUNTIME_POLICY, **configured}
    try:
        output["max_latency_ms"] = int(output.get("max_latency_ms") or DEFAULT_LOCAL_GPU_RUNTIME_POLICY["max_latency_ms"])
    except (TypeError, ValueError):
        output["max_latency_ms"] = DEFAULT_LOCAL_GPU_RUNTIME_POLICY["max_latency_ms"]
    output["fallback_on"] = [
        str(item)
        for item in (output.get("fallback_on") or DEFAULT_LOCAL_GPU_RUNTIME_POLICY["fallback_on"])
    ]
    return output


def _normalize_latency_ms(value: float | int | str | None) -> int | None:
    if value in {None, ""}:
        return None
    try:
        latency = int(float(value))
    except (TypeError, ValueError):
        return None
    return latency if latency >= 0 else None


def _local_runtime_fallback_reason(
    *,
    local_route_status: str,
    local_latency_ms: int | None,
    max_latency_ms: int,
) -> str | None:
    status = str(local_route_status or "").strip().lower()
    if status in LOCAL_FAILURE_STATUSES:
        return f"Local GPU route reported {status}; using API fallback."
    if local_latency_ms is not None and local_latency_ms > max_latency_ms:
        return (
            f"Local GPU route latency {local_latency_ms}ms exceeded "
            f"{max_latency_ms}ms threshold; using API fallback."
        )
    return None


def _local_gpu_diagnostics(
    *,
    requested: bool,
    considered: bool,
    selected: bool,
    local_gpu_policy: dict[str, Any],
    reason: str,
    local_route_status: str,
    local_latency_ms: int | None,
    max_latency_ms: int | None,
    fallback_active: bool = False,
) -> dict[str, Any]:
    validation = local_gpu_policy.get("validation", {})
    return {
        "requested": requested,
        "considered": considered,
        "selected": selected,
        "route_allowed": bool(local_gpu_policy.get("route_allowed")),
        "fallback_active": fallback_active,
        "validation": validation,
        "local_route_status": str(local_route_status or "not_attempted"),
        "local_latency_ms": local_latency_ms,
        "max_latency_ms": max_latency_ms,
        "reason": reason,
    }


def _build_route(policy: dict[str, Any], route: str, reason: str, approval_required: bool) -> dict[str, Any]:
    model = policy["cloud_models"][route]
    cost_profile = _route_cost_profile(policy, route)
    warning = _cost_warning(route=route, reason=reason, cost_profile=cost_profile)
    return {
        "provider": model["provider"],
        "route": route,
        "model": model["model"],
        "reasoning_effort": model["reasoning_effort"],
        "reason": reason,
        "user_visible_reason": reason,
        "approval_required": bool(approval_required),
        "relative_cost": cost_profile["relative_cost"],
        "estimated_cost": {
            "currency": cost_profile["currency"],
            "estimated_min": cost_profile["estimated_min"],
            "estimated_max": cost_profile["estimated_max"],
            "basis": cost_profile["basis"],
        },
        "cost_warning": warning,
        "selected_runtime": "api",
        "fallback": {"active": False},
        "route_decision": _route_decision(
            selected_runtime="api",
            primary_route=route,
            final_route=route,
            reason=reason,
            fallback_active=False,
            local_route_allowed=False,
            local_attempted=False,
        ),
    }


def _build_cloud_route(
    policy: dict[str, Any],
    route: str,
    reason: str,
    approval_required: bool,
    *,
    local_gpu_policy: dict[str, Any],
    local_gpu_requested: bool,
    local_gpu_skip_reason: str | None = None,
) -> dict[str, Any]:
    output = _build_route(policy, route, reason, approval_required)
    if local_gpu_requested:
        diagnostics_reason = local_gpu_skip_reason or "Local GPU was requested but API routing was selected for this task."
        output["local_gpu_diagnostics"] = {
            **_local_gpu_diagnostics(
                requested=True,
                considered=False,
                selected=False,
                local_gpu_policy=local_gpu_policy,
                reason=diagnostics_reason,
                local_route_status="not_attempted",
                local_latency_ms=None,
                max_latency_ms=_runtime_policy(local_gpu_policy)["max_latency_ms"],
            ),
        }
        output["route_decision"] = _route_decision(
            selected_runtime="api",
            primary_route="local_gpu",
            final_route=route,
            reason=diagnostics_reason,
            fallback_active=False,
            local_route_allowed=bool(local_gpu_policy.get("route_allowed")),
            local_attempted=False,
        )
    return output


def _build_local_gpu_route(
    local_gpu_policy: dict[str, Any],
    *,
    local_route_status: str,
    local_latency_ms: int | None,
    max_latency_ms: int,
) -> dict[str, Any]:
    reason = "Private/sensitive low-to-medium risk task with enabled and validated local GPU route."
    cost_profile = DEFAULT_ROUTE_COSTS["local_gpu"]
    return {
        "provider": "local",
        "route": "local_gpu",
        "model": str(local_gpu_policy.get("selected_model") or "local-policy-selected"),
        "reasoning_effort": "n/a",
        "reason": reason,
        "user_visible_reason": reason,
        "approval_required": False,
        "relative_cost": cost_profile["relative_cost"],
        "estimated_cost": {
            "currency": DEFAULT_COST_POLICY["currency"],
            "estimated_min": cost_profile["estimated_min"],
            "estimated_max": cost_profile["estimated_max"],
            "basis": "Local GPU route has no provider-call estimate; benchmark, quality, and resource cost validation are recorded in local_gpu_diagnostics.",
        },
        "cost_warning": {
            "required": False,
            "severity": "none",
            "message": "No provider cost warning required for validated local GPU route.",
            "reason": reason,
        },
        "selected_runtime": "local_gpu",
        "fallback": {"active": False},
        "route_decision": _route_decision(
            selected_runtime="local_gpu",
            primary_route="local_gpu",
            final_route="local_gpu",
            reason=reason,
            fallback_active=False,
            local_route_allowed=True,
            local_attempted=bool(local_route_status),
        ),
        "local_gpu_diagnostics": _local_gpu_diagnostics(
            requested=True,
            considered=True,
            selected=True,
            local_gpu_policy=local_gpu_policy,
            reason="Local GPU validation passed and runtime telemetry stayed within fallback limits.",
            local_route_status=local_route_status or "eligible",
            local_latency_ms=local_latency_ms,
            max_latency_ms=max_latency_ms,
        ),
    }


def _apply_api_fallback(
    output: dict[str, Any],
    *,
    fallback_reason: str,
    local_gpu_policy: dict[str, Any],
    local_route_status: str,
    local_latency_ms: int | None,
    max_latency_ms: int,
) -> dict[str, Any]:
    output["selected_runtime"] = "api_fallback"
    output["fallback"] = {
        "active": True,
        "from_route": "local_gpu",
        "to_route": output["route"],
        "reason": fallback_reason,
        "local_route_status": str(local_route_status or "unknown"),
        "local_latency_ms": local_latency_ms,
        "max_latency_ms": max_latency_ms,
    }
    output["route_decision"] = _route_decision(
        selected_runtime="api_fallback",
        primary_route="local_gpu",
        final_route=str(output["route"]),
        reason=fallback_reason,
        fallback_active=True,
        local_route_allowed=True,
        local_attempted=True,
    )
    output["user_visible_reason"] = f"{fallback_reason} API route selected: {output['reason']}"
    output["local_gpu_diagnostics"] = _local_gpu_diagnostics(
        requested=True,
        considered=True,
        selected=False,
        local_gpu_policy=local_gpu_policy,
        reason=fallback_reason,
        local_route_status=local_route_status or "unknown",
        local_latency_ms=local_latency_ms,
        max_latency_ms=max_latency_ms,
        fallback_active=True,
    )
    return output


def choose_route(
    *,
    task_type: str = "general",
    complexity: str = "medium",
    risk: str = "medium",
    budget_mode: str = "balanced",
    privacy: str = "normal",
    local_gpu_ready: bool = False,
    local_route_status: str = "",
    local_latency_ms: float | int | str | None = None,
) -> dict[str, Any]:
    policy = load_policy()
    task_type = str(task_type or "general").strip().lower()
    complexity = str(complexity or "medium").lower()
    risk = _coarse_risk(risk)
    budget_mode = str(budget_mode or "balanced").lower()
    privacy = str(privacy or "normal").lower()
    local_gpu_policy = normalize_local_gpu_policy(policy.get("local_gpu") or {})
    runtime_policy = _runtime_policy(local_gpu_policy)
    normalized_latency_ms = _normalize_latency_ms(local_latency_ms)

    route = "balanced"
    reason = "Default balanced route for useful work without premium cost."

    if task_type in LOW_COST_TASK_TYPES and risk != "high":
        route = "cheap"
        reason = "Simple classification, extraction, or housekeeping task; use lowest-cost capable model."
    elif complexity == "low" and risk == "low":
        route = "cheap"
        reason = "Low-complexity, low-risk task; use lowest-cost capable model."

    if task_type in BALANCED_TASK_TYPES and task_type not in LOW_COST_TASK_TYPES:
        route = "balanced"
        reason = "Tool/code work needs reliable reasoning, but not flagship by default."

    if task_type in PREMIUM_TASK_TYPES or risk == "high" or complexity == "high":
        route = "premium"
        reason = "High complexity/risk/value requires stronger reasoning and review quality."

    if budget_mode == "economy" and route == "balanced" and risk == "low":
        route = "cheap"
        reason = "Economy budget mode allows cheaper route for low-risk work."

    if budget_mode == "quality" and route == "balanced" and complexity != "low":
        route = "premium"
        reason = "Quality budget mode escalates non-trivial work to premium."

    if (
        local_gpu_ready
        and bool(local_gpu_policy.get("route_allowed"))
        and privacy in {"private", "sensitive"}
        and risk != "high"
    ):
        fallback_reason = _local_runtime_fallback_reason(
            local_route_status=local_route_status,
            local_latency_ms=normalized_latency_ms,
            max_latency_ms=int(runtime_policy["max_latency_ms"]),
        )
        if not fallback_reason:
            return _build_local_gpu_route(
                local_gpu_policy,
                local_route_status=local_route_status,
                local_latency_ms=normalized_latency_ms,
                max_latency_ms=int(runtime_policy["max_latency_ms"]),
            )
        fallback_output = _build_route(policy, route, reason, approval_required=route == "premium" and task_type in {"security_review", "high_value_decision", "sensitive_decision"})
        return _apply_api_fallback(
            fallback_output,
            fallback_reason=fallback_reason,
            local_gpu_policy=local_gpu_policy,
            local_route_status=local_route_status,
            local_latency_ms=normalized_latency_ms,
            max_latency_ms=int(runtime_policy["max_latency_ms"]),
        )

    local_gpu_skip_reason = None
    if local_gpu_ready:
        if not bool(local_gpu_policy.get("route_allowed")):
            local_gpu_skip_reason = "Local GPU was requested but did not pass the validation gate."
        elif privacy not in {"private", "sensitive"}:
            local_gpu_skip_reason = "Task privacy does not require local GPU; API route selected for speed and quality."
        elif risk == "high":
            local_gpu_skip_reason = "High-risk task is kept on the stronger reviewed API route instead of local GPU."

    return _build_cloud_route(
        policy,
        route,
        reason,
        approval_required=route == "premium" and task_type in {"security_review", "high_value_decision", "sensitive_decision"},
        local_gpu_policy=local_gpu_policy,
        local_gpu_requested=local_gpu_ready,
        local_gpu_skip_reason=local_gpu_skip_reason,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Choose a Leon model route for an agent task.")
    parser.add_argument("--task-type", default="general")
    parser.add_argument("--complexity", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--risk", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--budget-mode", choices=["economy", "balanced", "quality"], default="balanced")
    parser.add_argument("--privacy", choices=["normal", "private", "sensitive"], default="normal")
    parser.add_argument("--local-gpu-ready", action="store_true")
    parser.add_argument("--local-route-status", default="")
    parser.add_argument("--local-latency-ms", default=None)
    args = parser.parse_args(argv)

    print(json.dumps(choose_route(**vars(args)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
