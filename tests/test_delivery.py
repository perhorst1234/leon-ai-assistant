import sqlite3
from pathlib import Path

import pytest

from leon_control_plane import delivery
from leon_control_plane.delivery import DeliveryConfig, backup, restore, setup, _literal_env


def config(tmp_path: Path) -> DeliveryConfig:
    return DeliveryConfig(tmp_path, tmp_path / "runtime", tmp_path / ".env.local", tmp_path / "state" / "control-plane.sqlite")


def test_setup_writes_private_literal_env_without_replacing_it(tmp_path):
    item = config(tmp_path)
    setup(item, install=False)
    first = item.env_file.read_text()
    assert "LEON_DASHBOARD_TOKEN=" in first
    assert _literal_env(item.env_file)[0]["LEON_DASHBOARD_AUTH_MODE"] == "required"
    setup(item, install=False)
    assert item.env_file.read_text() == first
    assert (item.env_file.stat().st_mode & 0o777) == 0o600


def test_setup_installs_pinned_python_project_once_per_pyproject(tmp_path, monkeypatch):
    item = config(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\nversion='1.0.0'\n")
    (tmp_path / "requirements.lock").write_text("demo==1.0 --hash=sha256:" + "0" * 64 + "\n")
    (tmp_path / "apps" / "web" / "node_modules").mkdir(parents=True)
    python = tmp_path / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("")
    calls = []
    monkeypatch.setattr(delivery.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(delivery, "_version", lambda name: (24, 0, 0))
    monkeypatch.setattr(delivery.subprocess, "run", lambda command, **kwargs: calls.append(command))

    messages = setup(item)
    assert "installed Python dependencies" in messages
    assert calls == [
        [str(python), "-m", "ensurepip", "--upgrade"],
        [str(python), "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "--require-hashes", "-r", "requirements.lock"],
        [str(python), "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "--no-deps", "-e", "."],
    ]
    calls.clear()
    setup(item)
    assert calls == []


def test_delivery_defaults_mutable_db_under_private_runtime(tmp_path, monkeypatch):
    monkeypatch.delenv("LEON_DB_PATH", raising=False)
    monkeypatch.setenv("LEON_RUNTIME_DIR", str(tmp_path / "private-runtime"))
    assert DeliveryConfig.from_env(tmp_path).db == (tmp_path / "private-runtime" / "control-plane.sqlite").resolve()


def test_start_passes_one_database_to_backend_and_worker(tmp_path, monkeypatch):
    item = config(tmp_path)
    setup(item, install=False)
    token = _literal_env(item.env_file)[0]["LEON_DASHBOARD_TOKEN"]
    python = tmp_path / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("")
    item.env_file.write_text(item.env_file.read_text().replace(
        f"LEON_DASHBOARD_TOKEN={token}", f'LEON_DASHBOARD_TOKEN="{token}"'))
    calls = []

    class FakeProcess:
        next_pid = 41000

        def __init__(self):
            self.pid = FakeProcess.next_pid
            FakeProcess.next_pid += 1

        def poll(self):
            return None

    def fake_popen(command, **kwargs):
        calls.append((command, kwargs))
        return FakeProcess()

    monkeypatch.setattr(delivery.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(delivery.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(delivery, "_wait_for_port", lambda process, port: None)
    monkeypatch.setattr(delivery, "_port_available", lambda port: True)
    delivery.start(item)
    backend, worker = calls[:2]
    assert str(item.db) in backend[0] and str(item.db) in worker[0]
    assert backend[0][backend[0].index("--db") + 1] == worker[0][worker[0].index("--db") + 1] == str(item.db)
    assert backend[1]["env"]["LEON_DB_PATH"] == str(item.db)
    assert calls[2][1]["env"]["LEON_BACKEND_URL"] == f"http://127.0.0.1:{item.port}"
    assert calls[2][1]["env"]["LEON_DASHBOARD_TOKEN"] == token


def test_setup_recreates_partial_virtualenv_and_checks_node_version(tmp_path, monkeypatch):
    item = config(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\nversion='1.0.0'\n")
    (tmp_path / "requirements.lock").write_text("demo==1.0 --hash=sha256:" + "0" * 64 + "\n")
    (tmp_path / "apps" / "web" / "node_modules").mkdir(parents=True)
    (tmp_path / ".venv").mkdir()
    calls = []
    monkeypatch.setattr(delivery.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(delivery, "_version", lambda name: (22, 12, 9))
    monkeypatch.setattr(delivery.subprocess, "run", lambda command, **kwargs: calls.append(command))
    with pytest.raises(RuntimeError, match="Node.js 22.13"):
        setup(item)
    assert calls == []

    monkeypatch.setattr(delivery, "_version", lambda name: (22, 13, 0))
    setup(item)
    assert calls[0] == ["/usr/bin/python3", "-m", "venv", "--clear", str(tmp_path / ".venv")]


def test_owned_python_process_allows_resolved_interpreter_path(monkeypatch):
    command = ["/usr/local/bin/python3", "-m", "leon_control_plane.local_worker",
               "--db", "/private/runtime/control-plane.sqlite"]

    class Result:
        stdout = ("/usr/local/Cellar/python@3.14/bin/python3 -m "
                  "leon_control_plane.local_worker --db /private/runtime/control-plane.sqlite\n")

    monkeypatch.setattr(delivery.subprocess, "run", lambda *args, **kwargs: Result())
    assert delivery._owned_process({"pid": 1234, "command": command})


def test_start_refuses_an_in_use_port_before_launching(tmp_path, monkeypatch):
    item = config(tmp_path)
    setup(item, install=False)
    monkeypatch.setattr(delivery, "_port_available", lambda port: port != item.port)
    monkeypatch.setattr(delivery.subprocess, "Popen",
                        lambda *args, **kwargs: pytest.fail("must not launch"))

    with pytest.raises(RuntimeError, match="backend port .* already in use"):
        delivery.start(item)


def test_sqlite_backup_is_consistent_and_restore_refuses_overwrite(tmp_path):
    item = config(tmp_path)
    item.db.parent.mkdir()
    with sqlite3.connect(item.db) as connection:
        connection.execute("create table values_table (value text)")
        connection.execute("insert into values_table values ('kept')")
    destination = tmp_path / "backup.sqlite"
    assert backup(item, destination) == destination
    with pytest.raises(FileExistsError):
        backup(item, destination)
    item.db.unlink()
    assert restore(item, destination) == item.db
    with sqlite3.connect(item.db) as connection:
        assert connection.execute("select value from values_table").fetchone() == ("kept",)
    with pytest.raises(FileExistsError):
        restore(item, destination)
