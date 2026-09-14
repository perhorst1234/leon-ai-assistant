"""Fail-closed rootless Podman execution contract; deliberately not API-wired."""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence

from leon_control_plane.secret_scanner import redact_text, scan_text

OUTPUT_CAP_BYTES = 64 * 1024
FILE_CAP_BYTES = 512 * 1024
TOTAL_FILE_CAP_BYTES = 2 * 1024 * 1024
MAX_FILES = 32
TIMEOUT_SECONDS = 60
FIXED_PYTEST_ARGV = ("python", "-I", "-m", "pytest", "-q", "--disable-warnings", "--maxfail=1")
_IMAGE = re.compile(r"^[a-z0-9][a-z0-9._/-]*@sha256:[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_VERSION = re.compile(r"(?:podman\s+version\s+|version:\s*)([0-9]+(?:\.[0-9]+){1,2})", re.I)
_RUN_NAME = re.compile(r"leon-si-[a-f0-9]{32}")
_PROBE_NAME = re.compile(r"leon-si-probe-[a-f0-9]{32}")
Runner = Callable[[Sequence[str], float], subprocess.CompletedProcess[Any]]


@dataclass(frozen=True)
class _BoundedCapture:
    sample: bytes
    total_bytes: int
    sha256: str
    truncated: bool


@dataclass(frozen=True)
class PodmanSandboxConfig:
    enabled: bool
    executable: str
    image: str
    base_commit: str
    allowed_podman_versions: tuple[str, ...]
    service_uid: int
    service_gid: int


@dataclass(frozen=True)
class SandboxRunRequest:
    workspace_root: Path
    base_commit: str
    allowed_files: tuple[str, ...]


def _client_env() -> dict[str, str]:
    env = {"PATH": os.defpath, "LANG": "C", "LC_ALL": "C"}
    for key in ("HOME", "XDG_RUNTIME_DIR"):
        value = os.environ.get(key)
        if value and os.path.isabs(value):
            env[key] = value
    return env


def _run(argv: Sequence[str], timeout: float) -> subprocess.CompletedProcess[Any]:
    process = subprocess.Popen(
        list(argv), env=_client_env(), shell=False,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    states = [dict(sample=bytearray(), total=0, digest=hashlib.sha256()) for _ in range(2)]

    def drain(pipe: Any, state: dict[str, Any]) -> None:
        while True:
            chunk = pipe.read(8192)
            if not chunk:
                break
            state["total"] += len(chunk)
            state["digest"].update(chunk)
            room = OUTPUT_CAP_BYTES - len(state["sample"])
            if room > 0:
                state["sample"].extend(chunk[:room])
            if state["total"] > OUTPUT_CAP_BYTES:
                try:
                    process.kill()
                except OSError:
                    pass

    threads = [
        threading.Thread(target=drain, args=(process.stdout, states[0]), daemon=True),
        threading.Thread(target=drain, args=(process.stderr, states[1]), daemon=True),
    ]
    for thread in threads:
        thread.start()
    timed_out = False
    try:
        returncode = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        returncode = process.wait()
    for thread in threads:
        thread.join(timeout=5)

    captures = tuple(
        _BoundedCapture(bytes(state["sample"]), state["total"], state["digest"].hexdigest(), state["total"] > OUTPUT_CAP_BYTES)
        for state in states
    )
    if timed_out:
        raise subprocess.TimeoutExpired(list(argv), timeout, output=captures[0], stderr=captures[1])
    return subprocess.CompletedProcess(list(argv), returncode, captures[0], captures[1])


def _err(message: str) -> ValueError:
    return ValueError("Podman sandbox rejected: " + message)


def _bytes(value: Any) -> bytes:
    if isinstance(value, _BoundedCapture):
        return value.sample
    return b"" if value is None else value if isinstance(value, bytes) else str(value).encode("utf-8", "replace")


def _output(value: Any) -> dict[str, Any]:
    raw = _bytes(value)
    sample = raw[:OUTPUT_CAP_BYTES].decode("utf-8", "replace")
    redacted = redact_text(sample)
    return {
        "bytes": value.total_bytes if isinstance(value, _BoundedCapture) else len(raw),
        "sha256": value.sha256 if isinstance(value, _BoundedCapture) else hashlib.sha256(raw).hexdigest(),
        "truncated": value.truncated if isinstance(value, _BoundedCapture) else len(raw) > OUTPUT_CAP_BYTES,
        "redacted": redacted != sample,
        "text": redacted,
    }


def load_podman_sandbox_config(path: Path | str) -> PodmanSandboxConfig:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise _err("configuration is unreadable") from exc
    fields = {"enabled", "executable", "image", "base_commit", "allowed_podman_versions", "service_uid", "service_gid"}
    if not isinstance(raw, dict) or set(raw) != fields or type(raw["enabled"]) is not bool:
        raise _err("configuration is invalid")
    versions = raw["allowed_podman_versions"]
    if not isinstance(versions, list):
        raise _err("configuration has invalid field types")
    cfg = PodmanSandboxConfig(
        raw["enabled"], raw["executable"], raw["image"], raw["base_commit"],
        tuple(versions), raw["service_uid"], raw["service_gid"],
    )
    if (
        not isinstance(cfg.executable, str)
        or (cfg.executable and not os.path.isabs(cfg.executable))
        or not isinstance(cfg.image, str) or not isinstance(cfg.base_commit, str)
        or not all(isinstance(v, str) and re.fullmatch(r"[0-9]+\.[0-9]+(?:\.[0-9]+)?", v) for v in cfg.allowed_podman_versions)
    ):
        raise _err("configuration has invalid field types")
    if cfg.enabled:
        _validate_config(cfg)
    return cfg


def _validate_config(cfg: PodmanSandboxConfig) -> None:
    if not cfg.enabled:
        raise _err("sandbox is disabled")
    if not cfg.executable or not _IMAGE.fullmatch(cfg.image):
        raise _err("image must be immutable repository@sha256 reference")
    if not _COMMIT.fullmatch(cfg.base_commit):
        raise _err("base_commit must be exact lowercase commit")
    if not cfg.allowed_podman_versions or len(set(cfg.allowed_podman_versions)) != len(cfg.allowed_podman_versions):
        raise _err("allowed Podman versions must be non-empty and unique")
    for label, value in (("service_uid", cfg.service_uid), ("service_gid", cfg.service_gid)):
        if not isinstance(value, int) or isinstance(value, bool) or not 0 < value <= 2**31 - 1:
            raise _err(f"{label} must be non-root")


def _version(value: Any) -> str:
    found = _VERSION.search(_bytes(value).decode("utf-8", "replace"))
    if not found:
        raise _err("cannot parse Podman version")
    return found.group(1)


def _call_probe(
    runner: Runner, argv: Sequence[str], timeout: float, label: str,
    verifier: Callable[[], None] | None = None,
) -> subprocess.CompletedProcess[Any]:
    if verifier:
        verifier()
    try:
        result = runner(argv, timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise _err(f"{label} unavailable") from exc
    if result.returncode:
        raise _err(f"{label} failed")
    return result


def _isolation_flags(cfg: PodmanSandboxConfig, name: str) -> list[str]:
    return [
        cfg.executable, "run", "--rm", "--name", name, "--pull=never",
        "--network=none", "--http-proxy=false", "--read-only",
        "--read-only-tmpfs=false", "--image-volume=ignore", "--log-driver=none",
        "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pids-limit=64",
        "--memory=512m", "--memory-swap=512m", "--cpus=1",
        "--ulimit=nofile=64:64", "--ipc=private", "--pid=private",
        "--userns=keep-id", f"--user={cfg.service_uid}:{cfg.service_gid}",
        "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m", "--workdir=/app",
        "--env=HOME=/tmp", "--env=PYTHONDONTWRITEBYTECODE=1", "--env=PYTHONHASHSEED=0",
    ]


def _cleanup(
    cfg: PodmanSandboxConfig, name: str, runner: Runner,
    verifier: Callable[[], None] | None = None,
) -> dict[str, Any]:
    try:
        if verifier:
            verifier()
        done = runner((cfg.executable, "rm", "--force", "--ignore", name), 10)
        return {"attempted": True, "returncode": done.returncode, "stderr": _output(done.stderr)}
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return {"attempted": True, "error": "cleanup_unavailable"}


def _verify_executable(
    cfg: PodmanSandboxConfig, stat_func: Callable[..., Any], lstat_func: Callable[..., Any],
    expected: tuple[int, int] | None = None,
) -> tuple[int, int]:
    try:
        followed, raw = stat_func(cfg.executable), lstat_func(cfg.executable)
    except OSError as exc:
        raise _err("Podman executable is missing") from exc
    if stat.S_ISLNK(raw.st_mode) or not stat.S_ISREG(followed.st_mode):
        raise _err("executable must be regular non-symlink")
    if followed.st_uid != 0 or followed.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise _err("executable must be root-owned and not group/world writable")
    identity = (followed.st_dev, followed.st_ino)
    if expected is not None and identity != expected:
        raise _err("Podman executable identity changed")
    return identity


def probe_podman(
    cfg: PodmanSandboxConfig, *, runner: Runner = _run, stat_func=os.stat,
    lstat_func=os.lstat, uid_func=os.getuid, gid_func=os.getgid,
    name_factory: Callable[[], str] | None = None,
) -> dict[str, Any]:
    _validate_config(cfg)
    if cfg.service_uid != uid_func() or cfg.service_gid != gid_func():
        raise _err("configured service identity does not match process")
    executable_identity = _verify_executable(cfg, stat_func, lstat_func)
    verify = lambda: _verify_executable(cfg, stat_func, lstat_func, executable_identity)

    version = _call_probe(runner, (cfg.executable, "--version"), 10, "Podman version probe", verify)
    parsed = _version(version.stdout)
    if parsed not in cfg.allowed_podman_versions:
        raise _err("Podman version is not allowlisted")
    info = _call_probe(runner, (cfg.executable, "info", "--format=json"), 10, "Podman info probe", verify)
    try:
        host = json.loads(_bytes(info.stdout))["host"]
        security = host["security"]
        ok = (
            host["os"] == "linux" and host["cgroupVersion"] == "v2"
            and host["serviceIsRemote"] is False and security["rootless"] is True
            and security["seccompEnabled"] is True
        )
    except (TypeError, KeyError, json.JSONDecodeError):
        ok = False
    if not ok:
        raise _err("Podman must be local Linux rootless with cgroup v2 and seccomp")
    inspected = _call_probe(runner, (cfg.executable, "image", "inspect", "--format=json", cfg.image), 10, "image inspect", verify)
    try:
        result = json.loads(_bytes(inspected.stdout))
        digest = result[0]["Digest"] if isinstance(result, list) else result["Digest"]
    except (TypeError, KeyError, IndexError, json.JSONDecodeError) as exc:
        raise _err("image inspect lacks digest") from exc
    if digest != cfg.image.rsplit("@", 1)[1]:
        raise _err("image digest mismatch")

    name = name_factory() if name_factory else "leon-si-probe-" + uuid.uuid4().hex
    if not _PROBE_NAME.fullmatch(name):
        raise _err("probe container name is unsafe")
    smoke = [*_isolation_flags(cfg, name), cfg.image, "python", "-I", "-c", "import os; assert os.geteuid() != 0"]
    smoke_error: ValueError | None = None
    try:
        _call_probe(runner, smoke, 20, "isolation smoke probe", verify)
    except ValueError as exc:
        smoke_error = exc
    cleanup = _cleanup(cfg, name, runner, verify)
    if cleanup.get("returncode") != 0:
        raise _err("isolation smoke cleanup failed")
    if smoke_error:
        raise smoke_error
    return {
        "podman_version": parsed, "image_digest": digest, "isolation_smoke": "passed",
        "executable_identity": list(executable_identity),
    }


def _relative_name(value: str) -> str:
    if not isinstance(value, str):
        raise _err("allowed files must be visible normalized relative paths")
    path = Path(value)
    if (
        not value or path.is_absolute() or "\\" in value
        or any(character in value for character in (",", "=", ":", "\n", "\r", "\x00"))
        or any(part in {"", ".", ".."} or part.startswith(".") for part in path.parts)
    ):
        raise _err("allowed files must be visible normalized relative paths")
    return path.as_posix()


def _safe_read(root: Path, name: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    dir_flags = flags | getattr(os, "O_DIRECTORY", 0)
    fds: list[int] = []
    try:
        current = os.open(root, dir_flags)
        fds.append(current)
        parts = Path(_relative_name(name)).parts
        for part in parts[:-1]:
            current = os.open(part, dir_flags, dir_fd=current)
            fds.append(current)
        target = os.open(parts[-1], flags, dir_fd=current)
        fds.append(target)
        info = os.fstat(target)
        if not stat.S_ISREG(info.st_mode) or info.st_size > FILE_CAP_BYTES:
            raise _err("approved source must be bounded regular file")
        chunks: list[bytes] = []
        remaining = FILE_CAP_BYTES + 1
        while remaining:
            chunk = os.read(target, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        if len(data) > FILE_CAP_BYTES:
            raise _err("approved source exceeds size cap")
        if scan_text(data.decode("utf-8", "replace")).has_findings:
            raise _err("approved source contains secret-like content")
        return data
    except OSError as exc:
        raise _err("approved source traversal changed or contains symlink") from exc
    finally:
        for descriptor in reversed(fds):
            os.close(descriptor)


def _validated_names(request: SandboxRunRequest) -> tuple[str, ...]:
    if not _COMMIT.fullmatch(request.base_commit) or not request.workspace_root.is_absolute():
        raise _err("workspace or base_commit is invalid")
    names = tuple(_relative_name(name) for name in request.allowed_files)
    if not names or len(names) > MAX_FILES or tuple(sorted(set(names))) != names:
        raise _err("allowed files must be non-empty, unique and sorted")
    return names


@contextmanager
def _staged_files(request: SandboxRunRequest) -> Iterator[Path]:
    names = _validated_names(request)
    stage = Path(tempfile.mkdtemp(prefix="leon-si-stage-"))
    try:
        os.chmod(stage, 0o700)
        total_bytes = 0
        for name in names:
            data = _safe_read(request.workspace_root, name)
            total_bytes += len(data)
            if total_bytes > TOTAL_FILE_CAP_BYTES:
                raise _err("approved sources exceed total size cap")
            destination = stage / name
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            for parent in destination.parents:
                if parent == stage.parent:
                    break
                os.chmod(parent, 0o700)
            descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o400)
            try:
                view = memoryview(data)
                while view:
                    written = os.write(descriptor, view)
                    if written <= 0:
                        raise _err("snapshot write failed")
                    view = view[written:]
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            os.chmod(destination, 0o400)
        yield stage
    finally:
        for current, directories, files in os.walk(stage, topdown=False, followlinks=False):
            for filename in files:
                try:
                    os.unlink(Path(current) / filename)
                except OSError:
                    pass
            for dirname in directories:
                try:
                    os.rmdir(Path(current) / dirname)
                except OSError:
                    pass
        try:
            os.rmdir(stage)
        except OSError:
            pass


def _snapshot_mounts(cfg: PodmanSandboxConfig, request: SandboxRunRequest, stage: Path) -> tuple[tuple[str, Path], ...]:
    meta = os.lstat(stage)
    if stat.S_ISLNK(meta.st_mode) or not stat.S_ISDIR(meta.st_mode) or meta.st_uid != cfg.service_uid or stat.S_IMODE(meta.st_mode) != 0o700:
        raise _err("snapshot root must be private and service-owned")
    mounts: list[tuple[str, Path]] = []
    resolved_stage = stage.resolve()
    for name in _validated_names(request):
        source = stage / name
        item = os.lstat(source)
        resolved_source = source.resolve()
        if (
            stat.S_ISLNK(item.st_mode) or not stat.S_ISREG(item.st_mode)
            or item.st_uid != cfg.service_uid or item.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
            or resolved_stage not in resolved_source.parents
        ):
            raise _err("snapshot source is unsafe")
        mounts.append((name, resolved_source))
    return tuple(mounts)


def build_podman_argv(cfg: PodmanSandboxConfig, request: SandboxRunRequest, container_name: str, *, staged_root: Path) -> list[str]:
    _validate_config(cfg)
    if request.base_commit != cfg.base_commit:
        raise _err("request base_commit does not match image")
    if not _RUN_NAME.fullmatch(container_name):
        raise _err("container name is unsafe")
    argv = _isolation_flags(cfg, container_name)
    for name, source in _snapshot_mounts(cfg, request, staged_root):
        argv.extend(("--mount", f"type=bind,src={source},dst=/app/{name},readonly=true"))
    return [*argv, cfg.image, *FIXED_PYTEST_ARGV]


def _argv_digest(argv: Sequence[str]) -> str:
    return hashlib.sha256(json.dumps(list(argv), separators=(",", ":")).encode()).hexdigest()


def _base_evidence(status: str, name: str | None, probe: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "status": status, "container_name": name, "probe": probe,
        "policy": {
            "network": "none", "root_filesystem": "read_only", "image_volumes": "ignored",
            "http_proxy": "disabled", "mounts": "private_read_only_snapshots", "python_isolated": True,
        },
    }


def run_podman_sandbox(
    cfg: PodmanSandboxConfig, request: SandboxRunRequest, *, runner: Runner = _run,
    stat_func=os.stat, lstat_func=os.lstat, uid_func=os.getuid, gid_func=os.getgid,
    name_factory: Callable[[], str] | None = None, probe_name_factory: Callable[[], str] | None = None,
) -> dict[str, Any]:
    try:
        probe = probe_podman(
            cfg, runner=runner, stat_func=stat_func, lstat_func=lstat_func,
            uid_func=uid_func, gid_func=gid_func, name_factory=probe_name_factory,
        )
    except ValueError as exc:
        evidence = _base_evidence("sandbox_unavailable", None, None)
        evidence["error"] = redact_text(str(exc))[:512]
        return evidence

    name = name_factory() if name_factory else "leon-si-" + uuid.uuid4().hex
    executable_identity = tuple(probe["executable_identity"])
    verify = lambda: _verify_executable(cfg, stat_func, lstat_func, executable_identity)
    try:
        with _staged_files(request) as stage:
            argv = build_podman_argv(cfg, request, name, staged_root=stage)
            execution_status, returncode, stdout, stderr, error = "failed", None, None, None, None
            try:
                verify()
                done = runner(argv, TIMEOUT_SECONDS)
                returncode, stdout, stderr = done.returncode, done.stdout, done.stderr
                execution_status = "passed" if done.returncode == 0 else "failed"
            except subprocess.TimeoutExpired as exc:
                execution_status, stdout, stderr = "timed_out", exc.stdout, exc.stderr
            except OSError:
                error = "execution_unavailable"
            cleanup = _cleanup(cfg, name, runner, verify)
            status = execution_status if cleanup.get("returncode") == 0 else "cleanup_failed"
            evidence = _base_evidence(status, name, probe)
            evidence.update({
                "execution_status": execution_status, "argv_sha256": _argv_digest(argv),
                "returncode": returncode, "stdout": _output(stdout), "stderr": _output(stderr),
                "cleanup": cleanup,
            })
            if execution_status == "timed_out":
                evidence["timeout_seconds"] = TIMEOUT_SECONDS
            if error:
                evidence["error"] = error
            return evidence
    except (OSError, ValueError) as exc:
        evidence = _base_evidence("sandbox_rejected", name, probe)
        evidence["error"] = redact_text(str(exc))[:512]
        return evidence


load_config = load_podman_sandbox_config
run_sandbox = run_podman_sandbox
