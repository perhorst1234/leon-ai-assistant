from pathlib import Path
import json
import time
from urllib.request import Request, urlopen

from leon_control_plane.server_monitor import ServerMonitor, server_status_request
from leon_control_plane import server_monitor
from test_control_plane import http_json, make_store, run_test_http_server


class FakeProbe:
    uptime = 42.5
    load = (0.1, 0.2, 0.3)
    memory = {"total_bytes": 1024, "available_bytes": 512, "status": "ok"}


def test_monitor_uses_injected_probe_and_reports_bounded_read_only_snapshot(tmp_path):
    result = ServerMonitor(paths=(("runtime", tmp_path),), probe=FakeProbe()).snapshot()
    assert result["status"] == "ok"
    assert result["uptime"] == {"value": 42.5, "status": "ok"}
    assert result["load"]["value"] == [0.1, 0.2, 0.3]
    assert result["memory"]["total_bytes"] == 1024
    assert result["disk"][0]["label"] == "runtime"
    assert str(tmp_path) not in str(result)
    assert result["permission"] == {"scope": "server:status_read", "read_only": True, "audit": "connector execution"}
    assert result["bounded"] is True


def test_monitor_makes_unavailable_metrics_explicit():
    class Missing:
        uptime = None
        load = None
        memory = {"status": "unavailable"}

    result = ServerMonitor(probe=Missing()).snapshot()
    assert result["uptime"]["status"] == "unavailable"
    assert result["load"]["status"] == "unavailable"
    assert result["memory"]["status"] == "unavailable"


def test_darwin_uptime_fallback_uses_native_boot_time(monkeypatch):
    monkeypatch.setattr(Path, "read_text", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError()))
    monkeypatch.setattr(server_monitor, "_darwin_boot_time", lambda: time.time() - 42.0)
    assert 41.0 <= ServerMonitor()._uptime() <= 43.0


def test_status_request_is_get_only_and_audited(tmp_path):
    store = make_store(tmp_path)
    assert server_status_request(store, method="POST", path="/api/server/status") is None
    assert server_status_request(store, method="GET", path="/api/other") is None
    payload = server_status_request(store, method="GET", path="/api/server/status", paths=(("repo", Path.cwd()),))
    assert payload["ok"] is True
    assert payload["disk"][0]["label"] == "repo"
    check = store.get_state()["connector_permission_checks"][0]
    assert check["connector_id"] == "server-monitor"
    assert check["connector_executed"] == 1


def test_disabled_status_skips_probe_and_records_no_execution(tmp_path):
    store = make_store(tmp_path)

    class ExplodingProbe:
        @property
        def uptime(self):
            raise AssertionError("probe must not run")

    payload = server_status_request(store, method="GET", path="/api/server/status", enabled=False, probe=ExplodingProbe())
    assert payload["status"] == "disabled"
    assert store.get_state()["connector_permission_checks"][0]["connector_executed"] == 0


def test_http_server_status_requires_explicit_bearer(tmp_path, monkeypatch):
    env = "LEON_DASHBOARD_TOKEN=secret\nLEON_DASHBOARD_AUTH_MODE=off\nLEON_SERVER_MONITOR_ENABLED=true\n"
    with run_test_http_server(tmp_path, monkeypatch, env_text=env) as (base, _store):
        status, body = http_json(base, "/api/server/status")
        assert status == 401
        assert "error" in body


def test_http_server_status_returns_audited_labels_without_paths(tmp_path, monkeypatch):
    env = "LEON_DASHBOARD_TOKEN=secret\nLEON_DASHBOARD_AUTH_MODE=off\nLEON_SERVER_MONITOR_ENABLED=true\n"
    with run_test_http_server(tmp_path, monkeypatch, env_text=env) as (base, store):
        request = Request(
            base + "/api/server/status",
            headers={"Authorization": "Bearer secret", "Host": "127.0.0.1"},
        )
        with urlopen(request) as response:
            body = json.loads(response.read())
        assert response.status == 200
        assert {item["label"] for item in body["disk"]} == {"repository", "state", "database"}
        assert str(tmp_path) not in json.dumps(body)
        check = next(item for item in store.get_state()["connector_permission_checks"] if item["id"] == body["permission_check_id"])
        assert check["connector_executed"] == 1
