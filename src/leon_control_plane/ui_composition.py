from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
UI_POLICY_PATH = REPO_ROOT / "config" / "ui-composition.json"
CORE_CANVAS_SPACES = ["home", "chat", "workflows", "memory", "skills", "projects", "settings"]
SPACE_LABELS = {
    "home": "Home",
    "chat": "Chat",
    "workflows": "Tasks",
    "memory": "Memory",
    "skills": "Skills",
    "projects": "Projects",
    "settings": "Settings",
}
SPACE_ALIASES = {
    "workflow": "workflows",
    "tools": "skills",
    "research": "projects",
}
FAILED_STATUSES = {"failed", "error", "danger", "policy_violation"}
RUNNING_STATUSES = {"running", "active", "executing", "in_progress"}
REVIEW_STATUSES = {"review", "waiting_for_review", "review_ready"}
BLOCKED_STATUSES = {"blocked", "waiting_for_user", "waiting_for_approval", "waiting_for_secret"}
SLEEPING_STATUSES = {"sleeping", "asleep", "dormant", "inactive"}


def load_ui_policy(path: Path = UI_POLICY_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            output.append(item)
    return output


def _normalize_space(space: str) -> str:
    value = str(space or "home").strip()
    return SPACE_ALIASES.get(value, value)


def _component_allowed_in_space(component: dict[str, Any], space: str) -> bool:
    allowed_spaces = {_normalize_space(item) for item in component.get("allowed_spaces") or []}
    return bool(component.get("registered")) and space in allowed_spaces


def _first_matching(items: list[dict[str, Any]], statuses: set[str]) -> dict[str, Any] | None:
    for item in items:
        if str(item.get("status") or "").strip().lower() in statuses:
            return item
    return None


def _character_state_def(policy: dict[str, Any], state_id: str) -> dict[str, Any]:
    states = (policy.get("character_renderer") or {}).get("states") or {}
    return dict(states.get(state_id) or states.get("idle") or {})


def _status_color(policy: dict[str, Any], status_color_key: str) -> str:
    colors = ((policy.get("product_shell") or {}).get("status_colors") or {})
    fallback = ((policy.get("product_shell") or {}).get("dynamic_accent") or {}).get("fallback", "#62a8ff")
    return str((colors.get(status_color_key) or {}).get("color") or fallback)


def _active_task_title(task: dict[str, Any] | None) -> str:
    if not task:
        return ""
    return str(task.get("title") or task.get("id") or "").strip()


def derive_leon_character(
    state: dict[str, Any],
    *,
    ui_preview: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Derive Leon's character renderer state from safe runtime status.

    The browser consumes this payload directly. It intentionally separates the
    character's functional status from decorative UI composition previews.
    """

    policy = policy or load_ui_policy()
    ui_preview = ui_preview or {}
    tasks = [dict(item) for item in state.get("tasks") or []]
    approvals = [dict(item) for item in state.get("approvals") or []]
    required_env = [dict(item) for item in state.get("required_env") or []]
    agent_runs = [dict(item) for item in state.get("agent_runs") or []]
    night_runs = [dict(item) for item in (state.get("night_queue_runs") or [])]
    metadata = dict(state.get("metadata") or {})
    preview_state = str(((ui_preview.get("assistant_state") or {}).get("id")) or "").strip().lower()

    failed_task = _first_matching(tasks, FAILED_STATUSES)
    failed_run = _first_matching(agent_runs, FAILED_STATUSES)
    failed_night_run = _first_matching(night_runs, FAILED_STATUSES)
    pending_approval = next((item for item in approvals if str(item.get("status") or "") == "pending"), None)
    missing_env = next((item for item in required_env if not item.get("present")), None)
    blocked_task = _first_matching(tasks, BLOCKED_STATUSES)
    running_run = _first_matching(agent_runs, RUNNING_STATUSES)
    running_night_run = _first_matching(night_runs, RUNNING_STATUSES)
    review_run = _first_matching(agent_runs, REVIEW_STATUSES)
    review_task = _first_matching(tasks, REVIEW_STATUSES)
    active_task = _first_matching(tasks, {"active", "planned", "todo", "open"})
    metadata_status = str(metadata.get("status") or "").strip().lower()

    state_id = "idle"
    reason = "Leon is available for a new intent."
    active_space = _normalize_space(str(ui_preview.get("space") or "home"))
    active_component = ""
    active_component_label = ""
    active_ref = ""
    behavior_source = "default_idle"

    if failed_task or failed_run or failed_night_run:
        state_id = "error"
        failure = failed_task or failed_run or failed_night_run
        reason = f"Real failure detected: {str(failure.get('status') or 'failed')}."
        active_space = "workflows"
        active_component = "TaskCard" if failed_task else "AgentRunCard"
        active_component_label = _active_task_title(failed_task) or str(failure.get("id") or "Failure")
        active_ref = str(failure.get("id") or "")
        behavior_source = "failed_task_or_run"
    elif pending_approval or missing_env or blocked_task or preview_state in {
        "waiting_for_approval",
        "waiting_for_secret",
        "blocked",
    }:
        state_id = "attention"
        if pending_approval:
            reason = "Approval is required before Leon can continue."
            active_space = "skills"
            active_component = "ApprovalSheet"
            active_component_label = str(pending_approval.get("title") or pending_approval.get("id") or "Approval")
            active_ref = str(pending_approval.get("id") or "")
            behavior_source = "pending_approval"
        elif missing_env:
            reason = "A required local env key is missing."
            active_space = "settings"
            active_component = "SecretIntakeCard"
            active_component_label = str(missing_env.get("key") or "Required env")
            active_ref = str(missing_env.get("key") or "")
            behavior_source = "missing_env"
        else:
            reason = "A task is blocked and needs input."
            active_space = "workflows"
            active_component = "TaskCard"
            active_component_label = _active_task_title(blocked_task)
            active_ref = str((blocked_task or {}).get("id") or "")
            behavior_source = "blocked_task"
    elif running_run or running_night_run:
        state_id = "acting"
        run = running_run or running_night_run or {}
        reason = "Leon is executing approved local work."
        active_space = "workflows"
        active_component = "AgentRunCard" if running_run else "TaskQueue"
        active_component_label = str(run.get("agent_role") or run.get("id") or "Active work")
        active_ref = str(run.get("id") or "")
        behavior_source = "running_work"
    elif review_run or review_task or preview_state == "reviewing":
        state_id = "interacting"
        item = review_run or review_task or {}
        reason = "Leon has reviewable output ready in the work area."
        active_space = "workflows"
        active_component = "AgentRunCard" if review_run else "TaskCard"
        active_component_label = str(item.get("agent_role") or _active_task_title(item) or "Reviewable work")
        active_ref = str(item.get("id") or "")
        behavior_source = "reviewable_work"
    elif metadata_status in SLEEPING_STATUSES:
        state_id = "sleeping"
        reason = "Leon is sleeping with no active local work."
        active_space = "home"
        behavior_source = "metadata_status"
    elif active_task or preview_state in {"thinking", "researching"}:
        state_id = "thinking"
        reason = "Leon is planning, routing, or preparing a reviewable next step."
        active_space = _normalize_space(str(ui_preview.get("space") or "workflows"))
        active_component = str((ui_preview.get("component_ids") or ["TaskQueue"])[0] or "TaskQueue")
        active_component_label = _active_task_title(active_task) or active_component
        active_ref = str((active_task or {}).get("id") or "")
        behavior_source = "planning_or_open_task"

    state_def = _character_state_def(policy, state_id)
    status_color_key = str(state_def.get("status_color") or state_id)
    return {
        "id": state_id,
        "label": state_def.get("label", state_id.title()),
        "reason": reason,
        "status_color_key": status_color_key,
        "color": _status_color(policy, status_color_key),
        "motion": state_def.get("motion", "none"),
        "glow": state_def.get("glow", "soft"),
        "particles": state_def.get("particles", "none"),
        "dimmed": bool(state_def.get("dimmed", False)),
        "danger": bool(state_def.get("danger", state_id == "error")),
        "active_space": active_space,
        "active_component": active_component,
        "active_component_label": active_component_label,
        "active_ref": active_ref,
        "behavior_source": behavior_source,
    }


def _component_cards(policy: dict[str, Any], component_ids: list[str]) -> list[dict[str, Any]]:
    registry = policy.get("component_registry") or {}
    cards = []
    for component_id in component_ids:
        raw = dict(registry.get(component_id) or {})
        if not raw:
            cards.append(
                {
                    "id": component_id,
                    "purpose": "Missing component; use closest safe fallback.",
                    "allowed_spaces": [],
                    "required_state": [],
                    "safety_role": "missing_component",
                    "registered": False,
                }
            )
            continue
        raw["id"] = component_id
        raw["registered"] = True
        raw["allowed_spaces"] = [_normalize_space(item) for item in raw.get("allowed_spaces") or []]
        cards.append(raw)
    return cards


def _fallback_context(
    *,
    requested_component: str,
    route: str,
    task_status: str,
    risk_level: str,
    space: str,
    fallback_component_ids: list[str],
    safety_notes: list[str],
) -> dict[str, Any]:
    requested = requested_component or f"route:{route}"
    capability = (
        "Registered UI component needed for a requested capability."
        if requested_component
        else "Registered UI composition rule needed for an unknown route."
    )
    return {
        "requested_component": requested,
        "requested_capability": capability,
        "route": route,
        "task_status": task_status,
        "risk_level": risk_level,
        "space": space,
        "fallback_component_ids": fallback_component_ids,
        "temporary_alternative": {
            "component_ids": fallback_component_ids,
            "reason": "Use registered context, uncertainty, approval or policy components until a reviewed component exists.",
        },
        "safety_notes": safety_notes,
    }


def _build_dock_contract(policy: dict[str, Any]) -> dict[str, Any]:
    canvas_shell = policy.get("canvas_shell") or {}
    raw_dock = dict(canvas_shell.get("dock") or {})
    primary_space_ids = [
        _normalize_space(str(item)) for item in raw_dock.get("primary_spaces") or CORE_CANVAS_SPACES
    ]
    primary_space_ids = [item for item in _dedupe(primary_space_ids) if item in CORE_CANVAS_SPACES]
    if not primary_space_ids:
        primary_space_ids = list(CORE_CANVAS_SPACES)

    space_items = [
        {
            "id": space_id,
            "label": SPACE_LABELS[space_id],
            "target_space": space_id,
            "kind": "space",
            "aria_label": f"Open {SPACE_LABELS[space_id]} canvas space",
        }
        for space_id in primary_space_ids
    ]

    action_items = []
    for raw_action in raw_dock.get("core_actions") or []:
        target_space = _normalize_space(str(raw_action.get("target_space") or "home"))
        if target_space not in CORE_CANVAS_SPACES:
            continue
        action_id = str(raw_action.get("id") or "").strip()
        if not action_id:
            continue
        label = str(raw_action.get("label") or action_id.replace("_", " ").title())
        action_items.append(
            {
                "id": action_id,
                "label": label,
                "target_space": target_space,
                "kind": "action",
                "operation": str(raw_action.get("operation") or "focus_space"),
                "aria_label": str(raw_action.get("aria_label") or label),
            }
        )

    return {
        "placement": raw_dock.get("placement", "bottom_center_floating"),
        "visual_weight": raw_dock.get("visual_weight", "lightweight_glass"),
        "behavior": raw_dock.get("behavior", "transient_focus_controls"),
        "primary_spaces": space_items,
        "core_actions": action_items,
        "interaction_model": {
            "space_change": "set_active_canvas_space",
            "page_reload": False,
            "scroll_behavior": "smooth",
            "active_state": "aria_pressed",
            "keyboard_support": ["tab", "enter", "space"],
            "min_target_px": 44,
            "responsive_overflow": "horizontal_scroll_on_small_viewports",
            **dict(raw_dock.get("interaction_model") or {}),
        },
        "permanent_sidebar": False,
    }


def build_canvas_shell(policy: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the inert canvas shell contract exposed to the local UI.

    Placements are advisory and are limited to component types registered in
    the UI policy. The browser may move/expand approved cards, but it should
    never invent a new component type outside this registry.
    """

    policy = policy or load_ui_policy()
    raw_spaces = policy.get("spaces") or {}
    registry = policy.get("component_registry") or {}
    placement_contract = (policy.get("canvas_shell") or {}).get("placement_contract") or {}
    positions = {
        "home": {"x": 0, "y": 0, "w": 2, "h": 2},
        "chat": {"x": 2, "y": 0, "w": 1, "h": 1},
        "workflows": {"x": 3, "y": 0, "w": 2, "h": 1},
        "memory": {"x": 0, "y": 2, "w": 2, "h": 1},
        "skills": {"x": 2, "y": 1, "w": 1, "h": 2},
        "projects": {"x": 3, "y": 1, "w": 2, "h": 2},
        "settings": {"x": 2, "y": 3, "w": 3, "h": 1},
    }

    spaces: list[dict[str, Any]] = []
    placements: list[dict[str, Any]] = []
    for index, space_id in enumerate(CORE_CANVAS_SPACES):
        raw = dict(raw_spaces.get(space_id) or {})
        primary_components = [str(item) for item in raw.get("primary_components") or []]
        approved_components = []
        for component_index, component_id in enumerate(primary_components):
            component = dict(registry.get(component_id) or {})
            component["registered"] = bool(component)
            component["allowed_spaces"] = [
                _normalize_space(item) for item in component.get("allowed_spaces") or []
            ]
            if not _component_allowed_in_space(component, space_id):
                continue
            approved_components.append(component_id)
            placements.append(
                {
                    "id": f"{space_id}-{component_id}",
                    "space": space_id,
                    "component_type": component_id,
                    "component_id": component_id,
                    "region": "primary" if component_index == 0 else "support",
                    "order": component_index,
                    "approved": True,
                    "dynamic": True,
                    "allowed_operations": list(placement_contract.get("allowed_operations") or []),
                }
            )
        spaces.append(
            {
                "id": space_id,
                "label": SPACE_LABELS[space_id],
                "purpose": raw.get("purpose", ""),
                "position": positions[space_id],
                "primary_components": primary_components,
                "approved_components": approved_components,
                "connected_to": [
                    CORE_CANVAS_SPACES[(index - 1) % len(CORE_CANVAS_SPACES)],
                    CORE_CANVAS_SPACES[(index + 1) % len(CORE_CANVAS_SPACES)],
                ],
            }
        )

    return {
        "ok": True,
        "navigation_model": (policy.get("canvas_shell") or {}).get("navigation_model", "bottom_dock"),
        "layout_model": (policy.get("canvas_shell") or {}).get("layout_model", "connected_spatial_canvas"),
        "permanent_sidebar": False,
        "spaces": spaces,
        "placements": placements,
        "approved_component_types": sorted(registry.keys()),
        "placement_contract": placement_contract,
        "animation_system": (policy.get("canvas_shell") or {}).get("animation_system", {}),
        "dock": _build_dock_contract(policy),
    }


def _find_rule(policy: dict[str, Any], route: str) -> dict[str, Any] | None:
    for rule in policy.get("composition_rules") or []:
        if str(rule.get("when_route") or "") == route:
            return dict(rule)
    return None


def _task_status_overlay(policy: dict[str, Any], task_status: str) -> dict[str, Any] | None:
    raw = (policy.get("task_status_rules") or {}).get(task_status)
    return dict(raw) if raw else None


def compose_ui(
    *,
    route: str = "direct_answer",
    task_status: str = "",
    risk_level: str = "low",
    requires_approval: bool = False,
    missing_secret: bool = False,
    component_need: str = "",
    compact: bool = False,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a safe UI composition plan.

    This is advisory only. It does not execute actions, mutate state, or
    promote components. Unknown needs are represented through a missing
    component protocol instead of generating new UI.
    """

    policy = policy or load_ui_policy()
    route = str(route or "direct_answer").strip()
    task_status = str(task_status or "").strip()
    risk_level = str(risk_level or "low").strip()
    component_need = str(component_need or "").strip()
    requires_approval = bool(requires_approval)
    missing_secret = bool(missing_secret)

    rule = _find_rule(policy, route)
    missing_component_protocol = False
    route_missing = False
    missing_requested_component = ""
    if rule is None:
        rule = {
            "space": "home",
            "components": ["AssistantStatusPill", "ProjectStatusCard", "UncertaintyCard"],
            "assistant_state": "blocked",
            "friction_required": True,
        }
        missing_component_protocol = True
        route_missing = True

    space = _normalize_space(str(rule.get("space") or "home"))
    components = list(rule.get("components") or [])
    assistant_state = str(rule.get("assistant_state") or "idle")
    friction_required = bool(rule.get("friction_required", False))

    overlay = _task_status_overlay(policy, task_status)
    if overlay:
        space = _normalize_space(str(overlay.get("space") or space))
        assistant_state = str(overlay.get("assistant_state") or assistant_state)
        components.extend([str(item) for item in overlay.get("required_components") or []])

    if requires_approval:
        friction_required = True
        assistant_state = "waiting_for_approval"
        if "ApprovalSheet" not in components:
            components.append("ApprovalSheet")
    if missing_secret:
        friction_required = True
        assistant_state = "waiting_for_secret"
        space = "settings"
        if "SecretIntakeCard" not in components:
            components.append("SecretIntakeCard")
    if risk_level in {"high", "critical"}:
        friction_required = True
        if not any(component in components for component in ["ApprovalSheet", "PolicyRuleCard", "PermissionCheckCard"]):
            components.append("PolicyRuleCard")
    if component_need:
        registry = policy.get("component_registry") or {}
        if component_need in registry:
            components.append(component_need)
        else:
            missing_component_protocol = True
            missing_requested_component = component_need
            components.extend(["ContextCard", "UncertaintyCard"])

    components = _dedupe(components)
    limit_key = "max_primary_components_compact" if compact else "max_primary_components_complex"
    max_components = int(((policy.get("friction_metrics") or {}).get("limits") or {}).get(limit_key, 5))
    too_many_components = len(components) > max_components
    if too_many_components:
        friction_required = True
        components = components[:max_components]
        if "UncertaintyCard" not in components and max_components > 0:
            components[-1] = "UncertaintyCard"

    assistant_def = dict((policy.get("assistant_states") or {}).get(assistant_state) or {})
    cards = _component_cards(policy, components)
    unregistered = [card["id"] for card in cards if not card.get("registered")]
    safety_notes = []
    if friction_required:
        safety_notes.append("Friction required: approval, policy, uncertainty or user input must remain visible.")
    if missing_component_protocol:
        safety_notes.append("Missing Component Protocol: use closest safe registered components and log the gap.")
    if unregistered:
        safety_notes.append("Unregistered component requested; do not render high-risk custom UI.")
    if too_many_components:
        safety_notes.append("Composition was reduced to avoid overloading the user.")
    fallback_component_ids = [
        component_id
        for component_id in components
        if component_id in (policy.get("component_registry") or {}) and component_id != missing_requested_component
    ]
    missing_component_records = []
    if missing_component_protocol:
        missing_component_records.append(
            _fallback_context(
                requested_component=missing_requested_component,
                route=route,
                task_status=task_status,
                risk_level=risk_level,
                space=space,
                fallback_component_ids=fallback_component_ids,
                safety_notes=safety_notes,
            )
        )

    return {
        "ok": True,
        "policy_version": policy.get("version"),
        "status": "preview_only",
        "execution_allowed": False,
        "route": route,
        "task_status": task_status,
        "risk_level": risk_level,
        "space": space,
        "assistant_state": {
            "id": assistant_state,
            "label": assistant_def.get("label", assistant_state),
            "description": assistant_def.get("description", ""),
            "motion": assistant_def.get("motion", "none"),
        },
        "components": cards,
        "component_ids": components,
        "temporary_alternative": (
            missing_component_records[0]["temporary_alternative"] if missing_component_records else {}
        ),
        "missing_component_records": missing_component_records,
        "missing_route": route_missing,
        "friction_required": friction_required,
        "missing_component_protocol": missing_component_protocol,
        "safety_notes": safety_notes,
        "safety_invariants": list(policy.get("safety_invariants") or []),
    }
