from __future__ import annotations

from typing import Any

from leon_control_plane.agent_run_model import normalize_agent_run_role
from leon_control_plane.model_policy import choose_route
from leon_control_plane.risk_policy import evaluate_action_policy
from leon_control_plane.secret_scanner import redact_value, scan_value
from leon_control_plane.store import ControlPlaneStore


DEFAULT_ALLOWED_ACTIONS = [
    "read_task_context",
    "read_project_docs",
    "produce_plan",
    "produce_reviewable_result",
]

DEFAULT_FORBIDDEN_ACTIONS = [
    "read_raw_secrets",
    "write_env_files",
    "install_dependencies",
    "connect_external_accounts",
    "execute_shell_commands",
    "modify_files",
    "send_external_messages",
    "spend_money",
    "start_gpu_intensive_jobs",
]


def build_task_packet(
    *,
    task: dict[str, Any],
    agent_role: str,
    task_type: str,
    allowed_actions: list[str] | None = None,
    forbidden_actions: list[str] | None = None,
) -> dict[str, Any]:
    packet = {
        "task_id": task["id"],
        "title": task["title"],
        "goal": task["goal"],
        "phase_id": task.get("phase_id"),
        "priority": task["priority"],
        "risk_level": task["risk_level"],
        "status_at_assignment": task["status"],
        "source_refs": list(task.get("source_refs") or []),
        "agent_role": agent_role,
        "role": normalize_agent_run_role(agent_role),
        "task_type": task_type,
        "acceptance_criteria": task.get("acceptance_criteria", ""),
        "allowed_actions": allowed_actions or DEFAULT_ALLOWED_ACTIONS,
        "forbidden_actions": forbidden_actions or DEFAULT_FORBIDDEN_ACTIONS,
        "output_contract": {
            "result_summary": "Short summary of what the agent produced.",
            "evidence": "List of reviewed facts/files/checks; no raw secrets.",
            "open_questions": "Known uncertainties or required human decisions.",
            "review_required": True,
        },
    }
    result = scan_value(packet)
    safe_packet = redact_value(packet)
    safe_packet["secret_scan"] = {
        "scanned": True,
        "redacted_count": result.total,
        "finding_kinds": list(result.kinds),
        "raw_secret_values_allowed": False,
    }
    return safe_packet


class MockAgentRunner:
    """Local-only agent adapter used before real LLM/Codex integration.

    It exercises the task packet, model routing, persistence, and audit path
    without making external API calls, running shell commands, or reading
    secrets.
    """

    def __init__(self, store: ControlPlaneStore):
        self.store = store

    def run(
        self,
        *,
        task_id: str,
        agent_role: str = "Mock Builder Agent",
        task_type: str = "documentation",
        complexity: str = "medium",
        risk: str = "medium",
        privacy: str = "normal",
        budget_mode: str = "balanced",
        local_gpu_ready: bool = False,
        local_route_status: str = "",
        local_latency_ms: float | int | str | None = None,
        allowed_actions: list[str] | None = None,
        forbidden_actions: list[str] | None = None,
    ) -> dict[str, Any]:
        state = self.store.get_state()
        tasks = {task["id"]: task for task in state["tasks"]}
        if task_id not in tasks:
            raise ValueError("Unknown task id")
        task = tasks[task_id]
        model_route = choose_route(
            task_type=task_type,
            complexity=complexity,
            risk=risk,
            privacy=privacy,
            budget_mode=budget_mode,
            local_gpu_ready=local_gpu_ready,
            local_route_status=local_route_status,
            local_latency_ms=local_latency_ms,
        )
        allowed_actions = list(allowed_actions or DEFAULT_ALLOWED_ACTIONS)
        forbidden_actions = list(forbidden_actions or DEFAULT_FORBIDDEN_ACTIONS)
        risk_policy = evaluate_action_policy(
            action_type="local_mock_agent_run",
            requested_scope="local_mock_agent_run",
            metadata={
                "allowed_actions": allowed_actions,
                "forbidden_actions": forbidden_actions,
                "runner_kind": "local_mock",
            },
        )
        if not risk_policy["execution_allowed"]:
            raise ValueError(f"Agent run blocked by risk policy: {risk_policy['reason']}")
        task_packet = build_task_packet(
            task=task,
            agent_role=agent_role,
            task_type=task_type,
            allowed_actions=allowed_actions,
            forbidden_actions=forbidden_actions,
        )
        task_packet["risk_policy"] = risk_policy
        run_id = self.store.create_agent_run(
            task_id=task_id,
            agent_role=agent_role,
            task_type=task_type,
            complexity=complexity,
            risk=risk,
            privacy=privacy,
            budget_mode=budget_mode,
            model_route=model_route,
            task_packet=task_packet,
            allowed_actions=allowed_actions,
            forbidden_actions=forbidden_actions,
        )
        result_summary = (
            f"Mock run prepared a bounded task packet for '{task['title']}' "
            f"using route {model_route['route']} / {model_route['model']}. "
            "No external calls, file writes, shell commands, or secret reads were performed."
        )
        evidence = [
            {
                "type": "task_packet",
                "summary": "Task packet contains scope, allowed actions, forbidden actions, and review contract.",
            },
            {
                "type": "model_route",
                "summary": model_route["reason"],
                "route": model_route["route"],
                "model": model_route["model"],
            },
            {
                "type": "safety",
                "summary": "Runner is local-only and deterministic for adapter validation.",
            },
        ]
        self.store.complete_agent_run(run_id, result_summary=result_summary, evidence=evidence)
        return {
            "id": run_id,
            "task_id": task_id,
            "agent_role": agent_role,
            "model_route": model_route,
            "risk_policy": risk_policy,
            "task_packet": task_packet,
            "result_summary": result_summary,
            "evidence": evidence,
        }
