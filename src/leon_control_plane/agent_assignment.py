from __future__ import annotations

from typing import Any

from leon_control_plane.agent_runtime import DEFAULT_ALLOWED_ACTIONS, DEFAULT_FORBIDDEN_ACTIONS, build_task_packet
from leon_control_plane.model_policy import choose_route
from leon_control_plane.local_model import DEFAULT_MODEL
from leon_control_plane.risk_policy import evaluate_action_policy


def infer_task_type(task: dict[str, Any], requested_task_type: str | None = None) -> str:
    if requested_task_type:
        return requested_task_type
    haystack = " ".join(
        str(task.get(key) or "")
        for key in ("title", "goal", "owner", "acceptance_criteria", "acceptance")
    ).lower()
    if any(item in haystack for item in (
        "rabobank", "paypal", "transactie", "saldo", "uitgaven", "investering",
        "investeren", "investment", "beleggen", "crypto", "marktanalyse",
    )):
        return "financial_analysis"
    if any(item in haystack for item in (
        "server manager", "container", "docker", "podman", "ssh", "server update",
        "server error", "server log",
    )):
        return "server_operations"
    if any(item in haystack for item in ("3d model", "3d reference", "image-to-3d", "foto naar 3d", "mesh")):
        return "model_reference"
    if any(item in haystack for item in ("3d printer", "fluidd", "moonraker", "klipper", "print camera", "g-code")):
        return "printer_monitoring"
    if any(item in haystack for item in (
        "marktplaats", "vinted", "ticketswap", "shopper", "koop", "kopen",
        "aanbieding", "deal", "prijsvergelijk", "product zoeken",
    )):
        return "shopping_research"
    if any(item in haystack for item in ("research", "onderzoek", "bronnen", "vergelijk")):
        return "routine_research"
    if any(item in haystack for item in ("debug", "fix", "test", "api", "tool", "script", "code", "bouw")):
        return "tool_making"
    if any(item in haystack for item in ("architecture", "architectuur", "security", "approval", "policy", "gpu")):
        return "architecture"
    return "documentation"


def infer_complexity(task: dict[str, Any], task_type: str, requested_complexity: str | None = None) -> str:
    if requested_complexity:
        return requested_complexity
    if str(task.get("risk_level") or task.get("risk") or "") == "high":
        return "high"
    if str(task.get("priority") or "") == "P0" or task_type in {"tool_making", "architecture"}:
        return "medium"
    return "low"


def build_agent_assignment_proposal(
    *,
    task: dict[str, Any],
    agent_role: str = "Mock Builder Agent",
    runner_kind: str = "local_mock",
    task_type: str | None = None,
    complexity: str | None = None,
    privacy: str = "normal",
    budget_mode: str = "balanced",
    local_gpu_ready: bool = False,
    local_route_status: str = "",
    local_latency_ms: float | int | str | None = None,
    local_model_name: str = DEFAULT_MODEL,
    allowed_actions: list[str] | None = None,
    forbidden_actions: list[str] | None = None,
) -> dict[str, Any]:
    """Build a reviewable assignment proposal for one task.

    This is side-effect free. It prepares either the compatibility mock path or
    a bounded local Ollama text-only run. Neither path receives tools.
    """

    if runner_kind not in {"local_mock", "local_ollama"}:
        raise ValueError("Expected local_mock or local_ollama runner")
    selected_task_type = infer_task_type(task, task_type)
    automatic_roles = {
        "shopping_research": "Shopper",
        "financial_analysis": "Manager",
        "server_operations": "Server Manager",
        "model_reference": "3D Model Reference Maker",
        "printer_monitoring": "3D Printer Manager",
    }
    selected_agent_role = automatic_roles.get(selected_task_type, agent_role) if agent_role == "Mock Builder Agent" else agent_role
    selected_complexity = infer_complexity(task, selected_task_type, complexity)
    risk = str(task.get("risk_level") or task.get("risk") or "medium")
    selected_allowed = list(allowed_actions or DEFAULT_ALLOWED_ACTIONS)
    selected_forbidden = list(forbidden_actions or DEFAULT_FORBIDDEN_ACTIONS)
    for required_forbidden in [
        "read_raw_secrets",
        "write_env_files",
        "install_dependencies",
        "connect_external_accounts",
        "execute_shell_commands",
        "modify_files",
        "send_external_messages",
        "spend_money",
        "start_gpu_intensive_jobs",
    ]:
        if required_forbidden not in selected_forbidden:
            selected_forbidden.append(required_forbidden)

    if runner_kind == "local_ollama":
        privacy = "private"
        local_gpu_ready = True
    model_route = choose_route(
        task_type=selected_task_type,
        complexity=selected_complexity,
        risk=risk,
        privacy=privacy,
        budget_mode=budget_mode,
        local_gpu_ready=local_gpu_ready,
        local_route_status=local_route_status,
        local_latency_ms=local_latency_ms,
    )
    if runner_kind == "local_ollama":
        model_route = {
            **model_route,
            "provider": "ollama",
            "route": "local_gpu",
            "model": local_model_name,
            "reasoning_effort": "local",
            "approval_required": False,
            "selected_runtime": "local_gpu",
        }
    task_packet = build_task_packet(
        task=task,
        agent_role=selected_agent_role,
        task_type=selected_task_type,
        allowed_actions=selected_allowed,
        forbidden_actions=selected_forbidden,
    )
    task_packet["runner_kind"] = runner_kind
    execution_mode = "local_ollama_text_review" if runner_kind == "local_ollama" else "local_mock_review_only"
    task_packet["execution_mode"] = execution_mode
    task_packet["external_calls_allowed"] = False
    task_packet["secret_values_allowed"] = False
    risk_policy = evaluate_action_policy(
        action_type="local_text_agent_run" if runner_kind == "local_ollama" else "local_mock_agent_run",
        requested_scope="local_agent_task",
        metadata={
            "allowed_actions": selected_allowed,
            "forbidden_actions": selected_forbidden,
            "runner_kind": runner_kind,
        },
    )
    if runner_kind == "local_ollama" and str(risk).lower() in {"high", "r4", "r5"}:
        risk_policy = {
            **risk_policy,
            "decision": "blocked",
            "execution_allowed": False,
            "can_run_autonomously": False,
            "approval_required": True,
            "approval_first_required": True,
            "approval_state": "required_before_action",
            "reason": "High-risk tasks cannot use the bounded local Ollama runtime.",
        }
    task_packet["risk_policy"] = risk_policy
    execution_allowed = bool(risk_policy["execution_allowed"])
    local_runner = runner_kind == "local_ollama"
    return {
        "task_id": task["id"],
        "task_title": task["title"],
        "agent_role": selected_agent_role,
        "runner_kind": runner_kind,
        "execution_mode": execution_mode,
        "execution_allowed": execution_allowed,
        "external_calls_made": False,
        "external_calls_allowed": False,
        "secret_values_read": False,
        "shell_commands_allowed": False,
        "file_writes_allowed": False,
        "task_type": selected_task_type,
        "complexity": selected_complexity,
        "risk": risk,
        "privacy": privacy,
        "budget_mode": budget_mode,
        "model_route": model_route,
        "risk_policy": risk_policy,
        "allowed_actions": selected_allowed,
        "forbidden_actions": selected_forbidden,
        "task_packet": task_packet,
        "review_required": True,
        "recommended_next_step": "apply_to_local_ollama_queue" if local_runner else "apply_to_local_mock_agent_run",
        "safety_notes": [
            (
                "This assignment creates a durable local Ollama text-only agent run on the M40."
                if local_runner else "This assignment can only create a local mock agent_run."
            ),
            "No external provider call, tool call, shell command, file write, account connection, or secret read is allowed.",
            "The resulting agent_run still requires reviewer acceptance before task completion.",
        ],
    }
