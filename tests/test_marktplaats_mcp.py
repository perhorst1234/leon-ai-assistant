import pytest

from leon_control_plane import marktplaats_mcp


def test_lock_pins_audited_artifact_and_every_requirement_has_hashes():
    lock = marktplaats_mcp.LOCK.read_text()
    assert "marktplaats-mcp==0.1.1" in lock
    assert "429eb3393bad0e7b8200cb946548a00a7f5e6e77454e49683c219bb2b2d3d0a7" in lock
    lines = lock.splitlines()
    requirement_indexes = [index for index, line in enumerate(lines) if line and not line[0].isspace() and "==" in line]
    assert requirement_indexes
    boundaries = requirement_indexes[1:] + [len(lines)]
    assert all(
        any("--hash=sha256:" in line for line in lines[start:end])
        for start, end in zip(requirement_indexes, boundaries, strict=True)
    )


def test_target_must_stay_in_repo_and_avoid_symlink_parent(tmp_path, monkeypatch):
    monkeypatch.setattr(marktplaats_mcp, "ROOT", tmp_path)
    marktplaats_mcp._assert_private_local_target(tmp_path / ".runtime" / "mcp" / "safe")
    with pytest.raises(ValueError, match="inside repository"):
        marktplaats_mcp._assert_private_local_target(tmp_path.parent / "outside")

    (tmp_path / ".runtime").symlink_to(tmp_path.parent)
    with pytest.raises(ValueError, match="symlink"):
        marktplaats_mcp._assert_private_local_target(tmp_path / ".runtime" / "mcp" / "unsafe")


def test_static_verification_never_starts_third_party_runtime(tmp_path, monkeypatch):
    target = tmp_path / ".runtime" / "mcp" / "marktplaats-0.1.1"
    site = target / "lib" / "python3.13" / "site-packages" / "marktplaats_mcp-0.1.1.dist-info"
    site.mkdir(parents=True)
    (site / "METADATA").write_text("Metadata-Version: 2.1\nName: marktplaats-mcp\nVersion: 0.1.1\n")
    executable = target / "bin" / "marktplaats-mcp"
    executable.parent.mkdir()
    executable.write_text("must not run\n")
    monkeypatch.setattr(marktplaats_mcp, "ROOT", tmp_path)
    monkeypatch.setattr(marktplaats_mcp, "_server_in", lambda _target: executable)
    marktplaats_mcp._write_manifest(target)

    result = marktplaats_mcp.verify_installation(target)

    assert result["installed"] is True
    assert result["sandbox_attested"] is False
    assert result["enabled"] is False

    executable.write_text("tampered\n")
    with pytest.raises(RuntimeError, match="integrity check failed"):
        marktplaats_mcp.verify_installation(target)
