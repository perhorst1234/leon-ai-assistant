from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from leon_control_plane.agent_run_model import SUPPORTED_AGENT_RUN_ROLES


MAX_BINDING_CONFIG_BYTES = 128 * 1024
MAX_BINDINGS = 32
MODES = {"candidate_disabled", "readonly"}
REGISTRIES = {"local", "npm", "pypi"}
REQUIRED_FORBIDDEN_ACTIONS = frozenset({
    "purchase",
    "bid",
    "payment",
    "send_message",
    "read_raw_secret",
    "captcha_bypass",
    "anti_bot_evasion",
    "proxy_rotation",
})

DOCUMENT_FIELDS = {"version", "bindings"}
BINDING_FIELDS = {
    "source",
    "role",
    "tool_id",
    "mode",
    "allowed_tools",
    "read_scopes",
    "forbidden_actions",
    "network_domains",
    "max_results",
    "timeout_seconds",
}
SOURCE_FIELDS = {"registry", "package", "version", "commit", "integrity"}
SAFE_ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
SAFE_TOOL_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,95}$")
SAFE_PACKAGE = re.compile(r"^(?:@[a-z0-9._-]+/)?[a-z0-9][a-z0-9._-]{0,127}$")
EXACT_VERSION = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
DOMAIN = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
PYPI_INTEGRITY = re.compile(r"^sha256:[0-9a-f]{64}$")
NPM_INTEGRITY = re.compile(r"^sha512-[A-Za-z0-9+/]{86}==$")


def _string_list(
    value: Any,
    *,
    maximum: int,
    field: str,
    pattern: re.Pattern[str] = SAFE_ID,
) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or len(value) > maximum
        or not all(isinstance(item, str) and pattern.fullmatch(item) for item in value)
        or len(set(value)) != len(value)
    ):
        raise ValueError(f"Agent MCP binding {field} is invalid")
    return tuple(value)


def load_agent_mcp_bindings(path: Path) -> tuple[dict[str, Any], ...]:
    raw = path.read_bytes()
    if len(raw) > MAX_BINDING_CONFIG_BYTES:
        raise ValueError("Agent MCP binding config exceeds size limit")
    document = json.loads(raw)
    if not isinstance(document, dict) or set(document) != DOCUMENT_FIELDS or document.get("version") != 1:
        raise ValueError("Agent MCP binding config schema is invalid")
    items = document.get("bindings")
    if not isinstance(items, list) or not items or len(items) > MAX_BINDINGS:
        raise ValueError("Agent MCP binding list is invalid")

    bindings: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != BINDING_FIELDS:
            raise ValueError("Agent MCP binding entry schema is invalid")
        source = item["source"]
        if not isinstance(source, dict) or set(source) != SOURCE_FIELDS:
            raise ValueError("Agent MCP binding source schema is invalid")

        registry = source["registry"]
        package = source["package"]
        version = source["version"]
        commit = source["commit"]
        integrity = source["integrity"]
        expected_integrity = NPM_INTEGRITY if registry == "npm" else PYPI_INTEGRITY
        if (
            registry not in REGISTRIES
            or not isinstance(package, str)
            or not SAFE_PACKAGE.fullmatch(package)
            or not isinstance(version, str)
            or not EXACT_VERSION.fullmatch(version)
            or not isinstance(commit, str)
            or not COMMIT_SHA.fullmatch(commit)
            or not isinstance(integrity, str)
            or not expected_integrity.fullmatch(integrity)
        ):
            raise ValueError("Agent MCP binding source value is invalid")

        role = item["role"]
        tool_id = item["tool_id"]
        mode = item["mode"]
        if (
            role not in SUPPORTED_AGENT_RUN_ROLES
            or not isinstance(tool_id, str)
            or not SAFE_ID.fullmatch(tool_id)
            or mode not in MODES
        ):
            raise ValueError("Agent MCP binding identity is invalid")
        identity = (role, tool_id)
        if identity in seen:
            raise ValueError("Agent MCP binding identity is duplicated")

        allowed_tools = _string_list(
            item["allowed_tools"], maximum=32, field="allowed_tools", pattern=SAFE_TOOL_NAME
        )
        read_scopes = _string_list(item["read_scopes"], maximum=32, field="read_scopes")
        forbidden_actions = _string_list(item["forbidden_actions"], maximum=32, field="forbidden_actions")
        domains = item["network_domains"]
        if (
            not isinstance(domains, list)
            or not domains
            or len(domains) > 16
            or not all(isinstance(domain, str) and DOMAIN.fullmatch(domain) for domain in domains)
            or len(set(domains)) != len(domains)
        ):
            raise ValueError("Agent MCP binding network_domains is invalid")
        if not REQUIRED_FORBIDDEN_ACTIONS.issubset(forbidden_actions):
            raise ValueError("Agent MCP binding misses required forbidden actions")
        if set(allowed_tools) & set(forbidden_actions):
            raise ValueError("Agent MCP binding allows a forbidden action")
        max_results = item["max_results"]
        timeout_seconds = item["timeout_seconds"]
        if type(max_results) is not int or not 1 <= max_results <= 100:
            raise ValueError("Agent MCP binding max_results is invalid")
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 30:
            raise ValueError("Agent MCP binding timeout_seconds is invalid")

        seen.add(identity)
        bindings.append({
            "source": dict(source),
            "role": role,
            "tool_id": tool_id,
            "mode": mode,
            "allowed_tools": allowed_tools,
            "read_scopes": read_scopes,
            "forbidden_actions": forbidden_actions,
            "network_domains": tuple(domains),
            "max_results": max_results,
            "timeout_seconds": timeout_seconds,
        })
    return tuple(bindings)


def resolve_agent_mcp_binding(
    bindings: tuple[dict[str, Any], ...],
    *,
    role: str,
    tool_id: str,
    manifest_status: str | None = None,
) -> dict[str, Any]:
    """Resolve one exact role/tool binding. Every missing or unapproved case denies."""
    matches = [binding for binding in bindings if binding["role"] == role and binding["tool_id"] == tool_id]
    if len(matches) != 1:
        return {"decision": "denied", "reason": "binding_not_found", "allowed_tools": ()}
    binding = matches[0]
    if manifest_status != "approved_readonly":
        return {"decision": "denied", "reason": "manifest_not_approved_readonly", "allowed_tools": ()}
    if binding["mode"] != "readonly":
        return {"decision": "denied", "reason": "binding_not_enabled_readonly", "allowed_tools": ()}
    return {
        **binding,
        "decision": "allowed",
        "mode": "readonly",
        "allowed_tools": tuple(binding["allowed_tools"]),
    }
