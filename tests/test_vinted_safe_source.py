import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "integrations" / "shopper" / "vinted-safe"


def test_vinted_safe_source_matches_binding_integrity_and_file_manifest():
    manifest_path = SOURCE / "source-manifest.json"
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    bindings = json.loads((ROOT / "config" / "agent-mcp-bindings.json").read_text())
    binding = next(item for item in bindings["bindings"] if item["tool_id"] == "vinted-marketplace")

    assert binding["source"]["integrity"] == f"sha256:{hashlib.sha256(raw).hexdigest()}"
    assert manifest["source_archive_sha256"] == "3ba53ffeb29f5af4477ad749c14cb627291c7ad64e9c294157dd5dea2b9abfcd"
    assert manifest["upstream_commit"] == binding["source"]["commit"]
    assert set(manifest["files"]) == {
        path.relative_to(SOURCE).as_posix()
        for path in SOURCE.rglob("*")
        if path.is_file() and path != manifest_path
    }
    for relative, expected in manifest["files"].items():
        assert hashlib.sha256((SOURCE / relative).read_bytes()).hexdigest() == expected
