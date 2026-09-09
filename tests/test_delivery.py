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


def test_delivery_defaults_mutable_db_under_private_runtime(tmp_path, monkeypatch):
    monkeypatch.delenv("LEON_DB_PATH", raising=False)
    monkeypatch.setenv("LEON_RUNTIME_DIR", str(tmp_path / "private-runtime"))
    assert DeliveryConfig.from_env(tmp_path).db == (tmp_path / "private-runtime" / "control-plane.sqlite").resolve()


def test_start_passes_one_database_to_backend_and_worker(tmp_path, monkeypatch):
    item = config(tmp_path)
    setup(item, install=False)
    token = _literal_env(item.env_file)[0]["LEON_DASHBOARD_TOKEN"]
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
    delivery.start(item)
    backend, worker = calls[:2]
    assert str(item.db) in backend[0] and str(item.db) in worker[0]
    assert backend[0][backend[0].index("--db") + 1] == worker[0][worker[0].index("--db") + 1] == str(item.db)
    assert backend[1]["env"]["LEON_DB_PATH"] == str(item.db)
    assert calls[2][1]["env"]["LEON_BACKEND_URL"] == f"http://127.0.0.1:{item.port}"
    assert calls[2][1]["env"]["LEON_DASHBOARD_TOKEN"] == token


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
