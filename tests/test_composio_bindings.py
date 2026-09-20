import json
from pathlib import Path

import pytest

from leon_control_plane.composio_bindings import load_composio_bindings, resolve_composio_binding


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "composio-bindings.json"


def test_candidate_contract_is_exact_and_inert():
    binding = load_composio_bindings(CONFIG)
    assert binding["mode"] == "candidate_disabled"
    assert binding["role"] == "Planner"
    assert [(item["name"], item["version"]) for item in binding["toolkits"]] == [("gmail", "20260903_00"), ("googlecalendar", "20260902_00")]
    assert all(binding[key] is False for key in ("meta_tools", "sandbox", "workbench", "remote_bash"))
    assert resolve_composio_binding(binding, toolkit="gmail", tool="GMAIL_FETCH_EMAILS")["decision"] == "denied"


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(provider="other"),
    lambda d: d.update(mode="readonly"),
    lambda d: d["toolkits"].append({"name": "drive", "version": "20260901_00", "allowed_tools": ["DRIVE_LIST_FILES"], "read_scopes": ["drive.readonly"]}),
    lambda d: d["toolkits"][0]["allowed_tools"].append("GMAIL_SEND_EMAIL"),
    lambda d: d["toolkits"][0].update(read_scopes=["gmail.modify"]),
    lambda d: d.update(remote_bash=True),
    lambda d: d["forbidden_tools"].remove("GMAIL_SEND_EMAIL"),
    lambda d: d["toolkits"][0].update(extra="unknown"),
])
def test_loader_rejects_scope_expansion_unknown_keys_and_enablement(tmp_path, mutate):
    document = json.loads(CONFIG.read_text())
    mutate(document)
    path = tmp_path / "bindings.json"
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError):
        load_composio_bindings(path)


def test_loader_rejects_wildcards_and_unbounded_limits(tmp_path):
    document = json.loads(CONFIG.read_text())
    document["toolkits"][0]["allowed_tools"][0] = "*"
    document["max_results"] = 101
    path = tmp_path / "bindings.json"
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError):
        load_composio_bindings(path)
