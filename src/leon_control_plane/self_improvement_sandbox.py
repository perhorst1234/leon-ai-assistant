"""Review-only patch validation in a disposable Git repository.

Changed code is never executed here. Full test execution needs a separately
verified OS sandbox; a temporary directory alone is not process isolation.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from leon_control_plane.secret_scanner import assert_no_secrets


MAX_PATCH_BYTES = 512 * 1024
MAX_FILE_BYTES = 512 * 1024
MAX_OUTPUT_BYTES = 64 * 1024
VALIDATION_PROFILES = {"git_diff_check", "python_syntax"}
_DIFF_HEADER = re.compile(r"^diff --git a/([^\s]+) b/([^\s]+)$")
_PATCH_FILE = re.compile(r"^(---|\+\+\+) (?:a|b)/([^\s]+)$")
_FORBIDDEN_PATCH_MARKERS = (
    "new file mode ", "deleted file mode ", "rename from ", "rename to ",
    "copy from ", "copy to ", "old mode ", "new mode ", "GIT binary patch",
)


@dataclass(frozen=True)
class SandboxRequest:
    workspace_root: Path
    allowed_temp_root: Path
    base_commit: str
    patch: str
    patch_digest: str
    allowed_files: tuple[str, ...]
    validation_profile: str
    approval_id: str
    store: Any
    retain_patch_snapshot: bool = True
    approval_binding: dict[str, Any] | None = None


def _run(
    argv: Sequence[str], cwd: Path, *, timeout: float = 10.0,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    git_env = {
        "PATH": os.defpath,
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_ATTR_NOSYSTEM": "1",
    }
    return subprocess.run(
        list(argv), cwd=cwd,
        env=git_env,
        shell=False, text=True, capture_output=True, timeout=timeout,
        check=False, input=input_text,
    )


def _git(workspace: Path, *args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return _run(
        (
            "git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
            "-c", f"core.attributesFile={os.devnull}", *args,
        ),
        workspace, input_text=input_text,
    )


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _relative_path(value: str) -> str:
    path = Path(value)
    if (
        not value or path.is_absolute() or "\\" in value or ":" in value
        or any(part in {"", ".", ".."} or part.startswith(".") for part in path.parts)
    ):
        raise ValueError("paths must be visible normalized relative paths")
    return path.as_posix()


def _summary(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    encoded = (value or "").encode("utf-8", errors="replace")
    if len(encoded) <= MAX_OUTPUT_BYTES:
        return value or ""
    return encoded[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace") + "...[truncated]"


def _binding(request: SandboxRequest) -> dict[str, Any]:
    return {
        "workspace_root": str(request.workspace_root.resolve()),
        "allowed_temp_root": str(request.allowed_temp_root.resolve()),
        "base_commit": request.base_commit,
        "patch_digest": request.patch_digest,
        "allowed_files": list(request.allowed_files),
        "validation_profile": request.validation_profile,
    }


def _check_approval(request: SandboxRequest) -> None:
    if request.store is None:
        raise ValueError("approval store is required")
    request.store.initialize()
    with request.store.connect() as conn:
        row = conn.execute(
            "SELECT id, status, action_type, expected_change, expires_at, consumed_at FROM approvals WHERE id = ?",
            (request.approval_id,),
        ).fetchone()
    if row is None or row["status"] != "approved" or row["consumed_at"]:
        raise ValueError("approval must be approved, unconsumed and unexpired")
    if row["expires_at"]:
        try:
            expiry = datetime.fromisoformat(str(row["expires_at"]).replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("approval expiry is invalid") from None
        if expiry.astimezone(timezone.utc) <= datetime.now(timezone.utc):
            raise ValueError("approval must be approved, unconsumed and unexpired")
    if row["action_type"] != "apply_controlled_self_improvement":
        raise ValueError("approval action is not self-improvement")
    try:
        approved = json.loads(row["expected_change"])
    except (TypeError, json.JSONDecodeError):
        raise ValueError("approval lacks exact sandbox binding") from None
    if approved != (request.approval_binding or _binding(request)):
        raise ValueError("approval binding does not match workspace, base, patch or validation")


def _validate_patch(request: SandboxRequest, workspace: Path) -> tuple[str, ...]:
    if len(request.patch.encode("utf-8")) > MAX_PATCH_BYTES:
        raise ValueError("patch exceeds size cap")
    assert_no_secrets("self-improvement patch", request.patch)
    digest = hashlib.sha256(request.patch.encode("utf-8")).hexdigest()
    if digest != request.patch_digest:
        raise ValueError("patch digest mismatch")
    allowed = tuple(sorted({_relative_path(item) for item in request.allowed_files}))
    if not allowed or tuple(request.allowed_files) != allowed:
        raise ValueError("allowed_files must be non-empty, normalized and sorted")
    if request.validation_profile not in VALIDATION_PROFILES:
        raise ValueError("validation profile is not allowlisted")
    if request.validation_profile == "python_syntax" and any(not item.endswith(".py") for item in allowed):
        raise ValueError("python_syntax accepts only Python files")
    if any(marker in request.patch for marker in _FORBIDDEN_PATCH_MARKERS):
        raise ValueError("new, deleted, renamed, copied or binary files are forbidden")

    diff_lines = [line for line in request.patch.splitlines() if line.startswith("diff --git ")]
    headers = []
    for line in diff_lines:
        match = _DIFF_HEADER.fullmatch(line)
        if not match or match.group(1) != match.group(2):
            raise ValueError("patch diff header is unsupported")
        headers.append(_relative_path(match.group(1)))
    file_markers = []
    for line in request.patch.splitlines():
        if line.startswith(("--- ", "+++ ")):
            match = _PATCH_FILE.fullmatch(line)
            if not match:
                raise ValueError("patch file marker is unsupported")
            file_markers.append(_relative_path(match.group(2)))
    touched = tuple(sorted(set(headers)))
    if not touched or any(item not in allowed for item in touched) or any(item not in allowed for item in file_markers):
        raise ValueError("patch touches file outside allowlist")
    if set(file_markers) != set(touched):
        raise ValueError("patch headers and file markers disagree")
    for name in touched:
        target = workspace / name
        if not target.exists() or not target.is_file() or target.is_symlink():
            raise ValueError("patch target must be existing regular file")
        if not _inside(target.resolve(), workspace):
            raise ValueError("patch target escapes workspace")
        parent = target.parent
        while parent != workspace:
            if parent.is_symlink():
                raise ValueError("symlink parent is forbidden")
            parent = parent.parent
    return touched


def _safe_read_relative(
    root: Path, name: str, cap: int, *, expected: tuple[int, int] | None = None,
) -> bytes:
    """Read a regular file without following links or accepting path-component swaps."""
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    directory_flags = flags | getattr(os, "O_DIRECTORY", 0)
    fds: list[int] = []
    try:
        current = os.open(root, directory_flags)
        fds.append(current)
        parts = Path(_relative_path(name)).parts
        for part in parts[:-1]:
            current = os.open(part, directory_flags, dir_fd=current)
            fds.append(current)
        fd = os.open(parts[-1], flags, dir_fd=current)
        fds.append(fd)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("file must be an existing regular file")
        if expected is not None and (info.st_dev, info.st_ino) != expected:
            raise ValueError("file changed after validation")
        if info.st_size > cap:
            raise ValueError("file exceeds size cap")
        chunks: list[bytes] = []
        remaining = cap + 1
        while remaining:
            chunk = os.read(fd, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        if len(data) > cap:
            raise ValueError("file exceeds size cap")
        return data
    except OSError as exc:
        raise ValueError("file traversal changed or contains a symlink") from exc
    finally:
        for fd in reversed(fds):
            os.close(fd)


def _rollback(workspace: Path, base_commit: str) -> tuple[bool, str]:
    reset = _git(workspace, "reset", "--hard", base_commit)
    clean = _git(workspace, "clean", "-fd")
    return reset.returncode == 0 and clean.returncode == 0, _summary((reset.stderr + clean.stderr).strip())


def _reject_git_execution_config(workspace: Path) -> None:
    """Reject repository-local routes that can execute code during Git reads."""
    config = (workspace / ".git" / "config").read_text(encoding="utf-8", errors="replace").lower()
    if "[filter " in config or "[filter\t" in config or "attributesfile" in config or "[include" in config:
        raise ValueError("repository Git filters, attributes config and includes are forbidden")
    info_attributes = workspace / ".git" / "info" / "attributes"
    if info_attributes.exists() and info_attributes.read_text(encoding="utf-8", errors="replace").strip():
        raise ValueError("repository info attributes are forbidden")
    for current, directories, files in os.walk(workspace, followlinks=False):
        directories[:] = [item for item in directories if item != ".git"]
        if ".gitattributes" in files:
            raise ValueError("repository .gitattributes files are forbidden")


def execute_review_only(request: SandboxRequest) -> dict[str, Any]:
    """Apply patch in system temp repo and produce static review evidence."""
    workspace = request.workspace_root.resolve()
    temp_root = request.allowed_temp_root.resolve()
    system_temp = Path(tempfile.gettempdir()).resolve()
    if not _inside(temp_root, system_temp) or temp_root == system_temp:
        raise ValueError("allowed_temp_root must be a child of system temporary directory")
    if not _inside(workspace, temp_root) or workspace == temp_root:
        raise ValueError("workspace_root must be a child of allowed_temp_root")
    git_dir = workspace / ".git"
    if not workspace.is_dir() or not git_dir.is_dir() or not _inside(git_dir.resolve(), workspace):
        raise ValueError("workspace must have internal Git directory")
    _reject_git_execution_config(workspace)

    top = _git(workspace, "rev-parse", "--show-toplevel")
    head = _git(workspace, "rev-parse", "HEAD")
    status = _git(workspace, "status", "--porcelain", "--untracked-files=all")
    if top.returncode != 0 or Path(top.stdout.strip()).resolve() != workspace:
        raise ValueError("workspace is not Git root")
    if head.returncode != 0 or head.stdout.strip() != request.base_commit:
        raise ValueError("base commit mismatch")
    if status.returncode != 0 or status.stdout.strip():
        raise ValueError("workspace must be clean")

    touched = _validate_patch(request, workspace)
    _check_approval(request)
    checked = _git(workspace, "apply", "--check", "--whitespace=error-all", "-", input_text=request.patch)
    if checked.returncode != 0:
        request.store.consume_approval(
            request.approval_id,
            evidence="Bound sandbox patch attempt failed git apply preflight",
            actor_id="self-improvement-sandbox",
        )
        return {"status": "failed", "phase": "apply_check", "stderr": _summary(checked.stderr), "rolled_back": False}

    request.store.consume_approval(
        request.approval_id,
        evidence="Bound review-only sandbox patch validation started",
        actor_id="self-improvement-sandbox",
    )
    applied = _git(workspace, "apply", "--whitespace=error-all", "-", input_text=request.patch)
    if applied.returncode != 0:
        return {"status": "failed", "phase": "apply", "stderr": _summary(applied.stderr), "rolled_back": False}

    validation_error = ""
    changed = _git(workspace, "diff", "--name-only", "--no-ext-diff", request.base_commit)
    diff_check = _git(workspace, "diff", "--check", "--no-ext-diff")
    changed_files = tuple(sorted(line for line in changed.stdout.splitlines() if line))
    if changed.returncode != 0 or changed_files != touched:
        validation_error = "applied file set does not match approved allowlist"
    elif diff_check.returncode != 0:
        validation_error = _summary(diff_check.stderr or diff_check.stdout)
    elif request.validation_profile == "python_syntax":
        try:
            for name in touched:
                data = _safe_read_relative(workspace, name, MAX_FILE_BYTES)
                ast.parse(data.decode("utf-8"), filename=name)
        except (UnicodeDecodeError, SyntaxError, ValueError) as exc:
            validation_error = _summary(str(exc))

    after_result = _git(
        workspace, "diff", "--binary", "--no-ext-diff", "--no-textconv", request.base_commit,
    )
    after = after_result.stdout
    if after_result.returncode != 0:
        validation_error = validation_error or "unable to capture resulting patch"
    passed = not validation_error
    result: dict[str, Any] = {
        "status": "review_required" if passed else "failed",
        "approval_id": request.approval_id,
        "base_commit": request.base_commit,
        "patch_digest": request.patch_digest,
        "allowed_files": list(touched),
        "validation": {"profile": request.validation_profile, "passed": passed, "error": validation_error},
        "after_hash": hashlib.sha256(after.encode()).hexdigest(),
        "patch_snapshot": _summary(after) if request.retain_patch_snapshot else "",
        "rolled_back": False,
        "changed_code_executed": False,
    }
    if not passed:
        result["rolled_back"], result["rollback_error"] = _rollback(workspace, request.base_commit)
    request.store.record_code_change_rollback(
        target_ref=str(workspace) if request.retain_patch_snapshot else f"approval:{request.approval_id}",
        patch_snapshot=(after if request.retain_patch_snapshot else json.dumps({
            "patch_digest": hashlib.sha256(after.encode()).hexdigest(),
            "byte_count": len(after.encode()), "files": list(touched),
        }, sort_keys=True)),
        test_results={"passed": passed, "profile": request.validation_profile, "changed_code_executed": False},
        summary="Review-only temporary sandbox patch validation",
        action_ref_type="approval", action_ref_id=request.approval_id,
        actor_id="self-improvement-sandbox",
    )
    return result


run_review_only = execute_review_only
execute_self_improvement_sandbox = execute_review_only
