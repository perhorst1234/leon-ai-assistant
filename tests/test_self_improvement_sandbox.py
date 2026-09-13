import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from leon_control_plane import self_improvement_sandbox
from leon_control_plane.self_improvement_sandbox import SandboxRequest, execute_review_only


class FakeStore:
    def __init__(self, approval):
        self.approval = approval
        self.recorded = []

    def initialize(self):
        pass

    def connect(self):
        outer = self

        class Connection:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                pass

            def execute(self, _sql, _args):
                class Result:
                    def fetchone(self):
                        return outer.approval

                return Result()

        return Connection()

    def consume_approval(self, approval_id, **_kwargs):
        assert approval_id == self.approval["id"]
        if self.approval["status"] != "approved":
            raise ValueError("Only approved approvals can be consumed")
        self.approval["status"] = "consumed"
        self.approval["consumed_at"] = "now"

    def record_code_change_rollback(self, **kwargs):
        self.recorded.append(kwargs)


def _repo(tmp_path: Path):
    root = tmp_path / "allowed"
    repo = root / "repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "value.py").write_text("VALUE = 'before'\n")
    subprocess.run(["git", "add", "value.py"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "base"],
        cwd=repo, check=True,
    )
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    patch = (
        "diff --git a/value.py b/value.py\n--- a/value.py\n+++ b/value.py\n"
        "@@ -1 +1 @@\n-VALUE = 'before'\n+VALUE = 'after'\n"
    )
    return root, repo, base, patch


def _request(root: Path, repo: Path, base: str, patch: str, **changes):
    digest = hashlib.sha256(patch.encode()).hexdigest()
    binding = {
        "workspace_root": str(repo.resolve()),
        "allowed_temp_root": str(root.resolve()),
        "base_commit": base,
        "patch_digest": digest,
        "allowed_files": ["value.py"],
        "validation_profile": "python_syntax",
    }
    approval = {
        "id": "approval-1", "status": "approved",
        "action_type": "apply_controlled_self_improvement",
        "expected_change": json.dumps(binding), "expires_at": None, "consumed_at": None,
    }
    store = FakeStore(approval)
    request = SandboxRequest(repo, root, base, patch, digest, ("value.py",), "python_syntax", "approval-1", store)
    if changes:
        request = request.__class__(**{**request.__dict__, **changes})
    return request, store


def test_success_stays_review_only_and_never_executes_changed_code(tmp_path):
    root, repo, base, patch = _repo(tmp_path)
    request, store = _request(root, repo, base, patch)
    result = execute_review_only(request)
    assert result["status"] == "review_required"
    assert result["changed_code_executed"] is False
    assert (repo / "value.py").read_text() == "VALUE = 'after'\n"
    assert store.approval["status"] == "consumed"
    assert store.recorded[0]["test_results"]["changed_code_executed"] is False


def test_invalid_python_rolls_back(tmp_path):
    root, repo, base, patch = _repo(tmp_path)
    bad = patch.replace("VALUE = 'after'", "def broken(")
    request, _store = _request(root, repo, base, bad)
    result = execute_review_only(request)
    assert result["status"] == "failed" and result["rolled_back"] is True
    assert (repo / "value.py").read_text() == "VALUE = 'before'\n"


def test_binding_digest_and_consumed_approval_fail_closed(tmp_path):
    root, repo, base, patch = _repo(tmp_path)
    request, _store = _request(root, repo, base, patch)
    with pytest.raises(ValueError, match="digest"):
        execute_review_only(request.__class__(**{**request.__dict__, "patch_digest": "0" * 64}))
    request, store = _request(root, repo, base, patch)
    store.approval["expected_change"] = "{}"
    with pytest.raises(ValueError, match="binding"):
        execute_review_only(request)
    request, store = _request(root, repo, base, patch)
    store.approval["status"] = "consumed"
    store.approval["consumed_at"] = "now"
    with pytest.raises(ValueError, match="unconsumed"):
        execute_review_only(request)


def test_paths_symlinks_hidden_files_and_outside_write_are_rejected(tmp_path):
    root, repo, base, patch = _repo(tmp_path)
    request, _store = _request(root, repo, base, patch)
    with pytest.raises(ValueError, match="normalized"):
        execute_review_only(request.__class__(**{**request.__dict__, "allowed_files": ("../outside.py",)}))

    hidden = patch.replace("value.py", ".git/config")
    request, _store = _request(root, repo, base, hidden, allowed_files=(".git/config",))
    with pytest.raises(ValueError, match="normalized"):
        execute_review_only(request)

    outside = root / "outside.py"
    outside.write_text("SAFE = True\n")
    (repo / "link.py").symlink_to(outside)
    subprocess.run(["git", "add", "link.py"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "link"],
        cwd=repo, check=True,
    )
    link_base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    link_patch = "diff --git a/link.py b/link.py\n--- a/link.py\n+++ b/link.py\n@@ -1 +1 @@\n-SAFE = True\n+SAFE = False\n"
    request, _store = _request(root, repo, link_base, link_patch, allowed_files=("link.py",))
    with pytest.raises(ValueError, match="regular file"):
        execute_review_only(request)
    assert outside.read_text() == "SAFE = True\n"


def test_non_temp_workspace_and_secret_patch_are_rejected(tmp_path):
    root, repo, base, patch = _repo(tmp_path)
    request, _store = _request(root, repo, base, patch, allowed_temp_root=Path("/"))
    with pytest.raises(ValueError, match="temporary"):
        execute_review_only(request)
    fake_secret = "sk-" + "test-" + "abcdefghijklmnop"
    secret_patch = patch.replace("VALUE = 'after'", f"VALUE = '{fake_secret}'")
    request, _store = _request(root, repo, base, secret_patch)
    with pytest.raises(ValueError, match="secret-like"):
        execute_review_only(request)


def test_mode_changes_and_unapproved_extra_files_are_rejected(tmp_path):
    root, repo, base, patch = _repo(tmp_path)
    mode_patch = patch.replace("--- a/value.py", "old mode 100644\nnew mode 100755\n--- a/value.py")
    request, _store = _request(root, repo, base, mode_patch)
    with pytest.raises(ValueError, match="forbidden"):
        execute_review_only(request)

    extra = (
        patch
        + "diff --git a/other.py b/other.py\n--- a/other.py\n+++ b/other.py\n"
        + "@@ -1 +1 @@\n-OLD = True\n+OLD = False\n"
    )
    request, _store = _request(root, repo, base, extra)
    with pytest.raises(ValueError, match="outside allowlist"):
        execute_review_only(request)


def test_git_clean_filter_cannot_execute_changed_code(tmp_path):
    root, repo, _base, patch = _repo(tmp_path)
    (repo / ".gitattributes").write_text("value.py filter=owned\n")
    subprocess.run(["git", "add", ".gitattributes"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "attributes"],
        cwd=repo, check=True,
    )
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    marker = root / "executed"
    subprocess.run(
        ["git", "config", "--local", "filter.owned.clean", f"sh -c 'touch {marker}; cat'"],
        cwd=repo, check=True,
    )
    request, _store = _request(root, repo, base, patch)
    with pytest.raises(ValueError, match="forbidden"):
        execute_review_only(request)
    assert not marker.exists()


def test_safe_syntax_read_holds_parent_directory_during_swap(tmp_path, monkeypatch):
    root = tmp_path / "root"
    nested = root / "nested"
    nested.mkdir(parents=True)
    (nested / "value.py").write_text("SAFE = True\n")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "value.py").write_text("SAFE = False\n")
    real_open = self_improvement_sandbox.os.open
    swapped = False

    def swapping_open(path, flags, *args, **kwargs):
        nonlocal swapped
        fd = real_open(path, flags, *args, **kwargs)
        if path == "nested" and not swapped:
            nested.replace(root / "original")
            nested.symlink_to(outside, target_is_directory=True)
            swapped = True
        return fd

    monkeypatch.setattr(self_improvement_sandbox.os, "open", swapping_open)
    assert self_improvement_sandbox._safe_read_relative(root, "nested/value.py", 1024) == b"SAFE = True\n"
