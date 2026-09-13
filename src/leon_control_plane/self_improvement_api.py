"""Authenticated API service for approval-gated, review-only code patches."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

from leon_control_plane.secret_scanner import assert_no_secrets
from leon_control_plane.self_improvement_sandbox import (
    MAX_FILE_BYTES,
    MAX_PATCH_BYTES,
    VALIDATION_PROFILES,
    SandboxRequest,
    _relative_path,
    _validate_patch,
    execute_review_only,
)

_TEMP_PARENT = Path(tempfile.gettempdir()) / "leon-self-review-owned"
_OWNER_MARKER = ".leon-self-review-owner"
_TEMP_TTL_SECONDS = 60 * 60
_OWNED_TEMP_ROOTS: dict[str, tuple[Path, Path]] = {}
_OWNERS_LOCK = threading.Lock()
_REQUEST_KEYS = {"patch", "allowed_files", "validation_profile"}
_RUN_KEYS = {"approval_id", "patch"}


def _git(cwd: Path, args: Sequence[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": os.defpath,
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_ATTR_NOSYSTEM": "1",
    }
    return subprocess.run(
        [
            "git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
            "-c", f"core.attributesFile={os.devnull}", *args,
        ],
        cwd=cwd, env=env, shell=False, text=True, capture_output=True,
        timeout=10, check=False, input=input_text,
    )


def _require_ok(result: subprocess.CompletedProcess[str], message: str) -> None:
    if result.returncode != 0:
        raise ValueError(message)


def _normalize_preview(
    body: dict[str, Any], repo_root: Path,
) -> tuple[str, tuple[str, ...], str, dict[str, tuple[int, int]]]:
    if set(body) != _REQUEST_KEYS:
        raise ValueError("preview accepts only patch, allowed_files and validation_profile")
    patch = body.get("patch")
    files = body.get("allowed_files")
    profile = body.get("validation_profile")
    if not isinstance(patch, str) or not isinstance(files, list) or not all(isinstance(item, str) for item in files):
        raise ValueError("patch and allowed_files have invalid types")
    if len(patch.encode("utf-8")) > MAX_PATCH_BYTES:
        raise ValueError("patch exceeds size cap")
    assert_no_secrets("self-improvement patch", patch)
    allowed = tuple(sorted({_relative_path(item) for item in files}))
    if not allowed or list(allowed) != files:
        raise ValueError("allowed_files must be non-empty, unique, normalized and sorted")
    if profile not in VALIDATION_PROFILES:
        raise ValueError("validation profile is not allowlisted")
    if profile == "python_syntax" and any(not item.endswith(".py") for item in allowed):
        raise ValueError("python_syntax accepts only Python files")
    root = repo_root.resolve()
    identities: dict[str, tuple[int, int]] = {}
    for name in allowed:
        source = root / name
        if not source.exists() or not source.is_file() or source.is_symlink():
            raise ValueError("allowed file must be an existing regular file")
        if root not in source.resolve().parents:
            raise ValueError("allowed file escapes repository")
        parent = source.parent
        while parent != root:
            if parent.is_symlink():
                raise ValueError("symlink parent is forbidden")
            parent = parent.parent
        source_info = source.stat()
        if source_info.st_size > MAX_FILE_BYTES:
            raise ValueError("allowed file exceeds size cap")
        identities[name] = (source_info.st_dev, source_info.st_ino)
    return patch, allowed, profile, identities


def _safe_source_bytes(root: Path, name: str, expected: tuple[int, int]) -> bytes:
    from leon_control_plane.self_improvement_sandbox import _safe_read_relative
    return _safe_read_relative(root, name, MAX_FILE_BYTES, expected=expected)


def _safe_write_relative(
    root: Path, name: str, data: bytes, *, expected_root: tuple[int, int] | None = None,
) -> None:
    """Create a new file through pinned directories without following links."""
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    fds: list[int] = []
    file_fd: int | None = None
    try:
        current = os.open(root, directory_flags)
        fds.append(current)
        opened_root = os.fstat(current)
        if expected_root is not None and (opened_root.st_dev, opened_root.st_ino) != expected_root:
            raise ValueError("review destination changed during initialization")
        parts = Path(_relative_path(name)).parts
        for part in parts[:-1]:
            try:
                os.mkdir(part, mode=0o700, dir_fd=current)
            except FileExistsError:
                pass
            current = os.open(part, directory_flags, dir_fd=current)
            fds.append(current)
        file_fd = os.open(
            parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
            0o600, dir_fd=current,
        )
        view = memoryview(data)
        while view:
            written = os.write(file_fd, view)
            if written <= 0:
                raise ValueError("unable to write review source file")
            view = view[written:]
    except OSError as exc:
        raise ValueError("review destination changed or contains a symlink") from exc
    finally:
        if file_fd is not None:
            os.close(file_fd)
        for fd in reversed(fds):
            os.close(fd)


def _ensure_temp_parent() -> Path:
    """Create or validate private parent without accepting a pre-created symlink."""
    try:
        _TEMP_PARENT.mkdir(mode=0o700, parents=False)
    except FileExistsError:
        pass
    info = _TEMP_PARENT.lstat()
    resolved = _TEMP_PARENT.resolve(strict=True)
    expected_parent = _TEMP_PARENT.parent.resolve(strict=True)
    if (
        not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
        or resolved.parent != expected_parent
        or hasattr(os, "getuid") and info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) & 0o077
    ):
        raise ValueError("self-improvement temporary parent is not private and server-owned")
    return resolved


def _clear_directory_fd(directory_fd: int) -> None:
    """Remove contents through pinned descriptors; never follow a replaced path."""
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    for entry in os.scandir(directory_fd):
        info = entry.stat(follow_symlinks=False)
        if stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode):
            child_fd = os.open(entry.name, directory_flags, dir_fd=directory_fd)
            try:
                opened = os.fstat(child_fd)
                if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                    raise ValueError("temporary directory changed during cleanup")
                _clear_directory_fd(child_fd)
            finally:
                os.close(child_fd)
            current = os.stat(entry.name, dir_fd=directory_fd, follow_symlinks=False)
            if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
                raise ValueError("temporary directory changed during cleanup")
            os.rmdir(entry.name, dir_fd=directory_fd)
        else:
            os.unlink(entry.name, dir_fd=directory_fd)


def _delete_owned_root(path: Path) -> bool:
    parent_fd = root_fd = marker_fd = None
    try:
        parent = _ensure_temp_parent()
        if path.parent != parent or not path.name.startswith("request-") or path.is_symlink():
            return False
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        parent_fd = os.open(parent, directory_flags)
        root_fd = os.open(path.name, directory_flags, dir_fd=parent_fd)
        root_info = os.fstat(root_fd)
        marker_fd = os.open(_OWNER_MARKER, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=root_fd)
        marker_info = os.fstat(marker_fd)
        if not stat.S_ISREG(marker_info.st_mode) or os.read(marker_fd, 64) != b"leon-self-review-v1\n":
            return False
        _clear_directory_fd(root_fd)
        current = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
        if (current.st_dev, current.st_ino) != (root_info.st_dev, root_info.st_ino):
            return False
        os.rmdir(path.name, dir_fd=parent_fd)
        return True
    except (FileNotFoundError, OSError, ValueError):
        return False
    finally:
        for fd in (marker_fd, root_fd, parent_fd):
            if fd is not None:
                os.close(fd)


def sweep_abandoned_temp_repositories(*, now: float | None = None) -> int:
    """Delete marked, non-symlink orphan repositories older than the bounded TTL."""
    now = time.time() if now is None else now
    parent = _ensure_temp_parent()
    removed = 0
    for entry in list(parent.iterdir())[:1024]:
        try:
            info = entry.lstat()
            if entry.name.startswith("request-") and stat.S_ISDIR(info.st_mode) and not entry.is_symlink() and now - info.st_mtime >= _TEMP_TTL_SECONDS:
                removed += int(_delete_owned_root(entry))
        except OSError:
            continue
    return removed


def _create_clean_repo(
    repo_root: Path, allowed: tuple[str, ...], identities: dict[str, tuple[int, int]],
) -> tuple[Path, Path, str]:
    sweep_abandoned_temp_repositories()
    parent = _ensure_temp_parent()
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    parent_fd = os.open(parent, directory_flags)
    root_fd: int | None = None
    workspace_fd: int | None = None
    marker_fd: int | None = None
    request_name: str | None = None
    root_identity: tuple[int, int] | None = None
    workspace_identity: tuple[int, int] | None = None
    try:
        for _attempt in range(16):
            request_name = f"request-{os.urandom(18).hex()}"
            try:
                os.mkdir(request_name, mode=0o700, dir_fd=parent_fd)
                break
            except FileExistsError:
                continue
        else:
            raise ValueError("unable to allocate unique review repository")
        root_fd = os.open(request_name, directory_flags, dir_fd=parent_fd)
        root_info = os.fstat(root_fd)
        root_identity = (root_info.st_dev, root_info.st_ino)
        current_root = os.stat(request_name, dir_fd=parent_fd, follow_symlinks=False)
        if (current_root.st_dev, current_root.st_ino) != root_identity:
            raise ValueError("self-improvement temporary repository changed during allocation")
        marker_fd = os.open(
            _OWNER_MARKER,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
            0o600,
            dir_fd=root_fd,
        )
        marker = memoryview(b"leon-self-review-v1\n")
        while marker:
            written = os.write(marker_fd, marker)
            if written <= 0:
                raise ValueError("unable to initialize temporary repository marker")
            marker = marker[written:]
        os.close(marker_fd)
        marker_fd = None
        os.mkdir("workspace", mode=0o700, dir_fd=root_fd)
        workspace_fd = os.open("workspace", directory_flags, dir_fd=root_fd)
        workspace_info = os.fstat(workspace_fd)
        workspace_identity = (workspace_info.st_dev, workspace_info.st_ino)
        current_workspace = os.stat("workspace", dir_fd=root_fd, follow_symlinks=False)
        if (current_workspace.st_dev, current_workspace.st_ino) != workspace_identity:
            raise ValueError("self-improvement workspace changed during allocation")
        current_parent = os.stat(parent)
        opened_parent = os.fstat(parent_fd)
        if (current_parent.st_dev, current_parent.st_ino) != (opened_parent.st_dev, opened_parent.st_ino):
            raise ValueError("self-improvement temporary parent changed during allocation")
    except Exception:
        if root_fd is not None:
            try:
                _clear_directory_fd(root_fd)
                if request_name is not None and root_identity is not None:
                    current_root = os.stat(request_name, dir_fd=parent_fd, follow_symlinks=False)
                    if (current_root.st_dev, current_root.st_ino) == root_identity:
                        os.rmdir(request_name, dir_fd=parent_fd)
            except (FileNotFoundError, OSError, ValueError):
                pass
        raise
    finally:
        for fd in (marker_fd, workspace_fd, root_fd):
            if fd is not None:
                os.close(fd)
        os.close(parent_fd)
    assert request_name is not None and workspace_identity is not None
    temp_root = parent / request_name
    workspace = temp_root / "workspace"
    try:
        for name in allowed:
            _safe_write_relative(
                workspace, name,
                _safe_source_bytes(repo_root.resolve(), name, identities[name]),
                expected_root=workspace_identity,
            )
        _require_ok(_git(workspace, ["init", "--quiet"]), "unable to initialize review repository")
        _require_ok(_git(workspace, ["add", "--", *allowed]), "unable to stage review files")
        _require_ok(_git(workspace, [
            "-c", "user.name=Leon Review", "-c", "user.email=review@localhost",
            "commit", "--quiet", "--no-gpg-sign", "-m", "review base",
        ]), "unable to create review base")
        head = _git(workspace, ["rev-parse", "HEAD"])
        _require_ok(head, "unable to read review base")
    except Exception:
        _delete_owned_root(temp_root)
        raise
    return temp_root, workspace, head.stdout.strip()


def preview_self_improvement(store: Any, body: dict[str, Any], *, repo_root: Path) -> dict[str, Any]:
    patch, allowed, profile, identities = _normalize_preview(body, repo_root)
    temp_root, workspace, base_commit = _create_clean_repo(repo_root, allowed, identities)
    digest = hashlib.sha256(patch.encode("utf-8")).hexdigest()
    repository_id = os.urandom(24).hex()
    preflight = SandboxRequest(workspace, temp_root, base_commit, patch, digest, allowed, profile, "", store)
    try:
        _validate_patch(preflight, workspace)
        _require_ok(
            _git(workspace, ["apply", "--check", "--whitespace=error-all", "-"], input_text=patch),
            "patch does not apply cleanly",
        )
        approval_id = store.create_approval(
            task_id=None,
            action_type="apply_controlled_self_improvement",
            summary="Review bounded self-improvement patch",
            reason="A static review of a proposed code patch requires explicit approval.",
            affected_systems="temporary review repository",
            permissions="read allowlisted source files; write temporary repository only",
            external_effect="No production mutation and no changed-code execution.",
            risk_level="high",
            risk_class="R3",
            expected_change=json.dumps({
                "repository_id": repository_id, "base_commit": base_commit, "patch_digest": digest,
                "allowed_files": list(allowed), "validation_profile": profile,
            }, sort_keys=True),
            rollback_plan="Discard the server-owned temporary repository.",
            failure_mode="Stop, preserve production files, and return bounded review evidence.",
            expires_at=(datetime.now(timezone.utc) + timedelta(seconds=_TEMP_TTL_SECONDS)).isoformat(),
            requested_by="self-improvement-api",
            actor_id="self-improvement-api",
        )
    except Exception:
        _delete_owned_root(temp_root)
        raise
    with _OWNERS_LOCK:
        _OWNED_TEMP_ROOTS[repository_id] = (temp_root, workspace)
    return {
        "status": "pending_approval",
        "approval_id": approval_id,
        "patch_digest": digest,
        "allowed_files": list(allowed),
        "validation_profile": profile,
        "changed_code_executed": False,
        "restart_behavior": "temporary repository is discarded after the bounded TTL and cannot be resumed",
    }


def _approval_binding(store: Any, approval_id: str) -> dict[str, Any]:
    store.initialize()
    with store.connect() as conn:
        row = conn.execute(
            "SELECT status, consumed_at, expires_at, expected_change FROM approvals WHERE id = ?", (approval_id,),
        ).fetchone()
    if row is None:
        raise ValueError("unknown approval id")
    if row["status"] != "approved" or row["consumed_at"]:
        raise ValueError("approval must be approved, unconsumed and unexpired")
    if row["expires_at"]:
        try:
            expiry = datetime.fromisoformat(str(row["expires_at"]).replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("approval expiry is invalid") from None
        if expiry.astimezone(timezone.utc) <= datetime.now(timezone.utc):
            raise ValueError("approval must be approved, unconsumed and unexpired")
    try:
        binding = json.loads(row["expected_change"])
    except (TypeError, json.JSONDecodeError):
        raise ValueError("approval lacks exact sandbox binding") from None
    if not isinstance(binding, dict) or set(binding) != {
        "repository_id", "base_commit", "patch_digest", "allowed_files", "validation_profile",
    }:
        raise ValueError("approval lacks exact sandbox binding")
    return binding


def run_self_improvement(store: Any, body: dict[str, Any]) -> dict[str, Any]:
    if set(body) != _RUN_KEYS or not isinstance(body.get("approval_id"), str) or not isinstance(body.get("patch"), str):
        raise ValueError("run accepts only approval_id and patch")
    approval_id = body["approval_id"]
    patch = body["patch"]
    if len(patch.encode("utf-8")) > MAX_PATCH_BYTES:
        raise ValueError("patch exceeds size cap")
    binding = _approval_binding(store, approval_id)
    digest = hashlib.sha256(patch.encode("utf-8")).hexdigest()
    if digest != binding["patch_digest"]:
        raise ValueError("patch digest mismatch")
    repository_id = str(binding["repository_id"])
    with _OWNERS_LOCK:
        owned = _OWNED_TEMP_ROOTS.pop(repository_id, None)
    if owned is None:
        raise ValueError("approval temporary repository is not server-owned")
    temp_root, workspace = owned
    request = SandboxRequest(
        workspace, temp_root, str(binding["base_commit"]), patch, digest,
        tuple(binding["allowed_files"]), str(binding["validation_profile"]), approval_id, store, False, binding,
    )
    try:
        result = execute_review_only(request)
    except Exception:
        try:
            store.update_approval(
                approval_id, "expired",
                "Temporary review repository became unavailable before validation completed.",
                actor_type="system", actor_id="self-improvement-api",
            )
        except ValueError:
            pass
        raise
    finally:
        deleted = _delete_owned_root(temp_root)
    validation = dict(result.get("validation") or {})
    response = {
        "status": result.get("status", "failed"),
        "patch_digest": digest,
        "allowed_files": list(result.get("allowed_files") or binding["allowed_files"]),
        "validation": {
            "profile": validation.get("profile", binding["validation_profile"]),
            "passed": bool(validation.get("passed")),
            "error": str(validation.get("error") or "")[:4096],
        },
        "diff": {
            "passed": bool(validation.get("passed")),
            "after_hash": result.get("after_hash", ""),
        },
        "rollback": {
            "performed": bool(result.get("rolled_back")),
            "error": str(result.get("rollback_error") or "")[:4096],
        },
        "temporary_repository_deleted": deleted,
        "changed_code_executed": False,
    }
    if result.get("phase"):
        response["validation"]["phase"] = str(result["phase"])
    return response


def self_improvement_request(store: Any, *, path: str, body: dict[str, Any], repo_root: Path) -> dict[str, Any] | None:
    if path == "/api/self-improvement/preview":
        return preview_self_improvement(store, body, repo_root=repo_root)
    if path == "/api/self-improvement/run":
        return run_self_improvement(store, body)
    return None
