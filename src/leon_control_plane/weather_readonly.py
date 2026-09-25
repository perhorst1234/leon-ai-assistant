"""Bounded, fixed-location weather reader for Leon's personal dashboard."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import http.client
import json
import math
import re
import threading
import time
from typing import Any, Callable
from urllib.parse import urlencode

from leon_control_plane.connector_registry import classify_connector_action


HOST = "api.open-meteo.com"
DOCS_URL = "https://open-meteo.com/en/docs"
LOCATION = {"label": "Amsterdam", "latitude": 52.3676, "longitude": 4.9041, "timezone": "Europe/Amsterdam"}
MAX_RESPONSE_BYTES = 64 * 1024
CACHE_SECONDS = 600
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_TIME_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}\Z")


class WeatherReadonlyError(ValueError):
    """Stable failure code that is safe for logs and the web response."""


@dataclass(frozen=True)
class HTTPResponse:
    status: int
    body: bytes


Transport = Callable[[str, str, int, int], HTTPResponse]


def _transport(host: str, target: str, timeout: int, max_bytes: int) -> HTTPResponse:
    if host != HOST or not target.startswith("/v1/forecast?"):
        raise WeatherReadonlyError("weather_destination_denied")
    connection = http.client.HTTPSConnection(host, timeout=timeout)
    try:
        connection.request("GET", target, headers={"Accept": "application/json", "User-Agent": "Leon/1 weather-readonly"})
        response = connection.getresponse()
        return HTTPResponse(int(response.status), response.read(max_bytes + 1))
    except (OSError, TimeoutError, http.client.HTTPException):
        raise WeatherReadonlyError("weather_transport_failed") from None
    finally:
        connection.close()


def _number(value: Any, name: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WeatherReadonlyError(f"weather_invalid_{name}")
    number = float(value)
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise WeatherReadonlyError(f"weather_invalid_{name}")
    return round(number, 1)


def _integer(value: Any, name: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise WeatherReadonlyError(f"weather_invalid_{name}")
    return value


def weather_condition(code: int) -> dict[str, str]:
    if code == 0:
        return {"label": "Helder", "category": "clear"}
    if code in {1, 2}:
        return {"label": "Licht bewolkt", "category": "cloud"}
    if code == 3:
        return {"label": "Bewolkt", "category": "cloud"}
    if code in {45, 48}:
        return {"label": "Mist", "category": "fog"}
    if code in {51, 53, 55, 56, 57}:
        return {"label": "Motregen", "category": "rain"}
    if code in {61, 63, 65, 66, 67}:
        return {"label": "Regen", "category": "rain"}
    if code in {71, 73, 75, 77, 85, 86}:
        return {"label": "Sneeuw", "category": "snow"}
    if code in {80, 81, 82}:
        return {"label": "Buien", "category": "rain"}
    if code in {95, 96, 99}:
        return {"label": "Onweer", "category": "storm"}
    return {"label": "Onbekend", "category": "unknown"}


def _target() -> str:
    query = urlencode({
        "latitude": LOCATION["latitude"],
        "longitude": LOCATION["longitude"],
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,cloud_cover,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
        "forecast_days": 3,
        "timezone": LOCATION["timezone"],
    })
    return f"/v1/forecast?{query}"


def _daily(data: dict[str, Any]) -> list[dict[str, Any]]:
    keys = [
        "time", "weather_code", "temperature_2m_max", "temperature_2m_min",
        "precipitation_probability_max", "sunrise", "sunset",
    ]
    values = [data.get(key) for key in keys]
    if any(not isinstance(items, list) or len(items) != 3 for items in values):
        raise WeatherReadonlyError("weather_invalid_daily_shape")
    result = []
    for index in range(3):
        date, sunrise, sunset = str(values[0][index]), str(values[5][index]), str(values[6][index])
        if not _DATE_RE.fullmatch(date) or not _TIME_RE.fullmatch(sunrise) or not _TIME_RE.fullmatch(sunset):
            raise WeatherReadonlyError("weather_invalid_daily_time")
        code = _integer(values[1][index], "weather_code", 0, 99)
        minimum = _number(values[3][index], "temperature", -100, 70)
        maximum = _number(values[2][index], "temperature", -100, 70)
        if minimum > maximum:
            raise WeatherReadonlyError("weather_invalid_temperature_range")
        result.append({
            "date": date,
            "weather_code": code,
            "condition": weather_condition(code),
            "temperature_min_c": minimum,
            "temperature_max_c": maximum,
            "precipitation_probability_percent": _integer(values[4][index], "precipitation_probability", 0, 100),
            "sunrise": sunrise,
            "sunset": sunset,
        })
    return result


def normalize_response(value: Any, *, retrieved_at: str) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("timezone") != LOCATION["timezone"]:
        raise WeatherReadonlyError("weather_invalid_response")
    current = value.get("current")
    if not isinstance(current, dict) or not _TIME_RE.fullmatch(str(current.get("time") or "")):
        raise WeatherReadonlyError("weather_invalid_current")
    code = _integer(current.get("weather_code"), "weather_code", 0, 99)
    return {
        "ok": True,
        "status": "available",
        "location": dict(LOCATION),
        "current": {
            "time": current["time"],
            "temperature_c": _number(current.get("temperature_2m"), "temperature", -100, 70),
            "apparent_temperature_c": _number(current.get("apparent_temperature"), "temperature", -100, 70),
            "relative_humidity_percent": _integer(current.get("relative_humidity_2m"), "humidity", 0, 100),
            "precipitation_mm": _number(current.get("precipitation"), "precipitation", 0, 500),
            "cloud_cover_percent": _integer(current.get("cloud_cover"), "cloud_cover", 0, 100),
            "wind_speed_kmh": _number(current.get("wind_speed_10m"), "wind_speed", 0, 500),
            "weather_code": code,
            "condition": weather_condition(code),
        },
        "forecast": _daily(value.get("daily") if isinstance(value.get("daily"), dict) else {}),
        "source": {
            "provider": "Open-Meteo",
            "documentation_url": DOCS_URL,
            "licence": "CC BY 4.0",
            "retrieved_at": retrieved_at,
            "note": "Model forecast; weather conditions can differ locally.",
        },
        "bounded": True,
    }


class WeatherReadonlyClient:
    def __init__(self, *, transport: Transport = _transport, timeout_seconds: int = 10, clock: Callable[[], float] = time.time):
        if not 1 <= timeout_seconds <= 30:
            raise ValueError("weather_invalid_timeout")
        self.transport = transport
        self.timeout_seconds = timeout_seconds
        self.clock = clock
        self._lock = threading.Lock()
        self._cached_at = 0.0
        self._cached: dict[str, Any] | None = None

    def current(self) -> dict[str, Any]:
        now = self.clock()
        with self._lock:
            if self._cached is not None and now - self._cached_at < CACHE_SECONDS:
                return {**self._cached, "cache": "hit"}
            response = self.transport(HOST, _target(), self.timeout_seconds, MAX_RESPONSE_BYTES)
            if not isinstance(response, HTTPResponse):
                raise WeatherReadonlyError("weather_invalid_transport_response")
            if len(response.body) > MAX_RESPONSE_BYTES:
                raise WeatherReadonlyError("weather_response_too_large")
            if response.status != 200:
                raise WeatherReadonlyError(f"weather_http_status:{response.status}")
            try:
                value = json.loads(response.body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise WeatherReadonlyError("weather_invalid_json") from None
            retrieved_at = datetime.fromtimestamp(now, UTC).replace(microsecond=0).isoformat()
            result = normalize_response(value, retrieved_at=retrieved_at)
            self._cached = result
            self._cached_at = now
            return {**result, "cache": "miss"}


CLIENT = WeatherReadonlyClient()


def weather_request(store: Any, *, method: str, path: str, client: WeatherReadonlyClient | None = None) -> dict[str, Any] | None:
    if method != "GET" or path != "/api/weather/current":
        return None
    check = classify_connector_action(
        store.get_connector_manifest("weather-open-meteo"),
        action_type="read",
        requested_scope="weather:current_read",
    )
    if check.get("decision") != "allowed" or not check.get("execution_allowed"):
        check_id = store.record_connector_permission_check(
            check, actor_type="system", actor_id="weather-open-meteo", connector_executed=False,
        )
        raise WeatherReadonlyError(f"weather_permission_denied:{check.get('decision', 'denied')}:{check_id}")
    store.record_connector_permission_check(
        check, actor_type="system", actor_id="weather-open-meteo", connector_executed=False,
    )
    try:
        result = (client or CLIENT).current()
    except WeatherReadonlyError as exc:
        failed = {
            **check,
            "decision": "failed",
            "allowed": False,
            "execution_allowed": False,
            "reason": str(exc),
            "audit_event_type": "connector_weather_failed",
            "weather_outcome": str(exc),
        }
        store.record_connector_permission_check(
            failed, actor_type="system", actor_id="weather-open-meteo", connector_executed=True,
        )
        raise
    check_id = store.record_connector_permission_check(
        check, actor_type="system", actor_id="weather-open-meteo", connector_executed=True,
    )
    return {**result, "permission_check_id": check_id}
