from __future__ import annotations

from typing import Any

from leon_control_plane.tool_registry import normalize_tool_manifest


DEFAULT_MCP_REVIEW_GATES = [
    "no_auto_install",
    "no_auto_connect",
    "no_auto_status_promotion",
    "review_required_before_enable",
    "write_scopes_disabled_until_consumed_approval",
    "unknown_tools_default_deny",
    "secret_values_never_read",
    "sandbox_required",
]


def build_mcp_candidate_intake(
    *,
    manifest: dict[str, Any],
    tool_mappings: list[dict[str, Any]] | None = None,
    reviewer_note: str = "",
) -> dict[str, Any]:
    """Build a local review checklist for one MCP server candidate.

    The intake records what must be reviewed before a server can be installed
    or connected. It never approves, installs, executes, or changes the
    manifest status.
    """

    normalized = normalize_tool_manifest(manifest)
    if normalized["source_type"] != "mcp_server":
        raise ValueError("MCP candidate intake requires source_type=mcp_server")
    mappings = []
    for item in tool_mappings or []:
        mappings.append(
            {
                "mcp_tool": str(item.get("mcp_tool") or "").strip(),
                "leon_action_type": str(item.get("leon_action_type") or "read").strip(),
                "read_scopes": [str(scope).strip() for scope in item.get("read_scopes", []) if str(scope).strip()],
                "write_scopes": [str(scope).strip() for scope in item.get("write_scopes", []) if str(scope).strip()],
                "env_keys": [str(key).strip() for key in item.get("env_keys", []) if str(key).strip()],
                "external_effect": str(item.get("external_effect") or "none").strip(),
                "approval_required": bool(item.get("approval_required", False) or item.get("write_scopes")),
                "default_decision": "denied_until_reviewed" if not item.get("approved_readonly") else "candidate_readonly_review_needed",
            }
        )

    return {
        "tool_id": normalized["tool_id"],
        "name": normalized["name"],
        "source_url": normalized["source_url"],
        "manifest_status": normalized["status"],
        "review_status": "needs_review",
        "decision": "mcp_server_candidate_intake_only",
        "execution_allowed": False,
        "no_approval_granted": True,
        "status_unchanged": True,
        "install_allowed_now": False,
        "connect_allowed_now": False,
        "write_allowed_now": False,
        "source_pin_required": True,
        "license_review_required": True,
        "security_policy_required": True,
        "sandbox_required": True,
        "required_sections": [
            "identity_and_source_pin",
            "license_review",
            "security_surface_review",
            "tool_schema_mapping",
            "secret_handling",
            "network_allowlist_or_egress_policy",
            "sandbox_plan",
            "approval_gates",
            "rollback_plan",
        ],
        "manifest_snapshot": {
            "tool_id": normalized["tool_id"],
            "source_type": normalized["source_type"],
            "status": normalized["status"],
            "risk_level": normalized["risk_level"],
            "read_scopes": list(normalized["read_scopes"]),
            "write_scopes": list(normalized["write_scopes"]),
            "required_env_keys": list(normalized["required_env_keys"]),
            "external_effects": list(normalized["external_effects"]),
            "approval_required_for": list(normalized["approval_required_for"]),
            "forbidden_actions": list(normalized["forbidden_actions"]),
        },
        "tool_mappings": mappings,
        "default_unknown_tool_decision": "denied",
        "review_gates": sorted(set(DEFAULT_MCP_REVIEW_GATES)),
        "approval_required_for": sorted(set(normalized["approval_required_for"] + ["install", "connect"])),
        "forbidden_without_consumed_approval": [
            "write",
            "install",
            "connect",
            "resource_heavy",
            "spend_money",
            "read_raw_secret",
        ],
        "reviewer_note": reviewer_note,
        "recommended_next_step": "complete_individual_mcp_review_template_before_any_sandbox_or_approval",
    }
