from __future__ import annotations

import re
from typing import Any

from leon_control_plane.risk_policy import evaluate_action_policy


CONNECTOR_TYPES = {"browser_research", "mail", "calendar", "files", "tasks", "memory", "sources"}
CONNECTOR_STATUSES = {"disabled", "approved_readonly", "approved_write_gated", "rejected"}
CONNECTOR_ACTION_TYPES = {"read", "write", "external_write", "connect", "read_raw_secret"}
RISK_LEVELS = {"low", "medium", "high", "critical"}
ENV_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,80}$")


DEFAULT_CONNECTOR_MANIFESTS: list[dict[str, Any]] = [
    {
        "connector_id": "browser-research",
        "name": "Browser and research",
        "connector_type": "browser_research",
        "status": "approved_readonly",
        "read_scopes": ["web:search", "web:page_read", "web:source_metadata"],
        "write_scopes": ["web:form_submit", "web:account_state_change"],
        "external_system": True,
        "external_effects": ["web_requests", "possible_account_state_change"],
        "required_env_keys": [],
        "rollback_notes": "Stop automation, close the browser session, clear temporary browser state, and manually undo any remote change.",
    },
    {
        "connector_id": "mail",
        "name": "Mail",
        "connector_type": "mail",
        "status": "approved_readonly",
        "read_scopes": ["mail:metadata", "mail:message_read", "mail:thread_read"],
        "write_scopes": ["mail:draft_create", "mail:send", "mail:label_update"],
        "external_system": True,
        "external_effects": ["mailbox_read", "email_send_or_modify"],
        "required_env_keys": ["MAIL_CONNECTOR_TOKEN"],
        "rollback_notes": "Prefer drafts before send; for sent mail, record recipients/message id and prepare a follow-up correction.",
    },
    {
        "connector_id": "calendar",
        "name": "Calendar",
        "connector_type": "calendar",
        "status": "approved_readonly",
        "read_scopes": ["calendar:availability", "calendar:event_read"],
        "write_scopes": ["calendar:event_create", "calendar:event_update", "calendar:event_delete"],
        "external_system": True,
        "external_effects": ["calendar_read", "calendar_event_mutation"],
        "required_env_keys": ["CALENDAR_CONNECTOR_TOKEN"],
        "rollback_notes": "Store event id and before/after fields so the event can be reverted or deleted.",
    },
    {
        "connector_id": "files",
        "name": "Files",
        "connector_type": "files",
        "status": "approved_readonly",
        "read_scopes": ["files:metadata", "files:content_read", "files:project_docs"],
        "write_scopes": ["files:content_write", "files:delete", "files:move"],
        "external_system": False,
        "external_effects": [],
        "required_env_keys": [],
        "rollback_notes": "Local writes require before/after snapshots and delete/scrub support.",
    },
    {
        "connector_id": "tasks",
        "name": "Task manager",
        "connector_type": "tasks",
        "status": "approved_write_gated",
        "read_scopes": ["tasks:metadata", "tasks:item_read", "tasks:audit_read"],
        "write_scopes": ["tasks:item_create", "tasks:item_update", "tasks:item_delete"],
        "external_system": False,
        "external_effects": [],
        "required_env_keys": [],
        "connector_policy_allows_autonomy": True,
        "rollback_notes": "Local task writes are audited and can be changed through normal task transitions.",
    },
    {
        "connector_id": "memory-sources",
        "name": "Memory and source index",
        "connector_type": "memory",
        "status": "approved_write_gated",
        "read_scopes": ["memory:item_read", "memory:graph_read", "sources:index_read"],
        "write_scopes": ["memory:candidate_create", "memory:scrub", "sources:index_create", "sources:index_delete"],
        "external_system": False,
        "external_effects": [],
        "required_env_keys": [],
        "connector_policy_allows_autonomy": True,
        "rollback_notes": "Memory/source writes must keep delete or scrub support and never persist credential-like content.",
    },
]


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        raise ValueError("Expected a list of strings")
    output: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            output.append(text)
    return output


def _dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("Expected an object")
    return dict(value)


def _matches_scope(pattern: str, requested: str) -> bool:
    if pattern == "*" or pattern == requested:
        return True
    if pattern.endswith(":*"):
        return requested.startswith(pattern[:-1])
    return False


def _any_match(patterns: list[str], requested: str) -> bool:
    return any(_matches_scope(pattern, requested) for pattern in patterns)


def normalize_connector_manifest(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Connector manifest must be an object")

    connector_id = str(raw.get("connector_id") or raw.get("id") or "").strip()
    name = str(raw.get("name") or "").strip()
    connector_type = str(raw.get("connector_type") or raw.get("type") or "").strip()
    status = str(raw.get("status") or "disabled").strip()

    if not re.match(r"^[a-z0-9][a-z0-9_.-]{2,96}$", connector_id):
        raise ValueError("connector_id must be lowercase and contain only letters, numbers, dot, dash or underscore")
    if not name:
        raise ValueError("Connector manifest requires name")
    if connector_type not in CONNECTOR_TYPES:
        raise ValueError("Invalid connector_type")
    if status not in CONNECTOR_STATUSES:
        raise ValueError("Invalid connector status")
    external_system = bool(raw.get("external_system", connector_type in {"browser_research", "mail", "calendar"}))
    risk_level = str(raw.get("risk_level") or ("high" if external_system else "medium")).strip()
    if risk_level not in RISK_LEVELS:
        raise ValueError("Invalid risk_level")

    required_env_keys = _list(raw.get("required_env_keys"))
    for key in required_env_keys:
        if not ENV_KEY_RE.match(key):
            raise ValueError(f"Invalid required env key: {key}")

    secret_handling = {
        "raw_secret_values_visible": False,
        "secret_values_allowed_in_ui": False,
        "secret_values_allowed_in_logs": False,
        "secret_values_allowed_in_model_context": False,
    }
    secret_handling.update(_dict(raw.get("secret_handling")))
    for key in [
        "raw_secret_values_visible",
        "secret_values_allowed_in_ui",
        "secret_values_allowed_in_logs",
        "secret_values_allowed_in_model_context",
    ]:
        if bool(secret_handling.get(key)):
            raise ValueError("Connector manifests cannot allow raw connector secret exposure")

    return {
        "connector_id": connector_id,
        "name": name,
        "connector_type": connector_type,
        "status": status,
        "owner": str(raw.get("owner") or "Leon").strip(),
        "purpose": str(raw.get("purpose") or "").strip(),
        "read_scopes": _list(raw.get("read_scopes")),
        "write_scopes": _list(raw.get("write_scopes")),
        "required_env_keys": required_env_keys,
        "external_system": external_system,
        "external_effects": _list(raw.get("external_effects")),
        "approval_required_for": _list(raw.get("approval_required_for") or ["write", "external_write", "connect"]),
        "allowed_without_approval": _list(raw.get("allowed_without_approval") or ["read"]),
        "forbidden_actions": _list(raw.get("forbidden_actions") or ["read_raw_secret", "read_secret_value", "secret_exfiltration"]),
        "connector_policy_allows_autonomy": bool(raw.get("connector_policy_allows_autonomy", False)),
        "risk_level": risk_level,
        "rollback_notes": str(raw.get("rollback_notes") or "").strip(),
        "secret_handling": secret_handling,
        "notes": str(raw.get("notes") or "").strip(),
    }


def _policy_for_connector(
    manifest: dict[str, Any],
    *,
    action_type: str,
    requested_scope: str,
    approval_id: str | None,
    approval_status: str | None,
) -> dict[str, Any]:
    effective_action = "external_write" if action_type in {"write", "external_write"} and manifest["external_system"] else action_type
    metadata = {
        **manifest,
        "source_type": "api_connector" if manifest["external_system"] else "local_tool",
        "connector_policy_allows_autonomy": bool(manifest.get("connector_policy_allows_autonomy")),
    }
    risk_class = "R4" if effective_action == "external_write" else None
    return evaluate_action_policy(
        action_type=effective_action,
        requested_scope=requested_scope,
        risk_class=risk_class,
        approval_id=approval_id,
        approval_status=approval_status,
        metadata=metadata,
    )


def classify_connector_action(
    manifest: dict[str, Any] | None,
    *,
    action_type: str,
    requested_scope: str,
    present_env_keys: set[str] | None = None,
    approval_id: str | None = None,
    approval_status: str | None = None,
) -> dict[str, Any]:
    action_type = str(action_type or "").strip()
    requested_scope = str(requested_scope or "").strip()
    present_env_keys = present_env_keys or set()
    base_manifest = normalize_connector_manifest(manifest) if manifest is not None else None
    policy = _policy_for_connector(
        base_manifest or {
            "external_system": True,
            "external_effects": [],
            "connector_policy_allows_autonomy": False,
        },
        action_type=action_type,
        requested_scope=requested_scope,
        approval_id=approval_id,
        approval_status=approval_status,
    )
    base = {
        "connector_id": (base_manifest or {}).get("connector_id", "unknown"),
        "action_type": action_type,
        "effective_action_type": (
            "external_write"
            if action_type in {"write", "external_write"} and bool((base_manifest or {}).get("external_system", True))
            else action_type
        ),
        "requested_scope": requested_scope,
        "decision": "denied",
        "allowed": False,
        "approval_required": False,
        "required_gate": "",
        "reason": "",
        "risk_level": (base_manifest or {}).get("risk_level", "high"),
        "approval_id": approval_id,
        "approval_status": approval_status,
        "risk_class": policy["risk_class"],
        "policy_decision": policy["decision"],
        "risk_policy": policy,
        "execution_allowed": False,
        "can_run_autonomously": False,
        "connector_executed": False,
        "write_performed": False,
        "raw_secret_values_visible": False,
        "audit_event_type": "connector_permission_denied",
    }

    if base_manifest is None:
        base["reason"] = "Unknown connector: no permission manifest exists."
        return base
    manifest = base_manifest
    base["connector_id"] = manifest["connector_id"]
    base["risk_level"] = manifest["risk_level"]

    if action_type not in CONNECTOR_ACTION_TYPES:
        base["reason"] = "Unknown action_type."
        return base
    if not requested_scope:
        base["reason"] = "requested_scope is required."
        return base

    forbidden = manifest["forbidden_actions"]
    if (
        action_type == "read_raw_secret"
        or _any_match(forbidden, action_type)
        or _any_match(forbidden, requested_scope)
        or "secret_value" in requested_scope
        or "raw_secret" in requested_scope
    ):
        blocked_policy = evaluate_action_policy(
            action_type="read_raw_secret",
            requested_scope=requested_scope,
            metadata={"hard_blocked": True},
        )
        base.update(
            {
                "risk_class": blocked_policy["risk_class"],
                "policy_decision": blocked_policy["decision"],
                "risk_policy": blocked_policy,
                "reason": "Raw connector secrets or explicitly forbidden connector actions are never allowed.",
            }
        )
        return base

    if manifest["status"] == "rejected":
        base["reason"] = "Connector manifest is rejected."
        return base
    if manifest["status"] == "disabled":
        base["reason"] = "Connector is disabled; permission checks are reported without execution."
        return base

    missing = [key for key in manifest["required_env_keys"] if key not in present_env_keys]
    if missing:
        base.update(
            {
                "decision": "waiting_for_secret",
                "required_gate": "secret_intake",
                "reason": f"Missing required env key(s): {', '.join(missing)}.",
                "audit_event_type": "connector_permission_waiting_for_secret",
            }
        )
        return base

    if action_type == "read":
        if manifest["status"] not in {"approved_readonly", "approved_write_gated"}:
            base["reason"] = "Read requires an approved connector manifest."
            return base
        if not _any_match(manifest["read_scopes"], requested_scope):
            base["reason"] = "Requested read scope is not in the connector manifest."
            return base
        base.update(
            {
                "decision": "allowed",
                "allowed": True,
                "execution_allowed": policy["execution_allowed"],
                "can_run_autonomously": policy["can_run_autonomously"],
                "reason": "Approved connector read scope; no write, account mutation or secret exposure.",
                "audit_event_type": "connector_permission_allowed",
            }
        )
        return base

    if action_type in {"write", "external_write", "connect"}:
        base["approval_required"] = bool(policy["approval_required"] or action_type in manifest["approval_required_for"])
        base["required_gate"] = "approval_consumed" if base["approval_required"] else ""
        if manifest["status"] != "approved_write_gated":
            base["reason"] = "Connector write/connect actions require approved_write_gated status."
            return base
        if action_type in {"write", "external_write"} and not _any_match(manifest["write_scopes"], requested_scope):
            base["reason"] = "Requested write scope is not in the connector manifest."
            return base
        if action_type == "connect" and "connect" not in manifest["approval_required_for"]:
            base["reason"] = "Connector manifest does not explicitly allow account connection."
            return base
        if policy["decision"] == "blocked":
            base["decision"] = "blocked"
            base["reason"] = policy["reason"]
            return base
        if policy["decision"] == "needs_review":
            base.update(
                {
                    "decision": "waiting_for_approval",
                    "approval_required": True,
                    "required_gate": "approval_consumed",
                    "reason": policy["reason"],
                    "audit_event_type": "connector_permission_waiting_for_approval",
                }
            )
            return base
        base.update(
            {
                "decision": "allowed",
                "allowed": True,
                "execution_allowed": True,
                "can_run_autonomously": True,
                "reason": "Connector action is within manifest scope and policy allows execution.",
                "audit_event_type": "connector_permission_allowed",
            }
        )
        return base

    base["reason"] = "No connector policy branch allowed this action."
    return base
