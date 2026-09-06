from __future__ import annotations

import json
from typing import Any

from leon_control_plane.tool_registry import normalize_tool_manifest, score_tool_candidate


HIGH_IMPACT_ACTIONS = {"write", "install", "connect", "resource_heavy", "spend_money"}


def _json_manifest(item: dict[str, Any]) -> dict[str, Any]:
    if "manifest_json" in item:
        return json.loads(item.get("manifest_json") or "{}")
    return dict(item)


def adoption_lane(manifest: dict[str, Any], score: dict[str, Any]) -> str:
    if score.get("blockers"):
        return "reject"
    if manifest["status"] == "rejected":
        return "reject"
    if manifest["risk_level"] in {"critical"}:
        return "reject"
    if manifest["risk_level"] == "high" or manifest["resource_profile"] in {"gpu_heavy", "heavy"}:
        return "hold"
    if manifest["write_scopes"] or manifest["external_effects"]:
        return "sandbox_later"
    if int(score.get("score") or 0) >= 85 and score.get("evidence_level") == "github_metadata":
        return "evaluate_now"
    if int(score.get("score") or 0) >= 75 and score.get("evidence_level") == "github_metadata":
        return "sandbox_later"
    return "hold"


def adoption_gates(manifest: dict[str, Any]) -> list[str]:
    gates = ["no_auto_install", "no_auto_status_promotion", "review_required_before_enable"]
    if manifest.get("required_env_keys"):
        gates.append("secret_scope_review")
    for action in manifest.get("approval_required_for", []):
        if action in HIGH_IMPACT_ACTIONS:
            gates.append(f"approval_required:{action}")
    if manifest.get("write_scopes"):
        gates.append("write_scopes_disabled_until_consumed_approval")
    if manifest.get("external_effects"):
        gates.append("external_effects_require_runtime_permission_check")
    if manifest.get("sandbox_required", True):
        gates.append("sandbox_required")
    return sorted(set(gates))


def lane_reason(manifest: dict[str, Any], score: dict[str, Any], lane: str) -> list[str]:
    reasons: list[str] = []
    if score.get("blockers"):
        reasons.append("has_blockers")
    if score.get("evidence_level") != "github_metadata":
        reasons.append("missing_live_github_metadata")
    if manifest.get("write_scopes"):
        reasons.append("has_write_scopes")
    if manifest.get("external_effects"):
        reasons.append("has_external_effects")
    if manifest.get("required_env_keys"):
        reasons.append("requires_secret_scope_review")
    if manifest.get("risk_level") == "high":
        reasons.append("high_risk")
    if manifest.get("resource_profile") in {"gpu_heavy", "heavy"}:
        reasons.append("resource_heavy")
    if lane == "evaluate_now":
        reasons.append("high_score_readonly_candidate")
    if lane == "sandbox_later":
        reasons.append("sandbox_required_before_execution")
    if lane == "hold":
        reasons.append("not_ready_for_evaluation")
    if lane == "reject":
        reasons.append("not_adoptable_without_override")
    return sorted(set(reasons))


def adoption_next_task(manifest: dict[str, Any], lane: str) -> str:
    if lane == "evaluate_now":
        return "Maak een read-only fit/security review: API surface, license, minimal install plan, rollback, en beslissing hergebruik vs custom."
    if lane == "sandbox_later":
        return "Maak eerst een sandboxplan voor tool scopes, testdata, permission checks en rollback; nog niet installeren."
    if lane == "reject":
        return "Zoek alternatief of markeer kandidaat als ongeschikt na review."
    return "Bewaar als kandidaat; wacht op metadata, hardware, security review of productfase voordat sandbox/evaluatie start."


def build_tool_adoption_shortlist(tool_items: list[dict[str, Any]]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for item in tool_items:
        manifest = normalize_tool_manifest(_json_manifest(item))
        if manifest["status"] not in {"candidate", "reviewed", "approved_readonly", "approved_write_gated"}:
            continue
        score = score_tool_candidate(manifest)
        lane = adoption_lane(manifest, score)
        candidates.append(
            {
                "tool_id": manifest["tool_id"],
                "name": manifest["name"],
                "source_type": manifest["source_type"],
                "source_url": manifest["source_url"],
                "status": manifest["status"],
                "risk_level": manifest["risk_level"],
                "resource_profile": manifest["resource_profile"],
                "cost_profile": manifest["cost_profile"],
                "score": score["score"],
                "evidence_level": score["evidence_level"],
                "recommendation": score["recommendation"],
                "lane": lane,
                "lane_reason": lane_reason(manifest, score, lane),
                "gates": adoption_gates(manifest),
                "next_task": adoption_next_task(manifest, lane),
                "blockers": list(score.get("blockers") or []),
                "next_actions": list(score.get("next_actions") or []),
                "github": score.get("github") or {},
                "read_scope_count": len(manifest["read_scopes"]),
                "write_scope_count": len(manifest["write_scopes"]),
                "read_scopes": list(manifest["read_scopes"]),
                "write_scopes": list(manifest["write_scopes"]),
                "required_env_keys": list(manifest["required_env_keys"]),
                "external_effects": list(manifest["external_effects"]),
                "approval_required_for": list(manifest["approval_required_for"]),
                "allowed_without_approval": list(manifest["allowed_without_approval"]),
                "forbidden_actions": list(manifest["forbidden_actions"]),
                "sandbox_required": bool(manifest["sandbox_required"]),
                "no_approval_granted": True,
                "status_unchanged": True,
            }
        )

    lane_order = {
        "evaluate_now": 0,
        "sandbox_later": 1,
        "hold": 2,
        "reject": 3,
    }
    candidates.sort(key=lambda item: (lane_order.get(item["lane"], 9), -int(item["score"]), item["name"]))
    lanes: dict[str, int] = {}
    for item in candidates:
        lanes[item["lane"]] = lanes.get(item["lane"], 0) + 1
    return {
        "generated_from": "tool_manifests",
        "policy": "advisory_only_no_install_no_status_promotion_no_approval_granted",
        "lanes": lanes,
        "items": candidates,
    }
