from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from leon_control_plane.agent_run_model import SUPPORTED_AGENT_RUN_ROLES

MAX_SKILL_CONFIG_BYTES = 64 * 1024
SKILL_FIELDS = {"id", "role", "task_types", "instructions", "allowed_actions", "output_kind"}


def load_agent_skills(path: Path) -> tuple[dict[str, Any], ...]:
    raw = path.read_bytes()
    if len(raw) > MAX_SKILL_CONFIG_BYTES:
        raise ValueError("Agent skill config exceeds size limit")
    document = json.loads(raw)
    if not isinstance(document, dict) or set(document) != {"version", "skills"} or document["version"] != 1:
        raise ValueError("Agent skill config schema is invalid")
    skills = document["skills"]
    if not isinstance(skills, list) or not skills or len(skills) > 32:
        raise ValueError("Agent skill list is invalid")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in skills:
        if not isinstance(item, dict) or set(item) != SKILL_FIELDS:
            raise ValueError("Agent skill entry schema is invalid")
        skill_id = item["id"]
        role = item["role"]
        task_types = item["task_types"]
        instructions = item["instructions"]
        allowed_actions = item["allowed_actions"]
        output_kind = item["output_kind"]
        if (
            not isinstance(skill_id, str) or not skill_id.isascii() or not skill_id.replace("-", "").isalnum()
            or skill_id in seen or role not in SUPPORTED_AGENT_RUN_ROLES
            or not isinstance(task_types, list) or not task_types or len(task_types) > 12
            or not all(isinstance(value, str) and 1 <= len(value) <= 64 for value in task_types)
            or not isinstance(instructions, str) or not 1 <= len(instructions) <= 1200
            or not isinstance(allowed_actions, list) or not allowed_actions or len(allowed_actions) > 16
            or not all(isinstance(value, str) and 1 <= len(value) <= 64 for value in allowed_actions)
            or not isinstance(output_kind, str) or not 1 <= len(output_kind) <= 64
        ):
            raise ValueError("Agent skill entry value is invalid")
        seen.add(skill_id)
        normalized.append({
            "id": skill_id,
            "role": role,
            "task_types": tuple(task_types),
            "instructions": instructions,
            "allowed_actions": tuple(allowed_actions),
            "output_kind": output_kind,
        })
    return tuple(normalized)


def select_agent_skill(skills: tuple[dict[str, Any], ...], *, role: str, task_type: str) -> dict[str, Any]:
    exact = [skill for skill in skills if skill["role"] == role and task_type in skill["task_types"]]
    if len(exact) != 1:
        raise ValueError("Exactly one agent skill must match role and task type")
    return dict(exact[0])
