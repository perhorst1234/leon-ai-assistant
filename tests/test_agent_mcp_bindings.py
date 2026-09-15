import json
from pathlib import Path

import pytest

from leon_control_plane.agent_mcp_bindings import load_agent_mcp_bindings, resolve_agent_mcp_binding


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "agent-mcp-bindings.json"


def test_committed_shopper_bindings_are_pinned_read_only_candidates():
    bindings = load_agent_mcp_bindings(CONFIG)
    assert {binding["tool_id"] for binding in bindings} == {
        "marktplaats-marketplace", "vinted-marketplace", "paypal-sandbox-readonly",
        "bank-analysis-readonly",
    }
    for binding in bindings:
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
        "registry": "local",
        "package": "vinted-safe-stdio",
        "version": "1.0.0",
        "commit": "460317f23a4d665bd352863f388c9d299550955a",
        "integrity": "sha256:60fdca132fc6f6ac6dcfaf8d93507fef781f0dcd21912a1be5dc31656fb94c73",
    }
    assert "like_item" not in vinted["allowed_tools"]
    bank = next(binding for binding in bindings if binding["tool_id"] == "bank-analysis-readonly")
    assert bank["role"] == "Manager"
    assert bank["network_domains"] == ()
    assert bank["source"]["integrity"] == "sha512-eNMkjDexcyLirF8l6iq4sSwV9ESJwpVtTarhTc2VcJV/PodhzJCSb6YBqrAgyqMMPVcioLrtMdq2JduxBjv1kQ=="


def test_resolver_denies_by_default_and_returns_only_exact_approved_allowlist():
    bindings = load_agent_mcp_bindings(CONFIG)
    assert resolve_agent_mcp_binding(bindings, role="Shopper", tool_id="marktplaats-marketplace")["decision"] == "denied"
    paypal = next(binding for binding in bindings if binding["tool_id"] == "paypal-sandbox-readonly")
    assert paypal["source"]["integrity"] == "sha512-5r0TGkIhg66TSErwoLxatZbPHWjPnLQBHxoRG9vpobPRyzLF0tt2F8ca3Ca18SdfR8I32Usps7pzd/RuAF1Lsg=="
    assert "orders.capture" not in paypal["allowed_tools"]
    assert "payments.createRefund" not in paypal["allowed_tools"]
    assert resolve_agent_mcp_binding(bindings, role="Shopper", tool_id="paypal-sandbox-readonly")["decision"] == "denied"
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


def test_loader_accepts_exact_external_tool_names_but_rejects_shell_syntax(tmp_path):
    document = json.loads(CONFIG.read_text())
    paypal = next(item for item in document["bindings"] if item["tool_id"] == "paypal-sandbox-readonly")
    assert "subscriptionPlans.show" in paypal["allowed_tools"]
    paypal["allowed_tools"][0] = "orders.get;rm"
    path = tmp_path / "bindings.json"
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="allowed_tools"):
        load_agent_mcp_bindings(path)


def test_loader_allows_unresolved_domains_only_while_binding_is_disabled(tmp_path):
    document = json.loads(CONFIG.read_text())
    bank = next(item for item in document["bindings"] if item["tool_id"] == "bank-analysis-readonly")
    assert bank["network_domains"] == []
    bank["mode"] = "readonly"
    path = tmp_path / "bindings.json"
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="requires network_domains"):
        load_agent_mcp_bindings(path)
