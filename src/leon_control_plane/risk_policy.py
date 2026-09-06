from __future__ import annotations

from typing import Any


RISK_CLASSES: dict[str, dict[str, Any]] = {
    "R1": {
        "label": "Read-only or local temporary processing",
        "default_decision": "autonomous",
        "examples": [
            "answer a question from already available context",
            "read local status or reviewed source records",
            "build a temporary cache or summary that can be deleted",
        ],
        "rollback": "Temporary cache/delete support required.",
    },
    "R2": {
        "label": "Local persistent change",
        "default_decision": "autonomous",
        "examples": [
            "create a local task",
            "store reviewed memory or source metadata",
            "update local non-secret configuration",
        ],
        "rollback": "Before/after snapshot plus undo/delete/scrub support required.",
    },
    "R3": {
        "label": "Local code or system change",
        "default_decision": "needs_review",
        "examples": [
            "modify project files",
            "run bounded shell commands that change the workspace",
            "apply a code patch with tests",
        ],
        "rollback": "Git diff or patch snapshot plus test result required.",
    },
    "R4": {
        "label": "External write action",
        "default_decision": "needs_review",
        "examples": [
            "send email or mutate calendar events",
            "write to GitHub issues or pull requests",
            "submit a web form or post publicly",
        ],
        "rollback": "Compensating action where possible plus full audit trail.",
    },
    "R5": {
        "label": "Money, accounts, public exposure, secrets, installs",
        "default_decision": "blocked",
        "examples": [
            "spend money, buy tickets, bid or trade crypto",
            "install software, drivers, dependencies or large models",
            "connect accounts, change permissions, expose services publicly or touch raw secrets",
        ],
        "rollback": "Explicit approval required first; rollback plan must be reviewed before execution.",
    },
}

POLICY_DECISIONS = {"autonomous", "needs_review", "blocked"}

R5_ACTIONS = {
    "connect",
    "connect_account",
    "install",
    "install_dependency",
    "install_dependencies",
    "package_install",
    "public_deploy",
    "resource_heavy",
    "spend_money",
    "payment",
    "purchase",
    "read_raw_secret",
    "secret_change",
    "account_permission_change",
}
R4_ACTIONS = {"write", "send_email", "calendar_mutation", "external_write", "post_publicly"}
R3_ACTIONS = {"modify_files", "write_code", "execute_shell_commands", "system_change"}
R2_ACTIONS = {"local_persistent_write", "memory_store", "graph_node_add", "task_create", "config_update"}
R1_ACTIONS = {"local_temp_processing", "summarize", "embedding_generate", "cache_build", "local_mock_agent_run"}
READ_ONLY_ACTIONS = {"read", "web_research", "memory_retrieval", "status_check", "source_review", "direct_answer"}
HARD_BLOCK_ACTIONS = {"read_raw_secret", "secret_exfiltration", "unsafe_abuse", "malware", "phishing", "captcha_bypass"}


def coarse_risk_level(risk_class: str) -> str:
    if risk_class == "R1":
        return "low"
    if risk_class in {"R2", "R3"}:
        return "medium"
    return "high"


def _approval_present(approval_id: str | None, approval_status: str | None, explicit_approval: bool) -> bool:
    return explicit_approval or (bool(approval_id) and approval_status == "consumed")


def _contains_any(text: str, needles: set[str]) -> bool:
    return any(item in text for item in needles)


def infer_risk_class(
    *,
    action_type: str,
    requested_scope: str = "",
    metadata: dict[str, Any] | None = None,
) -> str:
    action = str(action_type or "").strip().lower()
    scope = str(requested_scope or "").strip().lower()
    metadata = metadata or {}
    allowed_actions = {str(item).strip().lower() for item in metadata.get("allowed_actions", [])}
    external_effects = {str(item).strip().lower() for item in metadata.get("external_effects", [])}
    source_type = str(metadata.get("source_type") or "").strip().lower()
    resource_profile = str(metadata.get("resource_profile") or "").strip().lower()
    cost_profile = str(metadata.get("cost_profile") or "").strip().lower()

    if _contains_any(action, HARD_BLOCK_ACTIONS) or "raw_secret" in scope or "secret_value" in scope:
        return "R5"
    if action in R5_ACTIONS or allowed_actions.intersection(R5_ACTIONS):
        return "R5"
    if any(item in scope for item in ("public", "payment", "billing", "account_permission", "secret", "install")):
        return "R5"
    if "gpu" in resource_profile or "heavy" in resource_profile or "billable" in cost_profile:
        return "R5"
    if action in R4_ACTIONS or allowed_actions.intersection(R4_ACTIONS):
        return "R4"
    if external_effects and action not in READ_ONLY_ACTIONS and action != "read":
        return "R4"
    if source_type in {"api_connector", "mcp_server"} and action == "write":
        return "R4"
    if action in R3_ACTIONS or allowed_actions.intersection(R3_ACTIONS):
        return "R3"
    if any(item in scope for item in ("project:file", "repo:write", "system:")):
        return "R3"
    if action in R2_ACTIONS or allowed_actions.intersection(R2_ACTIONS):
        return "R2"
    if any(item in scope for item in ("memory:", "graph:", "task:", "config:")) and action != "read":
        return "R2"
    if action in R1_ACTIONS or allowed_actions.intersection(R1_ACTIONS):
        return "R1"
    if action in READ_ONLY_ACTIONS:
        return "R1"
    return "R3" if action else "R5"


def evaluate_action_policy(
    *,
    action_type: str,
    requested_scope: str = "",
    risk_class: str | None = None,
    approval_id: str | None = None,
    approval_status: str | None = None,
    explicit_approval: bool = False,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = metadata or {}
    selected_risk_class = risk_class or infer_risk_class(
        action_type=action_type,
        requested_scope=requested_scope,
        metadata=metadata,
    )
    if selected_risk_class not in RISK_CLASSES:
        raise ValueError("Unknown risk_class")

    action = str(action_type or "").strip().lower()
    scope = str(requested_scope or "").strip().lower()
    hard_blocked = (
        _contains_any(action, HARD_BLOCK_ACTIONS)
        or "raw_secret" in scope
        or "secret_value" in scope
        or bool(metadata.get("hard_blocked"))
    )
    approval_present = _approval_present(approval_id, approval_status, explicit_approval)
    tests_passed = bool(metadata.get("tests_passed"))
    diff_limited = bool(metadata.get("diff_limited"))

    reason = f"{selected_risk_class} {RISK_CLASSES[selected_risk_class]['label']} policy."
    if hard_blocked:
        decision = "blocked"
        reason = "Action is explicitly forbidden and cannot be approved through the autonomy policy."
    elif selected_risk_class in {"R1", "R2"}:
        decision = "autonomous"
    elif selected_risk_class == "R3":
        decision = "autonomous" if tests_passed and diff_limited else "needs_review"
        if decision == "needs_review":
            reason = "R3 local code/system changes need bounded diff and passing tests before autonomous execution."
    elif selected_risk_class == "R4":
        decision = "autonomous" if approval_present else "needs_review"
        if decision == "needs_review":
            reason = "R4 external writes are approval-first and need consumed approval before execution."
    else:
        decision = "autonomous" if approval_present else "blocked"
        reason = (
            "R5 action has explicit consumed approval."
            if approval_present
            else "R5 actions are approval-first and blocked until explicit approval is present."
        )

    execution_allowed = decision == "autonomous"
    approval_required = selected_risk_class in {"R4", "R5"} and not execution_allowed and not hard_blocked
    if hard_blocked:
        approval_state = "not_approvable"
    elif selected_risk_class not in {"R4", "R5"}:
        approval_state = "not_required"
    elif approval_present:
        approval_state = "approved_consumed"
    else:
        approval_state = "required_before_action"
    return {
        "risk_class": selected_risk_class,
        "risk_label": RISK_CLASSES[selected_risk_class]["label"],
        "examples": RISK_CLASSES[selected_risk_class]["examples"],
        "coarse_risk_level": coarse_risk_level(selected_risk_class),
        "decision": decision,
        "execution_allowed": execution_allowed,
        "can_run_autonomously": execution_allowed,
        "requires_review": decision == "needs_review",
        "approval_required": approval_required,
        "approval_first_required": selected_risk_class in {"R4", "R5"},
        "approval_state": approval_state,
        "explicit_approval_present": approval_present,
        "hard_blocked": hard_blocked,
        "rollback_requirement": RISK_CLASSES[selected_risk_class]["rollback"],
        "audit_required": True,
        "risk_rationale": reason,
        "reason": reason,
    }


def classify_request_policy(*, route: str, matched_signals: set[str], text: str) -> dict[str, Any]:
    lowered = text.lower()
    metadata: dict[str, Any] = {}
    if "refuse_unsafe" in matched_signals:
        return evaluate_action_policy(action_type="unsafe_abuse", metadata={"hard_blocked": True})
    if "money_or_purchase" in matched_signals:
        return evaluate_action_policy(action_type="spend_money")
    if "install_or_infra" in matched_signals:
        return evaluate_action_policy(action_type="install")
    if any(item in lowered for item in ("api key", "secret", "password", "wachtwoord")):
        return evaluate_action_policy(action_type="secret_change")
    if "external_write" in matched_signals:
        return evaluate_action_policy(action_type="external_write")
    if route == "task_queue":
        return evaluate_action_policy(action_type="task_create", requested_scope="task:queue")
    if route == "memory_retrieval":
        return evaluate_action_policy(action_type="memory_retrieval")
    if route == "research_agent":
        return evaluate_action_policy(action_type="web_research")
    if route == "quick_tool_use":
        return evaluate_action_policy(action_type="status_check")
    if "coding" in matched_signals:
        metadata = {"tests_passed": False, "diff_limited": False}
        return evaluate_action_policy(action_type="write_code", metadata=metadata)
    return evaluate_action_policy(action_type="direct_answer")
