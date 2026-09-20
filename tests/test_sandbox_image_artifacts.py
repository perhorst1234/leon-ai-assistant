import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_container_build_contract_is_offline_narrow_and_nonroot():
    containerfile = (ROOT / "Containerfile").read_text()
    ignore = (ROOT / ".containerignore").read_text()

    assert "ARG TOOLCHAIN_IMAGE" in containerfile
    assert "FROM ${TOOLCHAIN_IMAGE}" in containerfile
    assert "python3 -m pip install --no-index --no-deps --no-build-isolation ." in containerfile
    assert "COPY src /app/src" in containerfile
    assert "COPY tests /app/tests" in containerfile
    assert "COPY requirements.lock /app/requirements.lock" in containerfile
    assert "import agents, mcp" in containerfile
    assert "chmod -R a-w /app/src" in containerfile
    assert "USER 65532:65532" in containerfile
    assert "!src/**" in ignore and "!tests/**" in ignore


def test_scripts_require_immutable_digest_clean_head_and_matching_isolation():
    build = (ROOT / "scripts" / "build-self-improvement-image").read_text()
    accept = (ROOT / "scripts" / "accept-self-improvement-sandbox").read_text()

    assert "--pull=never" in build
    assert "podman build --pull=never --network=none" in build
    assert "git status --porcelain --untracked-files=normal" in build
    assert "git archive HEAD Containerfile pyproject.toml requirements.lock src tests" in build
    assert "BASE_COMMIT must equal the current HEAD exactly" in build
    assert "--iidfile" in build
    assert "org.opencontainers.image.revision" in build
    assert "org.opencontainers.image.base.name" in build
    assert "built image revision label does not match HEAD" in build
    assert '"published_image_reference":null' in build
    assert '"local_image_id"' in build
    assert '"image_digest"' not in build
    assert "podman login" not in build
    assert " -t " not in build

    for flag in ("--pull=never", "--network=none", "--http-proxy=false", "--read-only",
                 "--read-only-tmpfs=false", "--image-volume=ignore", "--log-driver=none",
                 "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pids-limit=64",
                 "--memory=512m", "--memory-swap=512m", "--cpus=1", "--ulimit=nofile=64:64",
                 "--ipc=private", "--pid=private", "--userns=keep-id", "--workdir=/app"):
        assert flag in accept
    assert "cgroup v2 is required" in accept
    assert "SeccompEnabled" in accept
    assert '\"enabled\":false' in accept
    for field in ("executable", "image", "base_commit", "allowed_podman_versions", "service_uid", "service_gid"):
        assert f'"{field}"' in accept
    config_printf = accept.split("printf '{", 1)[-1]
    assert '"toolchain_image"' not in config_printf
    assert '"image_digest"' not in config_printf
    assert "deliberate failure unexpectedly passed" in accept


def test_isolated_pytest_imports_a_patched_src_snapshot_without_pythonpath(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\npythonpath = [\"src\"]\n"
    )
    (tmp_path / "src" / "snapshot_target.py").write_text("VALUE = 'patched snapshot'\n")
    (tmp_path / "tests" / "test_snapshot.py").write_text(
        "import snapshot_target\n\n"
        "def test_uses_patched_snapshot():\n"
        "    assert snapshot_target.VALUE == 'patched snapshot'\n"
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(tmp_path / "host_should_not_be_used")
    result = subprocess.run(
        [sys.executable, "-I", "-c",
         "import pytest; raise SystemExit(pytest.main(['-q', 'tests/test_snapshot.py']))"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout
