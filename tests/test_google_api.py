import pytest
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from leon_control_plane import google_api
from leon_control_plane.google_readonly import GoogleReadonlyError
from test_control_plane import http_json, make_store, run_test_http_server


def test_google_status_is_safe_and_disabled_by_default():
    assert google_api.status(None, {}) == {"ok": True, "enabled": False, "configured": False, "scopes": {"calendar": False, "mail": False}}


def test_google_client_uses_provider_object_and_internal_manifest_markers():
    client = google_api._client({"GOOGLE_ACCESS_TOKEN": "opaque", "GOOGLE_GRANTED_SCOPES": "scope"}, enabled=True)
    assert client.credential_provider.get_credentials().access_token == "opaque"
    assert "opaque" not in repr(client.credential_provider)
    assert {"CALENDAR_CONNECTOR_TOKEN", "MAIL_CONNECTOR_TOKEN"}.issubset(client.config.configured_keys)


class FakeClient:
    def __init__(self, *, config, credential_provider):
        self.config = config
        self.credential_provider = credential_provider

    def upcoming_events(self, manifest, *, start, end, timezone, limit):
        return {"items": [{"id": "event_1", "summary": "Planning"}], "truncated": False, "pages_fetched": 1}

    def gmail_metadata(self, manifest, *, limit):
        return {"items": [{"id": "message_1", "subject": "Hello", "from": "a@example.test", "date": "today", "thread_id": "t", "internal_date": "1"}], "truncated": False, "pages_fetched": 1}


def test_preview_returns_normalized_items_and_permission_audit_without_ingestion(tmp_path, monkeypatch):
    store = make_store(tmp_path)
    monkeypatch.setattr(google_api, "CLIENT_FACTORY", FakeClient)
    values = {"GOOGLE_READONLY_ENABLED": "true", "GOOGLE_ACCESS_TOKEN": "opaque", "GOOGLE_GRANTED_SCOPES": "https://www.googleapis.com/auth/calendar.events.readonly"}
    result = google_api.preview(store, values, "calendar", {"start": "2026-09-10T09:00:00+02:00", "end": "2026-09-10T10:00:00+02:00", "limit": 5})
    assert result["items"][0]["source_ref"] == "google:calendar:event:event_1"
    assert result["permission_check_id"].startswith("connector-check-")
    assert store.get_state()["source_records"] == []
    assert any(bool(item["connector_executed"]) for item in store.get_state()["connector_permission_checks"])


def test_preview_denies_missing_scope_before_provider_or_network(tmp_path, monkeypatch):
    store = make_store(tmp_path)
    calls = []

    class NeverClient:
        def __init__(self, **kwargs):
            calls.append("factory")

    monkeypatch.setattr(google_api, "CLIENT_FACTORY", NeverClient)
    with pytest.raises(GoogleReadonlyError, match="google_permission_denied"):
        google_api.preview(store, {"GOOGLE_READONLY_ENABLED": "true", "GOOGLE_ACCESS_TOKEN": "opaque", "GOOGLE_GRANTED_SCOPES": ""}, "mail", {"limit": 1})
    assert calls == []
    assert store.get_state()["source_records"] == []
    assert store.get_state()["connector_permission_checks"][-1]["decision"] != "allowed"


def test_http_google_routes_require_explicit_bearer(tmp_path, monkeypatch):
    with run_test_http_server(tmp_path, monkeypatch, env_text="LEON_DASHBOARD_TOKEN=secret\nLEON_DASHBOARD_AUTH_MODE=off\n") as (base, _store):
        for path, body in [
            ("/api/google/calendar/preview", {"start": "2026-09-10T09:00:00+02:00", "end": "2026-09-10T10:00:00+02:00"}),
            ("/api/google/mail/preview", {"limit": 1}),
        ]:
            status, response = http_json(base, path, method="POST", body=body)
            assert status == 401
            assert "error" in response


def test_http_google_status_and_calendar_preview_contract(tmp_path, monkeypatch):
    monkeypatch.setattr(google_api, "CLIENT_FACTORY", FakeClient)
    env = "\n".join([
        "LEON_DASHBOARD_TOKEN=secret",
        "LEON_DASHBOARD_AUTH_MODE=off",
        "GOOGLE_READONLY_ENABLED=true",
        "GOOGLE_ACCESS_TOKEN=opaque",
        "GOOGLE_GRANTED_SCOPES=https://www.googleapis.com/auth/calendar.events.readonly",
    ]) + "\n"
    with run_test_http_server(tmp_path, monkeypatch, env_text=env) as (base, store):
        # http_json intentionally supplies only common headers; use the standard library for bearer requests.
        request = Request(base + "/api/google/status", headers={"Authorization": "Bearer secret", "Host": "127.0.0.1"})
        with urlopen(request) as response:
            assert response.headers["cache-control"] == "no-store"
            status, body = response.status, json.loads(response.read())
        assert status == 200 and body["configured"] is True
        request = Request(base + "/api/google/calendar/preview", data=json.dumps({"start": "2026-09-10T09:00:00+02:00", "end": "2026-09-10T10:00:00+02:00"}).encode(), headers={"Authorization": "Bearer secret", "Content-Type": "application/json", "Host": "127.0.0.1"}, method="POST")
        with urlopen(request) as response:
            body = json.loads(response.read())
        assert body["items"][0]["source_ref"] == "google:calendar:event:event_1"
        assert store.get_state()["source_records"] == []


def _authorized_json(base, path, *, method="GET", body=None):
    request = Request(
        base + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Authorization": "Bearer secret", "Content-Type": "application/json", "Host": "127.0.0.1"},
        method=method,
    )
    try:
        with urlopen(request) as response:
            return response.status, json.loads(response.read())
    except HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def test_http_mail_preview_returns_metadata_audit_and_no_sources(tmp_path, monkeypatch):
    monkeypatch.setattr(google_api, "CLIENT_FACTORY", FakeClient)
    env = "LEON_DASHBOARD_TOKEN=secret\nLEON_DASHBOARD_AUTH_MODE=off\nGOOGLE_READONLY_ENABLED=true\nGOOGLE_ACCESS_TOKEN=opaque\nGOOGLE_GRANTED_SCOPES=https://www.googleapis.com/auth/gmail.metadata\n"
    with run_test_http_server(tmp_path, monkeypatch, env_text=env) as (base, store):
        status, body = _authorized_json(base, "/api/google/mail/preview", method="POST", body={"limit": 1})
        assert status == 200
        assert body["items"] == [{"id": "message_1", "subject": "Hello", "from": "a@example.test", "date": "today", "thread_id": "t", "internal_date": "1", "source_ref": "google:gmail:message:message_1"}]
        assert body["permission_check_id"]
        assert store.get_state()["source_records"] == []
        assert any(bool(item["connector_executed"]) for item in store.get_state()["connector_permission_checks"])


@pytest.mark.parametrize("scope", ["", "https://www.googleapis.com/auth/calendar.events.readonly"])
def test_http_disabled_or_missing_scope_short_circuits_factory(tmp_path, monkeypatch, scope):
    calls = []

    class NeverClient:
        def __init__(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(google_api, "CLIENT_FACTORY", NeverClient)
    enabled = "false" if not scope else "true"
    env = f"LEON_DASHBOARD_TOKEN=secret\nLEON_DASHBOARD_AUTH_MODE=off\nGOOGLE_READONLY_ENABLED={enabled}\nGOOGLE_ACCESS_TOKEN=opaque\nGOOGLE_GRANTED_SCOPES={scope}\n"
    with run_test_http_server(tmp_path, monkeypatch, env_text=env) as (base, store):
        status, body = _authorized_json(base, "/api/google/mail/preview", method="POST", body={"limit": 1})
        assert status == 400
        assert body["error"].startswith("google_permission_denied:")
        assert calls == []
        assert store.get_state()["source_records"] == []


def test_http_transport_error_maps_to_502_with_stable_detail(tmp_path, monkeypatch):
    class BrokenClient(FakeClient):
        def gmail_metadata(self, manifest, *, limit):
            raise GoogleReadonlyError("google_transport_failed")

    monkeypatch.setattr(google_api, "CLIENT_FACTORY", BrokenClient)
    env = "LEON_DASHBOARD_TOKEN=secret\nLEON_DASHBOARD_AUTH_MODE=off\nGOOGLE_READONLY_ENABLED=true\nGOOGLE_ACCESS_TOKEN=opaque\nGOOGLE_GRANTED_SCOPES=https://www.googleapis.com/auth/gmail.metadata\n"
    with run_test_http_server(tmp_path, monkeypatch, env_text=env) as (base, store):
        status, body = _authorized_json(base, "/api/google/mail/preview", method="POST", body={"limit": 1})
        assert status == 502
        assert body == {"error": "google_transport_failed"}
        assert store.get_state()["connector_permission_checks"][-1]["decision"] == "allowed"
        assert store.get_state()["connector_permission_checks"][-1]["connector_executed"] == 0


def test_http_invalid_preview_input_is_audited_and_safe400(tmp_path, monkeypatch):
    monkeypatch.setattr(google_api, "CLIENT_FACTORY", FakeClient)
    env = "LEON_DASHBOARD_TOKEN=secret\nLEON_DASHBOARD_AUTH_MODE=off\nGOOGLE_READONLY_ENABLED=true\nGOOGLE_ACCESS_TOKEN=opaque\nGOOGLE_GRANTED_SCOPES=https://www.googleapis.com/auth/calendar.events.readonly\n"
    with run_test_http_server(tmp_path, monkeypatch, env_text=env) as (base, store):
        status, body = _authorized_json(base, "/api/google/calendar/preview", method="POST", body={"start": "bad", "end": "also-bad"})
        assert status == 400
        assert body == {"error": "google_calendar_invalid_time_range"}
        assert store.get_state()["connector_permission_checks"][-1]["decision"] == "allowed"
