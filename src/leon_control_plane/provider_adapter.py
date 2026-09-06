from __future__ import annotations

import json
from typing import Any

from leon_control_plane.agent_runtime import build_task_packet
from leon_control_plane.decision_layer import redact_sensitive_text
from leon_control_plane.model_policy import choose_route


OPENAI_AGENTS_PROVIDER_ID = "openai_agents_sdk_python"
OPENAI_AGENTS_REQUIRED_ENV_KEYS = ["OPENAI_API_KEY"]

FORBIDDEN_PROVIDER_ACTIONS = [
    "read_raw_secrets",
    "write_env_files",
    "install_dependencies",
    "connect_external_accounts",
    "execute_shell_commands",
    "modify_files",
    "send_external_messages",
    "spend_money",
    "start_gpu_intensive_jobs",
    "use_shell_tool",
    "use_apply_patch_tool",
    "use_computer_tool",
    "use_hosted_mcp",
    "use_hosted_web_file_or_code_tools",
]


def _redact_object(value: Any) -> Any:
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, list):
        return [_redact_object(item) for item in value]
    if isinstance(value, tuple):
        return [_redact_object(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _redact_object(item) for key, item in value.items()}
    return value


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        loaded = json.loads(value)
        if isinstance(loaded, dict):
            return loaded
    return {}


def build_openai_agents_sdk_dry_run_plan(
    *,
    task: dict[str, Any],
    assignment_proposal: dict[str, Any] | None = None,
    present_env_keys: set[str] | None = None,
) -> dict[str, Any]:
    """Build a non-executing adapter plan for the OpenAI Agents SDK target.

    The plan is deliberately inert: it imports no SDK, performs no provider call,
    reads no secret values, creates no agent run, and grants no approval. It
    converts the existing local task/assignment context into the shape a later
    adapter would need to implement after explicit sandbox approval.
    """

    present_env_keys = set(present_env_keys or set())
    missing_env_keys = [key for key in OPENAI_AGENTS_REQUIRED_ENV_KEYS if key not in present_env_keys]
    proposal_json = _json_dict((assignment_proposal or {}).get("proposal_json") or assignment_proposal or {})

    if proposal_json:
        task_packet = _json_dict(proposal_json.get("task_packet"))
        model_route = _json_dict(proposal_json.get("model_route"))
        task_type = str(proposal_json.get("task_type") or task_packet.get("task_type") or "tool_making")
        complexity = str(proposal_json.get("complexity") or "medium")
        risk = str(proposal_json.get("risk") or task.get("risk_level") or task.get("risk") or "medium")
        privacy = str(proposal_json.get("privacy") or "normal")
        budget_mode = str(proposal_json.get("budget_mode") or "balanced")
    else:
        safe_task = dict(task)
        safe_task["title"] = redact_sensitive_text(str(safe_task.get("title") or ""))
        safe_task["goal"] = redact_sensitive_text(str(safe_task.get("goal") or ""))
        safe_task["acceptance_criteria"] = redact_sensitive_text(str(safe_task.get("acceptance_criteria") or ""))
        task_type = "tool_making"
        complexity = "medium"
        risk = str(task.get("risk_level") or task.get("risk") or "medium")
        privacy = "normal"
        budget_mode = "balanced"
        model_route = choose_route(task_type=task_type, complexity=complexity, risk=risk, privacy=privacy)
        task_packet = build_task_packet(task=safe_task, agent_role="OpenAI Agents SDK Dry Run", task_type=task_type)

    task_packet = _redact_object(task_packet)
    model_route = _redact_object(model_route)
    status = "dry_run_blocked_missing_required_env" if missing_env_keys else "dry_run_ready_waiting_for_sandbox_approval"

    return {
        "provider_id": OPENAI_AGENTS_PROVIDER_ID,
        "adapter_id": "openai_agents_sdk_dry_run_shell",
        "task_id": str(task.get("id") or ""),
        "assignment_proposal_id": str((assignment_proposal or {}).get("id") or ""),
        "status": status,
        "decision": "plan_only_no_execution",
        "execution_allowed": False,
        "provider_calls_made": False,
        "dependency_installed": False,
        "sdk_imported": False,
        "secret_values_read": False,
        "approval_consumed": False,
        "shell_commands_allowed": False,
        "file_writes_allowed": False,
        "required_env_keys": list(OPENAI_AGENTS_REQUIRED_ENV_KEYS),
        "env_key_presence": {key: key in present_env_keys for key in OPENAI_AGENTS_REQUIRED_ENV_KEYS},
        "missing_env_keys": missing_env_keys,
        "required_before_execution": [
            "explicit_user_approval_for_sandbox_install_and_provider_call",
            "OPENAI_API_KEY_present_as_named_env_key",
            "provider_adapter_implemented_behind_agent_assignment_proposals",
            "permission_preflight_for_every_function_tool",
            "trace_and_audit_redaction_verified",
        ],
        "blocked_tool_surfaces": [
            "ShellTool",
            "ApplyPatchTool",
            "ComputerTool",
            "hosted_MCP",
            "hosted_web_file_or_code_tools",
            "browser_automation",
            "external_writes",
        ],
        "allowed_later_sandbox_steps_after_approval": [
            "create_disposable_sandbox_environment",
            "run_text_only_agent_with_low_risk_test_prompt",
            "run_one_custom_function_tool_demo_after_leon_permission_preflight",
            "record_provider_call_started_and_completed_or_failed_audit_events",
            "rollback_to_local_mock",
        ],
        "forbidden_actions": sorted(set(FORBIDDEN_PROVIDER_ACTIONS)),
        "task_packet": task_packet,
        "model_route": model_route,
        "dry_run_contract": {
            "creates_agent_run": False,
            "starts_real_provider_runtime": False,
            "reads_env_values": False,
            "installs_dependencies": False,
            "changes_provider_config": False,
            "promotes_runtime": False,
            "consumes_approval": False,
        },
        "review_required": True,
        "recommended_next_step": "review_dry_run_plan_then_request_explicit_sandbox_approval_if_needed",
    }
