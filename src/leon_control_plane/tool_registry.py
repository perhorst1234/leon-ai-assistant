from __future__ import annotations

import re
from typing import Any

from leon_control_plane.risk_policy import evaluate_action_policy


SOURCE_TYPES = {"mcp_server", "local_tool", "api_connector", "script", "github_repository"}
MANIFEST_STATUSES = {"candidate", "reviewed", "approved_readonly", "approved_write_gated", "rejected"}
RISK_LEVELS = {"low", "medium", "high", "critical"}
ACTION_TYPES = {"read", "write", "install", "connect", "resource_heavy", "spend_money", "read_raw_secret"}
ENV_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,80}$")


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


def _bool(value: Any) -> bool:
    return bool(value)


def _dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("Expected an object")
    return dict(value)


def _score(value: Any, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(0, min(5, number))


def _matches_scope(pattern: str, requested: str) -> bool:
    if pattern == "*" or pattern == requested:
        return True
    if pattern.endswith(":*"):
        return requested.startswith(pattern[:-1])
    return False


def _any_match(patterns: list[str], requested: str) -> bool:
    return any(_matches_scope(pattern, requested) for pattern in patterns)


def normalize_tool_manifest(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Tool manifest must be an object")

    tool_id = str(raw.get("tool_id") or raw.get("id") or "").strip()
    name = str(raw.get("name") or "").strip()
    source_type = str(raw.get("source_type") or "").strip()
    status = str(raw.get("status") or "candidate").strip()
    risk_level = str(raw.get("risk_level") or "medium").strip()

    if not re.match(r"^[a-z0-9][a-z0-9_.-]{2,96}$", tool_id):
        raise ValueError("tool_id must be lowercase and contain only letters, numbers, dot, dash or underscore")
    if not name:
        raise ValueError("Tool manifest requires name")
    if source_type not in SOURCE_TYPES:
        raise ValueError("Invalid source_type")
    if status not in MANIFEST_STATUSES:
        raise ValueError("Invalid tool status")
    if risk_level not in RISK_LEVELS:
        raise ValueError("Invalid risk_level")

    required_env_keys = _list(raw.get("required_env_keys"))
    for key in required_env_keys:
        if not ENV_KEY_RE.match(key):
            raise ValueError(f"Invalid required env key: {key}")

    manifest = {
        "tool_id": tool_id,
        "name": name,
        "source_type": source_type,
        "source_url": str(raw.get("source_url") or "").strip(),
        "purpose": str(raw.get("purpose") or "").strip(),
        "owner": str(raw.get("owner") or "Leon").strip(),
        "risk_level": risk_level,
        "status": status,
        "read_scopes": _list(raw.get("read_scopes")),
        "write_scopes": _list(raw.get("write_scopes")),
        "required_env_keys": required_env_keys,
        "cost_profile": str(raw.get("cost_profile") or "unknown").strip(),
        "resource_profile": str(raw.get("resource_profile") or "low").strip(),
        "external_effects": _list(raw.get("external_effects")),
        "approval_required_for": _list(
            raw.get("approval_required_for")
            or ["write", "install", "connect", "resource_heavy", "spend_money"]
        ),
        "allowed_without_approval": _list(raw.get("allowed_without_approval") or ["read"]),
        "forbidden_actions": _list(raw.get("forbidden_actions") or ["read_raw_secret"]),
        "audit_events": _list(raw.get("audit_events") or ["tool_permission_checked"]),
        "rollback_notes": str(raw.get("rollback_notes") or "No execution is performed by registry checks.").strip(),
        "maintenance_status": str(raw.get("maintenance_status") or "unverified").strip(),
        "sandbox_required": _bool(raw.get("sandbox_required", True)),
        "evaluation": _dict(raw.get("evaluation")),
        "github_metadata": _dict(raw.get("github_metadata")),
        "notes": str(raw.get("notes") or "").strip(),
    }
    return manifest


def score_tool_candidate(raw_manifest: dict[str, Any]) -> dict[str, Any]:
    manifest = normalize_tool_manifest(raw_manifest)
    evaluation = manifest.get("evaluation") or {}
    risk_penalty = {"low": 0, "medium": 1, "high": 2, "critical": 4}[manifest["risk_level"]]
    has_write = bool(manifest["write_scopes"])
    has_external = bool(manifest["external_effects"])
    has_env = bool(manifest["required_env_keys"])
    resource_profile = manifest["resource_profile"].lower()
    cost_profile = manifest["cost_profile"].lower()
    source_type = manifest["source_type"]
    github_metadata = manifest.get("github_metadata") or {}
    has_github_metadata = bool(github_metadata)
    github_archived = bool(github_metadata.get("archived") or github_metadata.get("disabled"))
    pushed_days_ago = github_metadata.get("pushed_days_ago")

    product_fit = _score(evaluation.get("product_fit"), 4 if len(manifest["purpose"]) >= 30 else 2)
    reuse_leverage = _score(
        evaluation.get("reuse_leverage"),
        5 if source_type in {"mcp_server", "github_repository"} else 3,
    )
    permission_safety = _score(
        evaluation.get("permission_safety"),
        5 - risk_penalty - int(has_write) - int(has_external) - int(has_env and manifest["risk_level"] in {"high", "critical"}),
    )
    maintenance_confidence = _score(
        evaluation.get("maintenance_confidence"),
        0
        if github_archived
        else 5
        if isinstance(pushed_days_ago, int) and pushed_days_ago <= 90
        else 4
        if isinstance(pushed_days_ago, int) and pushed_days_ago <= 365
        else 2
        if isinstance(pushed_days_ago, int) and pushed_days_ago <= 1095
        else 1
        if has_github_metadata
        else
        1
        if "archived" in manifest["maintenance_status"].lower()
        else 2
        if manifest["maintenance_status"] in {"unverified", "candidate_from_product_plan"}
        else 3,
    )
    cost_efficiency = _score(
        evaluation.get("cost_efficiency"),
        5
        if any(token in cost_profile for token in ("none", "no direct", "no cost"))
        else 4
        if "quota" in cost_profile
        else 2
        if any(token in cost_profile for token in ("hosted", "significant", "electricity", "cost"))
        else 3,
    )
    resource_fit = _score(
        evaluation.get("resource_fit"),
        5
        if resource_profile in {"low", "none"}
        else 3
        if resource_profile == "medium"
        else 2
        if "gpu" in resource_profile or "heavy" in resource_profile
        else 3,
    )
    integration_complexity = _score(
        evaluation.get("integration_complexity"),
        5 - int(source_type == "mcp_server") - int(has_env) - int(has_write) - int(resource_profile != "low"),
    )
    replaceability = _score(evaluation.get("replaceability"), 4 if source_type == "github_repository" else 3)
    adoption_signal = _score(
        evaluation.get("adoption_signal"),
        5
        if int(github_metadata.get("stargazers_count") or 0) >= 10000
        else 4
        if int(github_metadata.get("stargazers_count") or 0) >= 1000
        else 3
        if int(github_metadata.get("stargazers_count") or 0) >= 100
        else 2
        if has_github_metadata
        else 2,
    )

    weights = {
        "product_fit": 20,
        "reuse_leverage": 15,
        "permission_safety": 20,
        "maintenance_confidence": 15,
        "cost_efficiency": 10,
        "resource_fit": 10,
        "integration_complexity": 5,
        "replaceability": 3,
        "adoption_signal": 2,
    }
    criteria = {
        "product_fit": product_fit,
        "reuse_leverage": reuse_leverage,
        "permission_safety": permission_safety,
        "maintenance_confidence": maintenance_confidence,
        "cost_efficiency": cost_efficiency,
        "resource_fit": resource_fit,
        "integration_complexity": integration_complexity,
        "replaceability": replaceability,
        "adoption_signal": adoption_signal,
    }
    total = sum(criteria[key] * weight for key, weight in weights.items())
    max_total = sum(weights.values()) * 5
    score = round((total / max_total) * 100)

    blockers: list[str] = []
    if manifest["status"] == "rejected":
        blockers.append("manifest_rejected")
    if manifest["risk_level"] == "critical":
        blockers.append("critical_risk")
    if "read_raw_secret" not in manifest["forbidden_actions"]:
        blockers.append("raw_secret_forbidden_action_missing")
    if any(action in manifest["approval_required_for"] for action in ("install", "connect", "write", "resource_heavy", "spend_money")) is False:
        blockers.append("approval_gates_missing")
    if "archived" in manifest["maintenance_status"].lower():
        blockers.append("archived_or_unmaintained")
    if github_archived:
        blockers.append("github_archived_or_disabled")
    if isinstance(pushed_days_ago, int) and pushed_days_ago > 1095:
        blockers.append("github_stale_over_3_years")

    if blockers:
        recommendation = "deprioritize_or_reject"
    elif score >= 78 and manifest["risk_level"] in {"low", "medium"} and not has_write:
        recommendation = "evaluate_for_readonly_review"
    elif score >= 68 and manifest["risk_level"] in {"low", "medium"}:
        recommendation = "sandbox_review"
    elif score >= 55:
        recommendation = "keep_candidate_research"
    else:
        recommendation = "deprioritize_or_replace"

    next_actions = [] if has_github_metadata else ["verify_current_repo_status"]
    if has_github_metadata:
        next_actions.append("review_license_and_security_notes")
    if manifest["required_env_keys"]:
        next_actions.append("confirm_required_env_scopes")
    if manifest["source_type"] == "mcp_server":
        next_actions.append("map_mcp_tools_to_individual_scopes")
    if has_write or manifest["risk_level"] in {"high", "critical"}:
        next_actions.append("security_review_before_enable")
    if any(action in manifest["approval_required_for"] for action in ("install", "connect", "resource_heavy", "spend_money")):
        next_actions.append("approval_required_before_execution")

    return {
        "tool_id": manifest["tool_id"],
        "score": score,
        "criteria": criteria,
        "weights": weights,
        "recommendation": recommendation,
        "blockers": blockers,
        "next_actions": next_actions,
        "evidence_level": "github_metadata" if has_github_metadata else "manifest_only",
        "github": {
            "full_name": github_metadata.get("full_name", ""),
            "stars": github_metadata.get("stargazers_count", 0),
            "forks": github_metadata.get("forks_count", 0),
            "pushed_days_ago": pushed_days_ago,
            "archived": bool(github_metadata.get("archived", False)),
            "license": (github_metadata.get("license") or {}).get("spdx_id", ""),
            "fetched_at": github_metadata.get("fetched_at", ""),
        },
        "reason": (
            "Score uses public GitHub repository metadata plus local manifest fields."
            if has_github_metadata
            else "Score is based on local manifest fields only. It is a triage signal, not proof that the repository is current, safe or suitable."
        ),
    }


def _has_required_env(manifest: dict[str, Any], present_env_keys: set[str]) -> bool:
    return all(key in present_env_keys for key in manifest.get("required_env_keys", []))


def classify_tool_action(
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
    policy = evaluate_action_policy(
        action_type=action_type,
        requested_scope=requested_scope,
        approval_id=approval_id,
        approval_status=approval_status,
        metadata=dict(manifest or {}),
    )

    base = {
        "tool_id": (manifest or {}).get("tool_id", "unknown"),
        "action_type": action_type,
        "requested_scope": requested_scope,
        "decision": "denied",
        "allowed": False,
        "approval_required": False,
        "required_gate": "",
        "reason": "",
        "risk_level": (manifest or {}).get("risk_level", "high"),
        "approval_id": approval_id,
        "approval_status": approval_status,
        "risk_class": policy["risk_class"],
        "policy_decision": policy["decision"],
        "risk_policy": policy,
        "execution_allowed": policy["execution_allowed"],
        "can_run_autonomously": policy["can_run_autonomously"],
        "audit_event_type": "tool_permission_denied",
    }

    if manifest is None:
        base["reason"] = "Unknown tool: no reviewed manifest exists."
        return base
    manifest = normalize_tool_manifest(manifest)
    policy = evaluate_action_policy(
        action_type=action_type,
        requested_scope=requested_scope,
        approval_id=approval_id,
        approval_status=approval_status,
        metadata=manifest,
    )
    base["tool_id"] = manifest["tool_id"]
    base["risk_level"] = manifest["risk_level"]
    base["risk_class"] = policy["risk_class"]
    base["policy_decision"] = policy["decision"]
    base["risk_policy"] = policy
    base["execution_allowed"] = policy["execution_allowed"]
    base["can_run_autonomously"] = policy["can_run_autonomously"]

    if action_type not in ACTION_TYPES:
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
        base["reason"] = "Raw secrets or explicitly forbidden actions are never allowed through tools."
        base["policy_decision"] = "blocked"
        base["risk_policy"] = evaluate_action_policy(
            action_type="read_raw_secret",
            requested_scope=requested_scope,
            metadata={"hard_blocked": True},
        )
        return base

    if manifest["status"] in {"candidate", "reviewed"}:
        base["reason"] = f"Tool status is {manifest['status']}; execution requires approved_readonly or approved_write_gated."
        return base
    if manifest["status"] == "rejected":
        base["reason"] = "Tool manifest is rejected."
        return base

    if not _has_required_env(manifest, present_env_keys):
        missing = [key for key in manifest["required_env_keys"] if key not in present_env_keys]
        base["decision"] = "waiting_for_secret"
        base["required_gate"] = "secret_intake"
        base["reason"] = f"Missing required env key(s): {', '.join(missing)}."
        base["audit_event_type"] = "tool_permission_waiting_for_secret"
        return base

    if action_type == "read":
        if policy["decision"] != "autonomous":
            base["decision"] = "waiting_for_approval" if policy["decision"] == "needs_review" else "denied"
            base["approval_required"] = bool(policy["approval_required"])
            base["required_gate"] = "approval_consumed" if policy["approval_required"] else ""
            base["reason"] = policy["reason"]
            base["audit_event_type"] = (
                "tool_permission_waiting_for_approval"
                if policy["decision"] == "needs_review"
                else "tool_permission_denied"
            )
            return base
        if manifest["status"] not in {"approved_readonly", "approved_write_gated"}:
            base["reason"] = "Read requires an approved manifest."
            return base
        if not _any_match(manifest["read_scopes"], requested_scope):
            base["reason"] = "Requested read scope is not in the manifest."
            return base
        if not (_any_match(manifest["allowed_without_approval"], "read") or _any_match(manifest["allowed_without_approval"], f"read:{requested_scope}")):
            base["decision"] = "waiting_for_approval"
            base["approval_required"] = True
            base["required_gate"] = "approval_consumed"
            base["reason"] = "This read scope is not allowed without approval."
            base["audit_event_type"] = "tool_permission_waiting_for_approval"
            return base
        base.update(
            {
                "decision": "allowed",
                "allowed": True,
                "reason": "Approved read-only scope; no external write, spend, install, account connection or secret exposure.",
                "audit_event_type": "tool_permission_allowed",
            }
        )
        return base

    if action_type in {"write", "install", "connect", "resource_heavy", "spend_money"}:
        base["approval_required"] = True
        base["required_gate"] = "approval_consumed"
        if policy["decision"] == "blocked":
            base["decision"] = "blocked"
            base["reason"] = policy["reason"]
            base["audit_event_type"] = "tool_permission_denied"
            return base
        if action_type == "write" and not _any_match(manifest["write_scopes"], requested_scope):
            base["reason"] = "Requested write scope is not in the manifest."
            return base
        if action_type in {"install", "connect", "resource_heavy", "spend_money"}:
            required = set(manifest["approval_required_for"])
            if action_type not in required:
                base["reason"] = "Manifest does not explicitly allow this high-impact action."
                return base
        if approval_status != "consumed" or not approval_id:
            base["decision"] = "waiting_for_approval"
            base["reason"] = "External write/install/connect/cost/resource-heavy actions require a consumed approval id."
            base["audit_event_type"] = "tool_permission_waiting_for_approval"
            return base
        base.update(
            {
                "decision": "allowed",
                "allowed": True,
                "execution_allowed": True,
                "can_run_autonomously": True,
                "reason": "High-impact action is within manifest scope and has a consumed approval id.",
                "audit_event_type": "tool_permission_allowed",
            }
        )
        return base

    base["reason"] = "No policy branch allowed this action."
    return base
