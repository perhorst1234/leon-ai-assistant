from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from leon_control_plane.store import ControlPlaneStore
from leon_control_plane.tool_registry import normalize_tool_manifest


ROOT = Path(__file__).resolve().parents[2]
MAX_CATALOG_BYTES = 2 * 1024 * 1024
MAX_CATALOG_ITEMS = 256


def load_tool_catalog(path: Path) -> tuple[dict[str, Any], ...]:
    raw = path.read_bytes()
    if len(raw) > MAX_CATALOG_BYTES:
        raise ValueError("Tool catalog exceeds size limit")
    document = json.loads(raw)
    if not isinstance(document, list) or not document or len(document) > MAX_CATALOG_ITEMS:
        raise ValueError("Tool catalog must be a bounded non-empty list")
    manifests = tuple(normalize_tool_manifest(item) for item in document)
    ids = [item["tool_id"] for item in manifests]
    if len(ids) != len(set(ids)):
        raise ValueError("Tool catalog contains duplicate tool_id")
    return manifests


def sync_tool_catalog(store: ControlPlaneStore, manifests: tuple[dict[str, Any], ...]) -> dict[str, int]:
    """Register catalog metadata without installing, connecting or changing status."""
    created = 0
    updated = 0
    protected = 0
    for manifest in manifests:
        try:
            existing = store.get_tool_manifest(manifest["tool_id"])
        except ValueError:
            created += 1
        else:
            if existing["status"] in {"approved_readonly", "approved_write_gated"}:
                protected += 1
                continue
            updated += 1
        store.upsert_tool_manifest(
            manifest,
            actor_type="system",
            actor_id="tool-catalog-sync",
            allow_status_change=False,
        )
    return {"created": created, "updated": updated, "protected": protected, "total": len(manifests)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync reviewed metadata from Leon tool candidate catalog")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=ROOT / "config" / "tool-catalog.candidates.json")
    parser.add_argument("--seed", type=Path, default=ROOT / "state" / "control-plane.seed.json")
    args = parser.parse_args(argv)
    manifests = load_tool_catalog(args.catalog.expanduser().resolve())
    result = sync_tool_catalog(ControlPlaneStore(args.db.expanduser().resolve(), args.seed.expanduser().resolve()), manifests)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
