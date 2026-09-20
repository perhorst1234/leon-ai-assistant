import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "integrations" / "shopper" / "aliexpress-safe"


def test_aliexpress_safe_source_manifest_covers_every_file():
    manifest_path = SOURCE / "source-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert set(manifest) == {
        "version", "name", "version_string", "upstream_name", "upstream_version",
        "source_archive_sha256", "source_license", "source_license_sha256", "files",
    }
    assert manifest["version"] == 1
    assert manifest["name"] == "aliexpress-safe-stdio"
    assert manifest["version_string"] == "1.0.0"
    assert manifest["upstream_name"] == "fetchaller-mcp"
    assert manifest["upstream_version"] == "3.5.4"
    assert manifest["source_archive_sha256"] == "3ba53ffeb29f5af4477ad749c14cb627291c7ad64e9c294157dd5dea2b9abfcd"
    assert manifest["source_license"] == "MIT"
    assert manifest["source_license_sha256"] == "584263df63d4217a82ba7ba80bda238020294f30767ed8efac35bec5b55fddf6"
    expected = manifest["files"]
    current = {
        path.relative_to(SOURCE).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(SOURCE.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    assert current == expected


def test_aliexpress_safe_source_has_exact_read_only_tool_surface():
    source = (SOURCE / "src" / "index.ts").read_text()
    expected = {
        "search_aliexpress",
        "get_aliexpress_product",
        "search_aliexpress_bundle_deals",
        "build_aliexpress_bundle",
    }
    block = re.search(r"const tools = \[(.*?)\n\];", source, re.DOTALL)
    assert block is not None
    assert set(re.findall(r'name: "([^"]+)"', block.group(1))) == expected
    assert block.group(1).count("annotations, inputSchema") == len(expected)
    assert "readOnlyHint: true" in source
    assert "destructiveHint: false" in source
    for forbidden in ("create_aliexpress_bundle_cart", "connect_aliexpress_account"):
        assert forbidden not in source
    assert 'method: "GET"' in source
    assert 'redirect: "error"' in source
