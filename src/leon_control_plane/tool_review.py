from __future__ import annotations

from typing import Any


def _license_status(spdx_id: str) -> str:
    if not spdx_id:
        return "unknown_requires_review"
    if spdx_id in {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC"}:
        return "permissive_review_still_required"
    return "manual_license_review_required"


def build_tool_review_packet(shortlist_item: dict[str, Any]) -> dict[str, Any]:
    github = shortlist_item.get("github") or {}
    tool_id = str(shortlist_item.get("tool_id") or "")
    name = str(shortlist_item.get("name") or tool_id)
    license_id = str(github.get("license") or "")
    has_high_impact_gates = any(
        str(gate).startswith("approval_required:")
        for gate in shortlist_item.get("gates", [])
    )
    return {
        "packet_id": f"review-packet-{tool_id}",
        "tool_id": tool_id,
        "name": name,
        "lane": shortlist_item.get("lane"),
        "source_url": shortlist_item.get("source_url"),
        "review_status": "needs_review",
        "execution_allowed": False,
        "no_approval_granted": True,
        "status_unchanged": True,
        "scope": "read_only_fit_security_license_review",
        "summary": f"Review {name} for reuse before any install, connection, approval or runtime enablement.",
        "evidence": {
            "score": shortlist_item.get("score"),
            "evidence_level": shortlist_item.get("evidence_level"),
            "github": {
                "stars": github.get("stars", 0),
                "forks": github.get("forks", 0),
                "pushed_days_ago": github.get("pushed_days_ago"),
                "archived": bool(github.get("archived", False)),
                "license": license_id,
                "fetched_at": github.get("fetched_at", ""),
            },
        },
        "required_checks": [
            "product_fit_against_leon_plan",
            "license_review",
            "maintenance_review",
            "security_surface_review",
            "permission_scope_mapping",
            "minimal_sandbox_plan",
            "rollback_plan",
            "custom_vs_reuse_decision",
        ],
        "license_status": _license_status(license_id),
        "permission_review": {
            "read_scopes": shortlist_item.get("read_scopes", []),
            "write_scopes": shortlist_item.get("write_scopes", []),
            "required_env_keys": shortlist_item.get("required_env_keys", []),
            "approval_required_for": shortlist_item.get("approval_required_for", []),
            "allowed_without_approval": shortlist_item.get("allowed_without_approval", []),
            "forbidden_actions": shortlist_item.get("forbidden_actions", []),
            "gates": shortlist_item.get("gates", []),
        },
        "install_plan_preview": {
            "install_allowed_now": False,
            "connect_allowed_now": False,
            "write_allowed_now": False,
            "resource_heavy_allowed_now": False,
            "required_before_install": [
                "review_packet_accepted",
                "sandbox_plan_accepted",
                "explicit_user_approval_for_install_or_connect",
            ],
        },
        "risk_notes": [
            "GitHub popularity and recent pushes are not security proof.",
            "Review packet is not an approval and does not change manifest status.",
            "Any install/connect/write/resource-heavy step remains behind explicit approval.",
        ]
        + (["High-impact gates are present; manual review required before any enablement."] if has_high_impact_gates else []),
        "decision_options": [
            "reuse_readonly_after_review",
            "sandbox_before_decision",
            "hold_for_later_phase",
            "replace_with_custom_or_alternative",
        ],
        "recommended_task_title": f"Review reuse candidate: {name}",
        "recommended_task_goal": (
            f"Review {name} for fit, license, security, scopes, sandbox plan and reuse-vs-custom decision. "
            "Do not install, connect accounts, write externally, spend money, or promote status."
        ),
        "acceptance_criteria": (
            "Review documents fit, license, maintenance, security surface, exact scopes, sandbox plan, rollback and reuse-vs-custom decision; "
            "no install/connect/write/approval/status promotion performed."
        ),
    }


def build_review_packets(shortlist: dict[str, Any], *, lane: str = "evaluate_now") -> dict[str, Any]:
    items = [item for item in shortlist.get("items", []) if item.get("lane") == lane]
    return {
        "policy": "review_only_no_execution_no_approval_no_status_change",
        "lane": lane,
        "packets": [build_tool_review_packet(item) for item in items],
    }
