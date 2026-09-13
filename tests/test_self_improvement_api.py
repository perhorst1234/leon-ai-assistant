import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from leon_control_plane import server
from leon_control_plane import self_improvement_api
from leon_control_plane.self_improvement_api import approve_self_improvement, preview_self_improvement, run_self_improvement
from leon_control_plane.store import ControlPlaneStore


def _store(tmp_path: Path) -> ControlPlaneStore:
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps({"metadata": {}, "tasks": [], "approvals": []}))
    return ControlPlaneStore(tmp_path / "state.sqlite", seed)


def _source(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "source"
    root.mkdir()
    (root / "value.py").write_text("VALUE = 'before'\n")
    patch = "diff --git a/value.py b/value.py\n--- a/value.py\n+++ b/value.py\n@@ -1 +1 @@\n-VALUE = 'before'\n+VALUE = 'after'\n"
    return root, patch


def test_two_step_exact_approval_is_review_only_and_one_use(tmp_path):
    store = _store(tmp_path)
    root, patch = _source(tmp_path)
    preview = preview_self_improvement(store, {
        "patch": patch, "allowed_files": ["value.py"], "validation_profile": "python_syntax",
    }, repo_root=root)
    with pytest.raises(ValueError, match="approved"):
        run_self_improvement(store, {"approval_id": preview["approval_id"], "patch": patch})
    store.update_approval(preview["approval_id"], "approved", "Reviewed exact bounded change")
    result = run_self_improvement(store, {"approval_id": preview["approval_id"], "patch": patch})
    assert result["status"] == "review_required"
    assert result["changed_code_executed"] is False
    assert result["rollback"]["performed"] is False
    assert result["temporary_repository_deleted"] is True
    assert "workspace" not in json.dumps(result) and patch not in json.dumps(result)
    assert (root / "value.py").read_text() == "VALUE = 'before'\n"
    with pytest.raises(ValueError, match="unconsumed"):
        run_self_improvement(store, {"approval_id": preview["approval_id"], "patch": patch})
    state = store.get_state()
    assert any(item["action_ref_id"] == preview["approval_id"] for item in state["rollback_registry"])
    serialized = json.dumps(state)
    assert patch not in serialized and "leon-self-review-owned" not in serialized


def test_concurrent_run_has_exactly_one_claimant(tmp_path):
    store = _store(tmp_path)
    root, patch = _source(tmp_path)
    preview = preview_self_improvement(store, {
        "patch": patch, "allowed_files": ["value.py"], "validation_profile": "python_syntax",
    }, repo_root=root)
    store.update_approval(preview["approval_id"], "approved", "Reviewed")
    barrier = threading.Barrier(2)
    outcomes = []

    def run():
        barrier.wait()
        try:
            outcomes.append(run_self_improvement(store, {"approval_id": preview["approval_id"], "patch": patch})["status"])
        except ValueError as exc:
            outcomes.append(type(exc).__name__)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(outcomes) == ["ValueError", "review_required"]


def test_specialized_approval_accepts_only_live_self_improvement_preview(tmp_path):
    store = _store(tmp_path)
    root, patch = _source(tmp_path)
    preview = preview_self_improvement(store, {
        "patch": patch, "allowed_files": ["value.py"], "validation_profile": "python_syntax",
    }, repo_root=root)
    approved = approve_self_improvement(store, {"approval_id": preview["approval_id"]})
    assert approved["status"] == "approved"
    assert approved["patch_digest"] == preview["patch_digest"]
    assert approved["changed_code_executed"] is False
    assert approve_self_improvement(store, {"approval_id": preview["approval_id"]}) == approved
    foreign_id = store.create_approval(
        task_id=None, action_type="read_only_analysis", summary="Unrelated approval",
        reason="Test separate approval boundary", risk_level="low",
    )
    with pytest.raises(ValueError, match="not a self-improvement"):
        approve_self_improvement(store, {"approval_id": foreign_id})
    with pytest.raises(ValueError, match="only approval_id"):
        approve_self_improvement(store, {"approval_id": preview["approval_id"], "choice": "approved"})


def test_specialized_approval_cannot_resurrect_concurrent_rejection(tmp_path, monkeypatch):
    store = _store(tmp_path)
    root, patch = _source(tmp_path)
    preview = preview_self_improvement(store, {
        "patch": patch, "allowed_files": ["value.py"], "validation_profile": "python_syntax",
    }, repo_root=root)
    original = store.approve_pending_approval

    def reject_then_approve(approval_id, note, **kwargs):
        store.update_approval(approval_id, "rejected", "Concurrent rejection wins")
        return original(approval_id, note, **kwargs)

    monkeypatch.setattr(store, "approve_pending_approval", reject_then_approve)
    with pytest.raises(ValueError, match="no longer pending"):
        approve_self_improvement(store, {"approval_id": preview["approval_id"]})
    state = store.get_state()
    record = next(item for item in state["approvals"] if item["id"] == preview["approval_id"])
    assert record["status"] == "rejected"


def test_sweep_only_deletes_old_strictly_marked_owned_directories(tmp_path, monkeypatch):
    parent = tmp_path / "owned"
    monkeypatch.setattr(self_improvement_api, "_TEMP_PARENT", parent)
    old = parent / "request-old"
    old.mkdir(parents=True)
    parent.chmod(0o700)
    (old / self_improvement_api._OWNER_MARKER).write_text("leon-self-review-v1\n")
    unmarked = parent / "request-unmarked"
    unmarked.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = parent / "request-link"
    link.symlink_to(outside, target_is_directory=True)
    stale = time.time() - self_improvement_api._TEMP_TTL_SECONDS - 1
    import os
    os.utime(old, (stale, stale))
    os.utime(unmarked, (stale, stale))
    assert self_improvement_api.sweep_abandoned_temp_repositories() == 1
    assert not old.exists() and unmarked.exists() and link.exists() and outside.exists()


def test_temp_parent_must_be_private_owned_directory_not_symlink(tmp_path, monkeypatch):
    outside = tmp_path / "outside"
    outside.mkdir()
    parent = tmp_path / "owned-link"
    parent.symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(self_improvement_api, "_TEMP_PARENT", parent)
    with pytest.raises(ValueError, match="private and server-owned"):
        self_improvement_api.sweep_abandoned_temp_repositories()
    assert list(outside.iterdir()) == []


def test_cleanup_does_not_delete_directory_swapped_after_open(tmp_path, monkeypatch):
    parent = tmp_path / "owned"
    parent.mkdir(mode=0o700)
    root = parent / "request-original"
    root.mkdir(mode=0o700)
    (root / self_improvement_api._OWNER_MARKER).write_text("leon-self-review-v1\n")
    (root / "payload").write_text("original")
    real_clear = self_improvement_api._clear_directory_fd
    swapped = False

    def swap_then_clear(directory_fd):
        nonlocal swapped
        if not swapped:
            root.rename(parent / "request-renamed")
            root.mkdir(mode=0o700)
            (root / self_improvement_api._OWNER_MARKER).write_text("leon-self-review-v1\n")
            (root / "payload").write_text("replacement")
            swapped = True
        real_clear(directory_fd)

    monkeypatch.setattr(self_improvement_api, "_TEMP_PARENT", parent)
    monkeypatch.setattr(self_improvement_api, "_clear_directory_fd", swap_then_clear)
    assert self_improvement_api._delete_owned_root(root) is False
    assert (root / "payload").read_text() == "replacement"


def test_preview_rejects_paths_symlinks_new_files_secrets_and_bad_inputs(tmp_path):
    store = _store(tmp_path)
    root, patch = _source(tmp_path)
    outside = tmp_path / "outside.py"
    outside.write_text("SAFE = True\n")
    (root / "link.py").symlink_to(outside)
    cases = [
        {"patch": patch, "allowed_files": ["../value.py"], "validation_profile": "python_syntax"},
        {"patch": patch.replace("value.py", "link.py"), "allowed_files": ["link.py"], "validation_profile": "python_syntax"},
        {"patch": patch.replace("value.py", "new.py").replace("--- a/new.py", "--- /dev/null"), "allowed_files": ["new.py"], "validation_profile": "python_syntax"},
        {"patch": patch.replace("after", "sk-test-abcdefghijklmnop"), "allowed_files": ["value.py"], "validation_profile": "python_syntax"},
        {"patch": "x" * (512 * 1024 + 1), "allowed_files": ["value.py"], "validation_profile": "python_syntax"},
    ]
    for body in cases:
        with pytest.raises(ValueError):
            preview_self_improvement(store, body, repo_root=root)
    with pytest.raises(ValueError, match="only"):
        preview_self_improvement(store, {"patch": patch, "allowed_files": ["value.py"], "validation_profile": "python_syntax", "workspace_root": "/tmp/x"}, repo_root=root)


def test_patch_mismatch_rejected(tmp_path):
    store = _store(tmp_path)
    root, patch = _source(tmp_path)
    preview = preview_self_improvement(store, {"patch": patch, "allowed_files": ["value.py"], "validation_profile": "python_syntax"}, repo_root=root)
    store.update_approval(preview["approval_id"], "approved", "Reviewed")
    with pytest.raises(ValueError, match="digest"):
        run_self_improvement(store, {"approval_id": preview["approval_id"], "patch": patch + "\n"})


def test_source_file_swap_after_validation_is_rejected(tmp_path, monkeypatch):
    store = _store(tmp_path)
    root, patch = _source(tmp_path)
    original = self_improvement_api._create_clean_repo

    def swapped(repo_root, allowed, identities):
        replacement = repo_root / "replacement.py"
        replacement.write_text("VALUE = 'attacker'\n")
        (repo_root / "value.py").replace(repo_root / "old.py")
        replacement.replace(repo_root / "value.py")
        return original(repo_root, allowed, identities)

    monkeypatch.setattr(self_improvement_api, "_create_clean_repo", swapped)
    with pytest.raises(ValueError, match="changed after validation"):
        preview_self_improvement(store, {
            "patch": patch, "allowed_files": ["value.py"], "validation_profile": "python_syntax",
        }, repo_root=root)


def test_destination_writer_rejects_file_and_parent_symlinks(tmp_path):
    root = tmp_path / "destination"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_file = outside / "value.py"
    outside_file.write_text("unchanged")
    (root / "value.py").symlink_to(outside_file)
    with pytest.raises(ValueError, match="symlink"):
        self_improvement_api._safe_write_relative(root, "value.py", b"changed")
    (root / "value.py").unlink()
    (root / "nested").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        self_improvement_api._safe_write_relative(root, "nested/value.py", b"changed")
    assert outside_file.read_text() == "unchanged"


def test_http_requires_exact_bearer(tmp_path, monkeypatch):
    store = _store(tmp_path)
    root, patch = _source(tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "REPO_ROOT", root)
    monkeypatch.setattr(server, "dashboard_token", lambda: "secret")
    http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{http.server_address[1]}/api/self-improvement/preview"
        data = json.dumps({"patch": patch, "allowed_files": ["value.py"], "validation_profile": "python_syntax"}).encode()
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(urllib.request.Request(url, data=data, method="POST"))
        assert exc.value.code == 401
        request = urllib.request.Request(url, data=data, method="POST", headers={"Authorization": "Bearer secret", "Content-Type": "application/json"})
        with urllib.request.urlopen(request) as response:
            assert response.status == 201
            preview = json.loads(response.read())
        approve_url = f"http://127.0.0.1:{http.server_address[1]}/api/self-improvement/approve"
        approve_data = json.dumps({"approval_id": preview["approval_id"]}).encode()
        approve_request = urllib.request.Request(
            approve_url, data=approve_data, method="POST",
            headers={"Authorization": "Bearer secret", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(approve_request) as response:
            assert response.status == 200
            assert json.loads(response.read())["status"] == "approved"
        run_url = f"http://127.0.0.1:{http.server_address[1]}/api/self-improvement/run"
        run_data = json.dumps({"approval_id": preview["approval_id"], "patch": patch}).encode()
        run_request = urllib.request.Request(
            run_url, data=run_data, method="POST",
            headers={"Authorization": "Bearer secret", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(run_request) as response:
            assert response.status == 200
            result = json.loads(response.read())
        assert result["status"] == "review_required"
        assert result["changed_code_executed"] is False
        assert result["temporary_repository_deleted"] is True
    finally:
        http.shutdown()
        thread.join()
