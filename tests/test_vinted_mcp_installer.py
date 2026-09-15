import json
from pathlib import Path

import pytest

from leon_control_plane import vinted_mcp


def _fake_runtime(target: Path) -> None:
    (target / "dist").mkdir(parents=True)
    (target / "dist" / "index.js").write_text("safe runtime\n")
    package = {
        "name": vinted_mcp.PACKAGE,
        "version": vinted_mcp.VERSION,
        "main": "dist/index.js",
        "dependencies": {"@modelcontextprotocol/sdk": vinted_mcp.SDK_VERSION},
    }
    lock = {
        "packages": {
            "": {"dependencies": package["dependencies"]},
            "node_modules/@modelcontextprotocol/sdk": {
                "version": vinted_mcp.SDK_VERSION,
                "integrity": vinted_mcp.SDK_INTEGRITY,
            },
        }
    }
    (target / "package.json").write_text(json.dumps(package))
    (target / "package-lock.json").write_text(json.dumps(lock))


def test_committed_vinted_source_and_lock_match_installer_contract():
    vinted_mcp._verify_source()
    vinted_mcp._verify_package_files(vinted_mcp.SOURCE)


def test_runtime_manifest_rejects_changed_or_added_files(tmp_path, monkeypatch):
    monkeypatch.setattr(vinted_mcp, "ROOT", tmp_path)
    target = tmp_path / ".runtime" / "mcp" / "vinted-safe-1.0.0"
    _fake_runtime(target)
    vinted_mcp._write_runtime_manifest(target)
    assert vinted_mcp.verify_installation(target)["enabled"] is False

    (target / "dist" / "index.js").write_text("tampered\n")
    with pytest.raises(RuntimeError, match="integrity check failed"):
        vinted_mcp.verify_installation(target)

    (target / "dist" / "index.js").write_text("safe runtime\n")
    (target / "extra.js").write_text("unexpected\n")
    with pytest.raises(RuntimeError, match="integrity check failed"):
        vinted_mcp.verify_installation(target)


def test_installer_uses_scriptless_exact_registry_install(tmp_path, monkeypatch):
    monkeypatch.setattr(vinted_mcp, "ROOT", tmp_path)
    monkeypatch.setattr(vinted_mcp, "_verify_source", lambda: None)
    monkeypatch.setattr(vinted_mcp, "_verify_package_files", lambda _root: None)
    monkeypatch.setattr(vinted_mcp.shutil, "which", lambda _npm: "/trusted/npm")
    calls = []
    monkeypatch.setattr(vinted_mcp.subprocess, "run", lambda command, **kwargs: calls.append((command, kwargs)))
    target = tmp_path / ".runtime" / "mcp" / "vinted-safe-1.0.0"
    source = tmp_path / "source"
    for relative in ("package.json", "package-lock.json", "LICENSE.md", "dist/index.js"):
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n")
    monkeypatch.setattr(vinted_mcp, "SOURCE", source)
    monkeypatch.setattr(vinted_mcp, "verify_installation", lambda _target: {"enabled": False})

    assert vinted_mcp.install(target=target)["enabled"] is False
    command, kwargs = calls[0]
    assert command == [
        "/trusted/npm", "ci", "--ignore-scripts", "--omit=dev", "--no-audit", "--no-fund",
        "--registry=https://registry.npmjs.org",
    ]
    assert kwargs["cwd"] == target
    assert "NODE_OPTIONS" not in kwargs["env"]
