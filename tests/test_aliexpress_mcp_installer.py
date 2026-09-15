import json
from pathlib import Path

import pytest

from leon_control_plane import aliexpress_mcp


def _fake_runtime(target: Path) -> None:
    (target / "dist").mkdir(parents=True)
    (target / "dist" / "index.js").write_text("safe runtime\n")
    package = {
        "name": aliexpress_mcp.PACKAGE,
        "version": aliexpress_mcp.VERSION,
        "main": "dist/index.js",
        "dependencies": {"@modelcontextprotocol/sdk": aliexpress_mcp.SDK_VERSION},
    }
    lock = {
        "packages": {
            "": {"dependencies": package["dependencies"]},
            "node_modules/@modelcontextprotocol/sdk": {
                "version": aliexpress_mcp.SDK_VERSION,
                "integrity": aliexpress_mcp.SDK_INTEGRITY,
            },
        }
    }
    (target / "package.json").write_text(json.dumps(package))
    (target / "package-lock.json").write_text(json.dumps(lock))


def test_committed_aliexpress_source_and_lock_match_installer_contract():
    aliexpress_mcp._verify_source()
    aliexpress_mcp._verify_package_files(aliexpress_mcp.SOURCE)


def test_runtime_manifest_rejects_changed_or_added_files(tmp_path, monkeypatch):
    monkeypatch.setattr(aliexpress_mcp, "ROOT", tmp_path)
    target = tmp_path / ".runtime" / "mcp" / "aliexpress-safe-1.0.0"
    _fake_runtime(target)
    aliexpress_mcp._write_runtime_manifest(target)
    assert aliexpress_mcp.verify_installation(target)["enabled"] is False

    (target / "dist" / "index.js").write_text("tampered\n")
    with pytest.raises(RuntimeError, match="integrity check failed"):
        aliexpress_mcp.verify_installation(target)

    (target / "dist" / "index.js").write_text("safe runtime\n")
    (target / "extra.js").write_text("unexpected\n")
    with pytest.raises(RuntimeError, match="integrity check failed"):
        aliexpress_mcp.verify_installation(target)


def test_installer_uses_scriptless_exact_registry_install(tmp_path, monkeypatch):
    monkeypatch.setattr(aliexpress_mcp, "ROOT", tmp_path)
    monkeypatch.setattr(aliexpress_mcp, "_verify_source", lambda: None)
    monkeypatch.setattr(aliexpress_mcp, "_verify_package_files", lambda _root: None)
    monkeypatch.setattr(aliexpress_mcp.shutil, "which", lambda _npm: "/trusted/npm")
    calls = []
    monkeypatch.setattr(aliexpress_mcp.subprocess, "run", lambda command, **kwargs: calls.append((command, kwargs)))
    target = tmp_path / ".runtime" / "mcp" / "aliexpress-safe-1.0.0"
    source = tmp_path / "source"
    for relative in ("package.json", "package-lock.json", "LICENSE.md", "dist/index.js"):
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n")
    monkeypatch.setattr(aliexpress_mcp, "SOURCE", source)
    monkeypatch.setattr(aliexpress_mcp, "verify_installation", lambda _target: {"enabled": False})

    assert aliexpress_mcp.install(target=target)["enabled"] is False
    command, kwargs = calls[0]
    assert command == [
        "/trusted/npm", "ci", "--ignore-scripts", "--omit=dev", "--no-audit", "--no-fund",
        "--registry=https://registry.npmjs.org",
    ]
    assert kwargs["cwd"] == target
    assert "NODE_OPTIONS" not in kwargs["env"]
