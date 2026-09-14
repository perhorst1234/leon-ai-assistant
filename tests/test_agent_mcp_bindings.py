import json
from pathlib import Path

import pytest

from leon_control_plane.agent_mcp_bindings import load_agent_mcp_bindings, resolve_agent_mcp_binding


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "agent-mcp-bindings.json"


def test_committed_shopper_bindings_are_pinned_read_only_candidates():
    bindings = load_agent_mcp_bindings(CONFIG)
    assert {binding["tool_id"] for binding in bindings} == {"marktplaats-marketplace", "vinted-marketplace"}
    for binding in bindings:
        assert binding["role"] == "Shopper"
        assert binding["mode"] == "candidate_disabled"
        assert binding["source"]["commit"]
        assert binding["source"]["integrity"]
        assert binding["max_results"] <= 100
        assert binding["timeout_seconds"] <= 30
        assert {"purchase", "bid", "payment", "send_message", "read_raw_secret", "captcha_bypass", "anti_bot_evasion", "proxy_rotation"} <= set(binding["forbidden_actions"])

    vinted = next(binding for binding in bindings if binding["tool_id"] == "vinted-marketplace")
    marktplaats = next(binding for binding in bindings if binding["tool_id"] == "marktplaats-marketplace")
    assert marktplaats["source"] == {
        "registry": "pypi",
        "package": "marktplaats-mcp",
        "version": "0.1.1",
        "commit": "8e650274c50c55829ce2917591631665ecd321a6",
        "integrity": "sha256:429eb3393bad0e7b8200cb946548a00a7f5e6e77454e49683c219bb2b2d3d0a7",
    }
    assert vinted["source"] == {
        "registry": "npm",
        "package": "@andrijdavid/vinted-mcp",
        "version": "0.1.2",
        "commit": "460317f23a4d665bd352863f388c9d299550955a",
        "integrity": "sha512-Wc4m2I2ci+SGlTzKEnT8Uu9Gzz9EpeUZxpclM5jbRyIGSwUD1UsUNh9sBRMln6OPZnVfJkQJg4BYIzfVIEtJMA==",
    }
    assert "like_item" not in vinted["allowed_tools"]


def test_resolver_denies_by_default_and_returns_only_exact_approved_allowlist():
    bindings = load_agent_mcp_bindings(CONFIG)
    assert resolve_agent_mcp_binding(bindings, role="Shopper", tool_id="marktplaats-marketplace")["decision"] == "denied"
    assert resolve_agent_mcp_binding(
        bindings,
        role="Shopper",
        tool_id="vinted-marketplace",
        manifest_status="approved_readonly",
    ) == {
        "decision": "denied",
        "reason": "binding_not_enabled_readonly",
        "allowed_tools": (),
    }
    assert resolve_agent_mcp_binding(
        bindings,
        role="Research",
        tool_id="marktplaats-marketplace",
        manifest_status="approved_readonly",
    )["decision"] == "denied"
    enabled_bindings = tuple(
        {**binding, "mode": "readonly"} if binding["tool_id"] == "vinted-marketplace" else binding
        for binding in bindings
    )
    resolved = resolve_agent_mcp_binding(
        enabled_bindings,
        role="Shopper",
        tool_id="vinted-marketplace",
        manifest_status="approved_readonly",
    )
    assert resolved["decision"] == "allowed"
    assert resolved["mode"] == "readonly"
    assert resolved["allowed_tools"] == ("search_items", "get_item", "get_seller", "compare_prices", "get_trending")


@pytest.mark.parametrize("field,value", [("max_results", 101), ("timeout_seconds", 31)])
def test_loader_rejects_resource_limits_above_contract(tmp_path, field, value):
    document = json.loads(CONFIG.read_text())
    document["bindings"][0][field] = value
    path = tmp_path / "bindings.json"
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match=field):
        load_agent_mcp_bindings(path)


def test_loader_rejects_commands_secrets_and_missing_hard_denials(tmp_path):
    document = json.loads(CONFIG.read_text())
    document["bindings"][0]["command"] = "run-anything"
    path = tmp_path / "bindings.json"
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="schema"):
        load_agent_mcp_bindings(path)

    document = json.loads(CONFIG.read_text())
    document["bindings"][0]["source"]["env"] = {"TOKEN": "secret"}
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="source schema"):
        load_agent_mcp_bindings(path)

    document = json.loads(CONFIG.read_text())
    document["bindings"][0]["forbidden_actions"].remove("purchase")
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="required forbidden"):
        load_agent_mcp_bindings(path)
