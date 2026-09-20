import json
from pathlib import Path

import pytest

from leon_control_plane.store import ControlPlaneStore
from leon_control_plane.tool_catalog import load_tool_catalog, sync_tool_catalog


ROOT = Path(__file__).resolve().parents[1]


def test_committed_catalog_is_valid_and_contains_requested_gaia_integrations():
    manifests = load_tool_catalog(ROOT / "config" / "tool-catalog.candidates.json")
    by_id = {item["tool_id"]: item for item in manifests}
    assert {
        "marktplaats-mcp-candidate", "vinted-mcp-candidate", "bank-mcp-candidate",
        "market-data-mcp-candidate", "paypal-mcp-candidate", "dish-roster-connector-candidate",
        "magister-connector-candidate", "ticketswap-connector-candidate",
        "moonraker-printer-connector-candidate", "sketchfab-reference-candidate",
        "meshy-image-to-3d-candidate",
        "aliexpress-fetchaller-candidate",
    } <= set(by_id)
    assert all(item["status"] == "candidate" for item in by_id.values())


def test_catalog_sync_is_idempotent_and_preserves_reviewed_status(tmp_path):
    store = ControlPlaneStore(tmp_path / "control-plane.sqlite", ROOT / "state" / "control-plane.seed.json")
    manifests = load_tool_catalog(ROOT / "config" / "tool-catalog.candidates.json")
    first = sync_tool_catalog(store, manifests)
    assert first["created"] == len(manifests)
    selected = store.get_tool_manifest("marktplaats-mcp-candidate")
    store.upsert_tool_manifest({**selected, "status": "approved_readonly"}, allow_status_change=True)
    second = sync_tool_catalog(store, manifests)
    assert second == {"created": 0, "updated": len(manifests) - 1, "protected": 1, "total": len(manifests)}
    assert store.get_tool_manifest("marktplaats-mcp-candidate")["status"] == "approved_readonly"
    assert store.get_tool_manifest("marktplaats-mcp-candidate")["notes"] == selected["notes"]


def test_catalog_loader_rejects_duplicate_ids(tmp_path):
    original = json.loads((ROOT / "config" / "tool-catalog.candidates.json").read_text())
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps([original[0], original[0]]))
    with pytest.raises(ValueError, match="duplicate"):
        load_tool_catalog(path)
