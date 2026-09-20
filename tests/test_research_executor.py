from pathlib import Path
import json
from urllib.request import Request, urlopen

import pytest

from leon_control_plane.research_executor import ResearchExecutorError, normalize_request, preview, run, status
from leon_control_plane.store import ControlPlaneStore
from test_control_plane import http_json, run_test_http_server


class FakeProvider:
    def search(self, **kwargs):
        assert kwargs["query"] == "bounded query"
        assert kwargs["domains"] == ["example.com"]
        return {"success": True, "data": {"web": [{"title": "Example", "description": "A result", "url": "https://example.com/page"}]}, "creditsUsed": 1}


def store(tmp_path: Path) -> ControlPlaneStore:
    seed = Path(__file__).parents[1] / "state" / "control-plane.seed.json"
    result = ControlPlaneStore(tmp_path / "test.sqlite", seed)
    result.initialize()
    return result


def values(**extra):
    return {"RESEARCH_EXECUTOR_ENABLED": "true", "FIRECRAWL_API_KEY": "test-key", "RESEARCH_ALLOWED_DOMAINS": "example.com", **extra}


def test_disabled_by_default_and_preview_is_explicit(tmp_path: Path):
    s = store(tmp_path)
    assert status(s, {})["enabled"] is False
    result = preview(s, {}, {"query": "bounded query", "domains": ["example.com"]})
    assert result["status"] == "disabled"
    assert result["preview_fingerprint"]
    assert result["execution_allowed"] is False


def test_preview_fingerprint_required_for_fake_read_only_run(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("leon_control_plane.research_executor.socket.getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, ("93.184.216.34", 0))])
    s = store(tmp_path)
    request = {"query": "bounded query", "allowed_domains": ["example.com"], "max_results": 1}
    planned = preview(s, values(), request)
    with pytest.raises(ResearchExecutorError, match="fingerprint"):
        run(s, values(), {**request, "preview_id": planned["preview_id"], "preview_fingerprint": "wrong"}, FakeProvider())
    with pytest.raises(ResearchExecutorError, match="preview_required"):
        run(s, values(), {**request, "preview_fingerprint": planned["preview_fingerprint"]}, FakeProvider())
    result = run(s, values(), {**request, "preview_id": planned["preview_id"], "preview_fingerprint": planned["preview_fingerprint"]}, FakeProvider())
    assert result["results"][0]["source_ref"] == "firecrawl:https://example.com/page"
    assert s.validate_audit_hash_chain()


def test_limits_allowlist_and_unsafe_sources(monkeypatch):
    assert normalize_request({"query": "x", "domains": ["example.com"]}, []).domains == ("example.com",)
    with pytest.raises(ResearchExecutorError, match="allowlist"):
        normalize_request({"query": "x"}, [])
    monkeypatch.setattr("leon_control_plane.research_executor.socket.getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, ("10.0.0.1", 0))])
    from leon_control_plane.research_executor import validate_https_url
    with pytest.raises(ResearchExecutorError, match="private"):
        validate_https_url("https://example.com/private", ["example.com"])


def test_unresolved_source_address_fails_closed(monkeypatch):
    monkeypatch.setattr("leon_control_plane.research_executor.socket.getaddrinfo", lambda *args, **kwargs: [])
    from leon_control_plane.research_executor import validate_https_url
    with pytest.raises(ResearchExecutorError, match="unresolved"):
        validate_https_url("https://example.com/page", ["example.com"])


def test_empty_ui_domain_list_uses_configured_allowlist():
    request = normalize_request({"query": "x", "allowed_domains": [], "max_results": 3}, ["example.com"])
    assert request.domains == ("example.com",)


def test_http_research_routes_require_explicit_bearer(tmp_path, monkeypatch):
    env = "LEON_DASHBOARD_TOKEN=secret\nLEON_DASHBOARD_AUTH_MODE=off\nRESEARCH_EXECUTOR_ENABLED=false\nRESEARCH_ALLOWED_DOMAINS=example.com\n"
    with run_test_http_server(tmp_path, monkeypatch, env_text=env) as (base, _store):
        assert http_json(base, "/api/research/status")[0] == 401
        assert http_json(base, "/api/research/preview", method="POST", body={"query": "x"})[0] == 401
        assert http_json(base, "/api/research/run", method="POST", body={"query": "x"})[0] == 401


def test_http_disabled_preview_returns_reviewable_contract(tmp_path, monkeypatch):
    env = "LEON_DASHBOARD_TOKEN=secret\nLEON_DASHBOARD_AUTH_MODE=off\nRESEARCH_EXECUTOR_ENABLED=false\nRESEARCH_ALLOWED_DOMAINS=example.com\n"
    with run_test_http_server(tmp_path, monkeypatch, env_text=env) as (base, _store):
        request = Request(
            base + "/api/research/preview",
            data=json.dumps({"query": "x", "allowed_domains": [], "max_results": 3}).encode(),
            headers={"Authorization": "Bearer secret", "Content-Type": "application/json", "Host": "127.0.0.1"},
            method="POST",
        )
        with urlopen(request) as response:
            body = json.loads(response.read())
        assert body["status"] == "disabled"
        assert body["execution_allowed"] is False
        assert body["preview_id"].startswith("connector-check-")


def test_invalid_provider_shape_is_audited_as_executed_failure(tmp_path: Path):
    class InvalidProvider:
        def search(self, **_kwargs):
            return []

    s = store(tmp_path)
    request = {"query": "bounded query", "allowed_domains": ["example.com"], "max_results": 1}
    planned = preview(s, values(), request)
    with pytest.raises(ResearchExecutorError, match="invalid_response"):
        run(s, values(), {**request, "preview_id": planned["preview_id"], "preview_fingerprint": planned["preview_fingerprint"]}, InvalidProvider())
    failed = next(
        item for item in s.get_state()["connector_permission_checks"]
        if json.loads(item["check_json"]).get("research_outcome") == "research_provider_invalid_response"
    )
    assert failed["connector_executed"] == 1
    event = next(item for item in s.get_state()["audit_events"] if item["event_type"] == "connector_research_failed")
    assert json.loads(event["redacted_payload_json"])["details"]["research_outcome"] == "research_provider_invalid_response"
