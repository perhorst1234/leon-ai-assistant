import json
import os
import stat
import subprocess
import sys

import pytest

from leon_control_plane import os_sandbox
from leon_control_plane.os_sandbox import (
    PodmanSandboxConfig,
    SandboxRunRequest,
    build_podman_argv,
    load_podman_sandbox_config,
    probe_podman,
    run_podman_sandbox,
)


def cfg(**changes):
    values = {
        "enabled": True,
        "executable": "/usr/bin/podman",
        "image": "registry.example/leon@sha256:" + "a" * 64,
        "base_commit": "b" * 40,
        "allowed_podman_versions": ("5.0.0",),
        "service_uid": os.getuid(),
        "service_gid": os.getgid(),
    }
    values.update(changes)
    return PodmanSandboxConfig(**values)


def regular(_path):
    return os.stat_result((stat.S_IFREG | 0o755,) + (0,) * 9)


def request(tmp_path, name="value.py", content="VALUE = 1\n"):
    target = tmp_path / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return SandboxRunRequest(tmp_path, "b" * 40, (name,))


class Runner:
    def __init__(self, result=0, output=b"ok", cleanup_result=0):
        self.calls = []
        self.result = result
        self.output = output
        self.cleanup_result = cleanup_result

    def __call__(self, argv, timeout):
        argv = tuple(argv)
        self.calls.append((argv, timeout))
        if argv[1] == "--version":
            return subprocess.CompletedProcess(argv, 0, b"podman version 5.0.0", b"")
        if argv[1] == "info":
            body = {"host": {"os": "linux", "cgroupVersion": "v2", "serviceIsRemote": False, "security": {"rootless": True, "seccompEnabled": True}}}
            return subprocess.CompletedProcess(argv, 0, json.dumps(body).encode(), b"")
        if argv[1] == "image":
            return subprocess.CompletedProcess(argv, 0, json.dumps({"Digest": "sha256:" + "a" * 64}).encode(), b"")
        if argv[1] == "rm":
            return subprocess.CompletedProcess(argv, self.cleanup_result, b"", b"cleanup")
        if "--name" in argv and argv[argv.index("--name") + 1].startswith("leon-si-probe-"):
            return subprocess.CompletedProcess(argv, 0, b"probe", b"")
        return subprocess.CompletedProcess(argv, self.result, self.output, self.output)


def run_names():
    return {
        "name_factory": lambda: "leon-si-" + "d" * 32,
        "probe_name_factory": lambda: "leon-si-probe-" + "e" * 32,
    }


def test_production_argv_is_fixed_restricted_and_mounts_snapshot(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    req = request(work)
    with os_sandbox._staged_files(req) as stage:
        argv = build_podman_argv(cfg(), req, "leon-si-" + "c" * 32, staged_root=stage)
        joined = " ".join(argv)
        for required in (
            "--pull=never", "--network=none", "--http-proxy=false", "--read-only",
            "--read-only-tmpfs=false", "--image-volume=ignore", "--log-driver=none",
            "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pids-limit=64",
            "--memory=512m", "--memory-swap=512m", "--cpus=1", "--ulimit=nofile=64:64",
            "--ipc=private", "--pid=private", "--userns=keep-id", "HOME=/tmp",
            "PYTHONDONTWRITEBYTECODE=1", "PYTHONHASHSEED=0",
        ):
            assert required in argv or required in joined
        assert argv[-7:] == ["python", "-I", "-m", "pytest", "-q", "--disable-warnings", "--maxfail=1"]
        assert str(stage) in joined
        assert str(work) not in joined
        assert all(word not in joined for word in ("--env-file", "--device", "--gpus", "--volume", "/run/", "shell"))


def test_probe_uses_official_locality_field_and_runs_smoke_cleanup():
    runner = Runner()
    result = probe_podman(
        cfg(), runner=runner, stat_func=regular, lstat_func=regular,
        name_factory=lambda: "leon-si-probe-" + "f" * 32,
    )
    assert result["isolation_smoke"] == "passed"
    smoke = next(call for call, _ in runner.calls if call[1] == "run")
    assert "--network=none" in smoke and "--http-proxy=false" in smoke and "--image-volume=ignore" in smoke
    assert any(call[1:4] == ("rm", "--force", "--ignore") for call, _ in runner.calls)


def test_probe_rejects_remote_missing_field_digest_identity_and_probe_errors(tmp_path):
    runner = Runner()

    def remote(argv, timeout):
        result = runner(argv, timeout)
        if argv[1] == "info":
            return subprocess.CompletedProcess(argv, 0, b'{"host":{"os":"linux","cgroupVersion":"v2","security":{"rootless":true,"seccompEnabled":true}}}', b"")
        return result

    with pytest.raises(ValueError, match="must be local"):
        probe_podman(cfg(), runner=remote, stat_func=regular, lstat_func=regular)
    with pytest.raises(ValueError, match="identity"):
        probe_podman(cfg(service_uid=os.getuid() + 1), runner=runner, stat_func=regular, lstat_func=regular)

    def mismatch(argv, timeout):
        result = runner(argv, timeout)
        if argv[1] == "image":
            return subprocess.CompletedProcess(argv, 0, json.dumps({"Digest": "sha256:" + "0" * 64}).encode(), b"")
        return result

    with pytest.raises(ValueError, match="digest mismatch"):
        probe_podman(cfg(), runner=mismatch, stat_func=regular, lstat_func=regular)

    def broken(argv, timeout):
        raise OSError("sensitive host path")

    result = run_podman_sandbox(cfg(), request(tmp_path), runner=broken, stat_func=regular, lstat_func=regular)
    assert result["status"] == "sandbox_unavailable"
    assert "sensitive host path" not in result["error"]


def test_safe_snapshot_holds_parent_descriptor_during_symlink_swap(tmp_path, monkeypatch):
    root = tmp_path / "root"
    nested = root / "nested"
    nested.mkdir(parents=True)
    (nested / "value.py").write_text("SAFE = True\n")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "value.py").write_text("SAFE = False\n")
    real_open = os_sandbox.os.open
    swapped = False

    def swapping_open(path, flags, *args, **kwargs):
        nonlocal swapped
        descriptor = real_open(path, flags, *args, **kwargs)
        if path == "nested" and not swapped:
            nested.replace(root / "original")
            nested.symlink_to(outside, target_is_directory=True)
            swapped = True
        return descriptor

    monkeypatch.setattr(os_sandbox.os, "open", swapping_open)
    assert os_sandbox._safe_read(root, "nested/value.py") == b"SAFE = True\n"


def test_symlink_and_secret_source_are_rejected_before_execution(tmp_path):
    outside = tmp_path / "outside.py"
    outside.write_text("VALUE = 2\n")
    work = tmp_path / "work"
    work.mkdir()
    (work / "value.py").symlink_to(outside)
    runner = Runner()
    result = run_podman_sandbox(cfg(), SandboxRunRequest(work, "b" * 40, ("value.py",)), runner=runner, stat_func=regular, lstat_func=regular, **run_names())
    assert result["status"] == "sandbox_rejected"
    assert sum(1 for call, _ in runner.calls if call[1] == "run") == 1  # smoke only

    (work / "value.py").unlink()
    (work / "value.py").write_text("API_KEY=abcd1234\n")
    result = run_podman_sandbox(cfg(), SandboxRunRequest(work, "b" * 40, ("value.py",)), runner=Runner(), stat_func=regular, lstat_func=regular, **run_names())
    assert result["status"] == "sandbox_rejected" and "secret-like" in result["error"]


def test_timeout_always_cleans_caps_and_redacts_output(tmp_path):
    runner = Runner()
    original = runner.__call__

    def timeout(argv, seconds):
        if argv[1] == "run" and not argv[argv.index("--name") + 1].startswith("leon-si-probe-"):
            raise subprocess.TimeoutExpired(argv, seconds, output=b"token=abcd1234\n" + b"x" * 70000, stderr=b"y" * 70000)
        return original(argv, seconds)

    result = run_podman_sandbox(cfg(), request(tmp_path), runner=timeout, stat_func=regular, lstat_func=regular, **run_names())
    assert result["status"] == "timed_out" and result["cleanup"]["returncode"] == 0
    assert result["stdout"]["truncated"] and result["stdout"]["redacted"]
    assert "abcd1234" not in result["stdout"]["text"]
    assert "argv" not in result and len(result["argv_sha256"]) == 64


def test_success_always_cleans_and_snapshot_disappears(tmp_path):
    runner = Runner(output=b"ok")
    result = run_podman_sandbox(cfg(), request(tmp_path), runner=runner, stat_func=regular, lstat_func=regular, **run_names())
    assert result["status"] == "passed" and result["cleanup"]["returncode"] == 0
    actual = [call for call, _ in runner.calls if call[1] == "run" and not call[call.index("--name") + 1].startswith("leon-si-probe-")][0]
    mount = actual[actual.index("--mount") + 1]
    source = mount.split(",src=", 1)[1].split(",dst=", 1)[0]
    assert not os.path.exists(source)


def test_cleanup_failure_overrides_execution_success(tmp_path):
    result = run_podman_sandbox(cfg(), request(tmp_path), runner=Runner(cleanup_result=4), stat_func=regular, lstat_func=regular, **run_names())
    # Smoke cleanup fails before untrusted execution can start.
    assert result["status"] == "sandbox_unavailable" and "cleanup failed" in result["error"]


def test_disabled_template_is_inert_and_config_is_exact(tmp_path):
    config = tmp_path / "sandbox.json"
    disabled = {
        "enabled": False, "executable": "/usr/bin/podman", "image": "", "base_commit": "",
        "allowed_podman_versions": [], "service_uid": 10001, "service_gid": 10001,
    }
    config.write_text(json.dumps(disabled))
    assert load_podman_sandbox_config(config).enabled is False
    enabled = {**disabled, "enabled": True, "image": "registry.example/leon:latest", "base_commit": "b" * 40, "allowed_podman_versions": ["5.0.0"]}
    config.write_text(json.dumps(enabled))
    with pytest.raises(ValueError, match="immutable"):
        load_podman_sandbox_config(config)
    config.write_text(json.dumps({**disabled, "extra": True}))
    with pytest.raises(ValueError, match="invalid"):
        load_podman_sandbox_config(config)


def test_client_environment_drops_proxy_socket_and_credentials(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://user:pass@example.test")
    monkeypatch.setenv("CONTAINER_HOST", "unix:///dangerous.sock")
    monkeypatch.setenv("DOCKER_HOST", "tcp://dangerous.test")
    monkeypatch.setenv("API_KEY", "abcd1234")
    env = os_sandbox._client_env()
    assert set(env) <= {"PATH", "LANG", "LC_ALL", "HOME", "XDG_RUNTIME_DIR"}
    assert all("dangerous" not in value and "abcd1234" not in value for value in env.values())


def test_mount_delimiters_are_rejected(tmp_path):
    for name in ("value.py,readonly=false", "value.py=bad", "dir:value.py"):
        with pytest.raises(ValueError, match="normalized"):
            os_sandbox._validated_names(SandboxRunRequest(tmp_path, "b" * 40, (name,)))


def test_snapshot_retries_partial_writes(tmp_path, monkeypatch):
    req = request(tmp_path, content="VALUE = 'complete'\n")
    real_write = os_sandbox.os.write

    def partial_write(descriptor, data):
        return real_write(descriptor, data[:3])

    monkeypatch.setattr(os_sandbox.os, "write", partial_write)
    with os_sandbox._staged_files(req) as stage:
        assert (stage / "value.py").read_text() == "VALUE = 'complete'\n"


def test_default_runner_caps_output_during_process_execution():
    done = os_sandbox._run(
        (sys.executable, "-I", "-c", "import os; os.write(1, b'x' * 70000)"), 10,
    )
    evidence = os_sandbox._output(done.stdout)
    assert evidence["truncated"] and evidence["bytes"] == 70000
    assert len(evidence["text"].encode()) == os_sandbox.OUTPUT_CAP_BYTES


def test_probe_rejects_executable_inode_change():
    calls = 0

    def changing_stat(_path):
        nonlocal calls
        calls += 1
        inode = 1 if calls == 1 else 2
        return os.stat_result((stat.S_IFREG | 0o755, inode, 3, 1, 0, 0, 0, 0, 0, 0))

    with pytest.raises(ValueError, match="identity changed"):
        probe_podman(cfg(), runner=Runner(), stat_func=changing_stat, lstat_func=regular)
