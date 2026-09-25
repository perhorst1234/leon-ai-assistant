from __future__ import annotations

import json
from urllib.request import Request, urlopen

import pytest

from leon_control_plane.weather_readonly import (
    HTTPResponse,
    MAX_RESPONSE_BYTES,
    WeatherReadonlyClient,
    WeatherReadonlyError,
    normalize_response,
    weather_request,
)
from leon_control_plane import weather_readonly
from test_control_plane import http_json, make_store, run_test_http_server


def response_data() -> dict:
    return {
        "timezone": "Europe/Amsterdam",
        "current": {
            "time": "2026-09-25T17:00",
            "temperature_2m": 18.4,
            "apparent_temperature": 17.2,
            "relative_humidity_2m": 61,
            "precipitation": 0.0,
            "weather_code": 2,
            "cloud_cover": 45,
            "wind_speed_10m": 13.7,
        },
        "daily": {
            "time": ["2026-09-25", "2026-09-26", "2026-09-27"],
            "weather_code": [2, 61, 3],
            "temperature_2m_max": [19.0, 17.5, 16.0],
            "temperature_2m_min": [11.0, 10.5, 9.0],
            "precipitation_probability_max": [10, 75, 30],
            "sunrise": ["2026-09-25T07:31", "2026-09-26T07:33", "2026-09-27T07:35"],
            "sunset": ["2026-09-25T19:30", "2026-09-26T19:28", "2026-09-27T19:25"],
        },
    }


def fake_client(*, clock=lambda: 1_790_355_600.0):
    calls = []

    def transport(host, target, timeout, max_bytes):
        calls.append((host, target, timeout, max_bytes))
        return HTTPResponse(200, json.dumps(response_data()).encode())

    return WeatherReadonlyClient(transport=transport, clock=clock), calls


def test_client_uses_fixed_https_contract_and_ten_minute_cache():
    now = [1_790_355_600.0]
    client, calls = fake_client(clock=lambda: now[0])
    first = client.current()
    second = client.current()
    assert len(calls) == 1
    assert calls[0][0] == "api.open-meteo.com"
    assert calls[0][1].startswith("/v1/forecast?")
    assert "latitude=52.3676" in calls[0][1]
    assert "forecast_days=3" in calls[0][1]
    assert first["cache"] == "miss"
    assert second["cache"] == "hit"
    assert first["location"]["label"] == "Amsterdam"
    assert first["current"]["condition"] == {"label": "Licht bewolkt", "category": "cloud"}
    assert first["forecast"][1]["condition"]["label"] == "Regen"
    assert first["source"]["licence"] == "CC BY 4.0"
    now[0] += 601
    assert client.current()["cache"] == "miss"
    assert len(calls) == 2


def test_response_validation_fails_closed_on_unbounded_or_malformed_data():
    bad = response_data()
    bad["current"]["temperature_2m"] = float("nan")
    with pytest.raises(WeatherReadonlyError, match="weather_invalid_temperature"):
        normalize_response(bad, retrieved_at="2026-09-25T15:00:00+00:00")

    bad = response_data()
    bad["daily"]["time"] = ["2026-09-25"]
    with pytest.raises(WeatherReadonlyError, match="weather_invalid_daily_shape"):
        normalize_response(bad, retrieved_at="2026-09-25T15:00:00+00:00")

    oversized = WeatherReadonlyClient(transport=lambda *_args: HTTPResponse(200, b"x" * (MAX_RESPONSE_BYTES + 1)))
    with pytest.raises(WeatherReadonlyError, match="weather_response_too_large"):
        oversized.current()


def test_weather_request_is_read_only_and_audited(tmp_path):
    store = make_store(tmp_path)
    client, _calls = fake_client()
    assert weather_request(store, method="POST", path="/api/weather/current", client=client) is None
    payload = weather_request(store, method="GET", path="/api/weather/current", client=client)
    assert payload["ok"] is True
    check = next(item for item in store.get_state()["connector_permission_checks"] if item["id"] == payload["permission_check_id"])
    assert check["connector_id"] == "weather-open-meteo"
    assert check["connector_executed"] == 1
    assert check["write_performed"] == 0
    assert store.validate_audit_hash_chain()


def test_provider_failure_is_visible_and_audited(tmp_path):
    store = make_store(tmp_path)
    client = WeatherReadonlyClient(transport=lambda *_args: (_ for _ in ()).throw(WeatherReadonlyError("weather_transport_failed")))
    with pytest.raises(WeatherReadonlyError, match="weather_transport_failed"):
        weather_request(store, method="GET", path="/api/weather/current", client=client)
    failed = next(
        item for item in store.get_state()["connector_permission_checks"]
        if json.loads(item["check_json"]).get("weather_outcome") == "weather_transport_failed"
    )
    assert failed["connector_executed"] == 1
    assert failed["write_performed"] == 0


def test_http_weather_requires_bearer_and_returns_bounded_payload(tmp_path, monkeypatch):
    env = "LEON_DASHBOARD_TOKEN=secret\nLEON_DASHBOARD_AUTH_MODE=off\n"
    client, _calls = fake_client()
    monkeypatch.setattr(weather_readonly, "CLIENT", client)
    with run_test_http_server(tmp_path, monkeypatch, env_text=env) as (base, _store):
        assert http_json(base, "/api/weather/current")[0] == 401
        request = Request(
            base + "/api/weather/current",
            headers={"Authorization": "Bearer secret", "Host": "127.0.0.1"},
        )
        with urlopen(request) as response:
            body = json.loads(response.read())
        assert response.status == 200
        assert body["location"]["label"] == "Amsterdam"
        assert body["bounded"] is True
        assert "permission_check_id" in body
