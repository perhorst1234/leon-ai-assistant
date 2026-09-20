"""Fail-closed, non-executing contract for a future Composio Gaia binding."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


MAX_CONFIG_BYTES = 32 * 1024
MAX_RESULTS = 100
MAX_TIMEOUT_SECONDS = 30
TOOLKIT_VERSION = re.compile(r"^20\d{6}_\d{2}$")

DOCUMENT_FIELDS = {
    "version", "provider", "mode", "role", "toolkits", "preset",
    "meta_tools", "sandbox", "workbench", "remote_bash", "max_results",
    "timeout_seconds", "forbidden_tools", "forbidden_actions",
}
TOOLKIT_FIELDS = {"name", "version", "allowed_tools", "read_scopes"}
TOOLKITS = {"gmail", "googlecalendar"}

# Keep this list deliberately small. Adding a Composio action is a contract
# change and must be reviewed alongside its scope and response limits.
READ_ONLY_TOOLS = {
    "gmail": frozenset({
        "GMAIL_FETCH_EMAILS",
        "GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID",
        "GMAIL_FETCH_MESSAGE_BY_THREAD_ID",
    }),
    "googlecalendar": frozenset({
        "GOOGLECALENDAR_EVENTS_GET",
        "GOOGLECALENDAR_EVENTS_LIST",
        "GOOGLECALENDAR_FIND_EVENT",
        "GOOGLECALENDAR_FIND_FREE_SLOTS",
    }),
}
READ_ONLY_SCOPES = {
    "gmail": frozenset({"gmail.readonly"}),
    "googlecalendar": frozenset({"calendar.readonly"}),
}
REQUIRED_FORBIDDEN_TOOLS = frozenset({
    "GMAIL_SEND_EMAIL", "GMAIL_CREATE_EMAIL_DRAFT", "GMAIL_DELETE_MESSAGE",
    "GMAIL_FORWARD_MESSAGE", "GMAIL_REPLY_TO_THREAD", "GMAIL_UPDATE_DRAFT",
    "GOOGLECALENDAR_CREATE_EVENT", "GOOGLECALENDAR_DELETE_EVENT",
    "GOOGLECALENDAR_PATCH_EVENT", "GOOGLECALENDAR_UPDATE_EVENT",
    "GOOGLECALENDAR_QUICK_ADD",
})
REQUIRED_FORBIDDEN_ACTIONS = frozenset({
    "send_email", "create_draft", "delete_message", "modify_labels",
    "forward_message", "reply_to_thread", "create_event", "update_event",
    "delete_event", "move_event", "manage_connections", "remote_workbench",
    "remote_bash", "sandbox_execution",
})


def _strings(value: Any, *, field: str, maximum: int) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or len(value) > maximum
        or not all(isinstance(item, str) and item and "*" not in item for item in value)
        or len(set(value)) != len(value)
    ):
        raise ValueError(f"Composio binding {field} is invalid")
    return tuple(value)


def load_composio_bindings(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if len(raw) > MAX_CONFIG_BYTES:
        raise ValueError("Composio binding config exceeds size limit")
    document = json.loads(raw)
    if not isinstance(document, dict) or set(document) != DOCUMENT_FIELDS:
        raise ValueError("Composio binding schema is invalid")
    if (
        document["version"] != 1
        or document["provider"] != "composio"
        or document["mode"] != "candidate_disabled"
        or document["role"] != "Planner"
        or document["preset"] != "direct_tools"
        or any(document[name] is not False for name in ("meta_tools", "sandbox", "workbench", "remote_bash"))
    ):
        raise ValueError("Composio binding identity or capability switches are invalid")

    if type(document["max_results"]) is not int or not 1 <= document["max_results"] <= MAX_RESULTS:
        raise ValueError("Composio binding max_results is invalid")
    if type(document["timeout_seconds"]) is not int or not 1 <= document["timeout_seconds"] <= MAX_TIMEOUT_SECONDS:
        raise ValueError("Composio binding timeout_seconds is invalid")

    toolkits = document["toolkits"]
    if not isinstance(toolkits, list) or len(toolkits) != 2:
        raise ValueError("Composio binding toolkits are invalid")
    parsed_toolkits: list[dict[str, Any]] = []
    seen: set[str] = set()
    for toolkit in toolkits:
        if not isinstance(toolkit, dict) or set(toolkit) != TOOLKIT_FIELDS:
            raise ValueError("Composio toolkit schema is invalid")
        name = toolkit["name"]
        if name not in TOOLKITS or name in seen or not isinstance(toolkit["version"], str) or not TOOLKIT_VERSION.fullmatch(toolkit["version"]):
            raise ValueError("Composio toolkit identity is invalid")
        allowed = _strings(toolkit["allowed_tools"], field=f"{name}.allowed_tools", maximum=16)
        if set(allowed) != READ_ONLY_TOOLS[name]:
            raise ValueError(f"Composio {name} allowlist is invalid")
        scopes = _strings(toolkit["read_scopes"], field=f"{name}.read_scopes", maximum=8)
        if set(scopes) != READ_ONLY_SCOPES[name]:
            raise ValueError(f"Composio {name} read scopes are invalid")
        parsed_toolkits.append({"name": name, "version": toolkit["version"], "allowed_tools": allowed, "read_scopes": scopes})
        seen.add(name)
    if seen != TOOLKITS:
        raise ValueError("Composio toolkit set is invalid")

    forbidden_tools = _strings(document["forbidden_tools"], field="forbidden_tools", maximum=64)
    forbidden_actions = _strings(document["forbidden_actions"], field="forbidden_actions", maximum=64)
    if not REQUIRED_FORBIDDEN_TOOLS.issubset(forbidden_tools) or not REQUIRED_FORBIDDEN_ACTIONS.issubset(forbidden_actions):
        raise ValueError("Composio binding misses required write denials")
    if set(forbidden_tools) & set().union(*(READ_ONLY_TOOLS.values())):
        raise ValueError("Composio binding forbids an allowed tool")
    if any(name.upper() in forbidden_tools or name.lower() in forbidden_actions for name in ("all", "*")):
        raise ValueError("Composio binding wildcard denial is invalid")
    return {
        **document,
        "toolkits": tuple(parsed_toolkits),
        "forbidden_tools": forbidden_tools,
        "forbidden_actions": forbidden_actions,
    }


def resolve_composio_binding(binding: dict[str, Any], *, toolkit: str, tool: str) -> dict[str, Any]:
    """Resolve exact tools only; candidate bindings never become executable."""
    if binding.get("mode") != "candidate_disabled":
        return {"decision": "denied", "reason": "binding_not_candidate_disabled", "allowed_tools": ()}
    matches = [item for item in binding.get("toolkits", ()) if item.get("name") == toolkit]
    if len(matches) != 1 or tool not in matches[0]["allowed_tools"]:
        return {"decision": "denied", "reason": "tool_not_allowlisted", "allowed_tools": ()}
    return {"decision": "denied", "reason": "candidate_disabled", "allowed_tools": ()}
