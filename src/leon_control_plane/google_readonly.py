"""Bounded, read-only Google Calendar and Gmail metadata client.

The client is inert until explicitly enabled and given a runtime credential
provider. It never reads environment variables or persists credentials.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import http.client
import json
import re
from typing import Any, Callable, Protocol
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from leon_control_plane.connector_registry import classify_connector_action


CALENDAR_HOST = "www.googleapis.com"
GMAIL_HOST = "gmail.googleapis.com"
OAUTH_HOST = "oauth2.googleapis.com"
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events.readonly"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.metadata"
MAX_RESPONSE_BYTES = 256 * 1024
MAX_ITEMS = 50
MAX_PAGES = 3
MAX_GMAIL_GETS = 20
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_CONFIGURED_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,80}$")


class GoogleReadonlyError(ValueError):
    """A stable, non-sensitive failure code safe for logs and results."""


@dataclass(frozen=True)
class GoogleOAuthCredentials:
    access_token: str = field(default="", repr=False)
    refresh_token: str = field(default="", repr=False)
    client_id: str = field(default="", repr=False)
    client_secret: str = field(default="", repr=False)
    granted_scopes: frozenset[str] = field(default_factory=frozenset)


class GoogleCredentialProvider(Protocol):
    def get_credentials(self) -> GoogleOAuthCredentials: ...


@dataclass(frozen=True)
class GoogleReadonlyConfig:
    enabled: bool = False
    configured_keys: frozenset[str] = field(default_factory=frozenset, repr=False)
    timeout_seconds: int = 10
    max_response_bytes: int = MAX_RESPONSE_BYTES
    max_pages: int = MAX_PAGES

    def validate(self) -> None:
        if not self.enabled:
            raise GoogleReadonlyError("google_connector_disabled")
        if type(self.timeout_seconds) is not int or not 1 <= self.timeout_seconds <= 30:
            raise GoogleReadonlyError("google_invalid_timeout")
        if type(self.max_response_bytes) is not int or not 1024 <= self.max_response_bytes <= MAX_RESPONSE_BYTES:
            raise GoogleReadonlyError("google_invalid_response_limit")
        if type(self.max_pages) is not int or not 1 <= self.max_pages <= MAX_PAGES:
            raise GoogleReadonlyError("google_invalid_page_limit")
        if not isinstance(self.configured_keys, frozenset) or any(
            not isinstance(key, str) or not _CONFIGURED_KEY_RE.fullmatch(key) for key in self.configured_keys
        ):
            raise GoogleReadonlyError("google_invalid_configured_keys")


@dataclass(frozen=True)
class HTTPResponse:
    status: int
    body: bytes


HTTPTransport = Callable[[str, str, str, dict[str, str], bytes | None, int, int], HTTPResponse]


def _https_transport(
    method: str,
    host: str,
    target: str,
    headers: dict[str, str],
    body: bytes | None,
    timeout: int,
    max_bytes: int,
) -> HTTPResponse:
    """One HTTPS request. http.client does not follow redirects."""
    if host not in {CALENDAR_HOST, GMAIL_HOST, OAUTH_HOST} or not target.startswith("/"):
        raise GoogleReadonlyError("google_destination_denied")
    connection = http.client.HTTPSConnection(host, timeout=timeout)
    try:
        connection.request(method, target, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read(max_bytes + 1)
        return HTTPResponse(status=int(response.status), body=raw)
    except (OSError, TimeoutError, http.client.HTTPException):
        raise GoogleReadonlyError("google_transport_failed") from None
    finally:
        connection.close()


class GoogleReadonlyClient:
    def __init__(
        self,
        *,
        config: GoogleReadonlyConfig | None = None,
        credential_provider: GoogleCredentialProvider | None = None,
        transport: HTTPTransport | None = None,
    ) -> None:
        self.config = config or GoogleReadonlyConfig()
        self.credential_provider = credential_provider
        self.transport = transport or _https_transport

    def _preflight(self, manifest: dict[str, Any], connector_id: str, scope: str, oauth_scope: str) -> str:
        self.config.validate()
        if str((manifest or {}).get("connector_id") or "") != connector_id:
            raise GoogleReadonlyError("google_manifest_mismatch")
        gate = classify_connector_action(
            manifest,
            action_type="read",
            requested_scope=scope,
            present_env_keys=set(self.config.configured_keys),
        )
        if not gate.get("allowed") or not gate.get("execution_allowed"):
            raise GoogleReadonlyError(f"google_permission_denied:{gate.get('decision', 'denied')}")

        if self.credential_provider is None:
            raise GoogleReadonlyError("google_credentials_missing")
        try:
            credentials = self.credential_provider.get_credentials()
        except Exception:
            raise GoogleReadonlyError("google_credentials_unavailable") from None
        if not isinstance(credentials, GoogleOAuthCredentials):
            raise GoogleReadonlyError("google_credentials_invalid")
        if oauth_scope not in credentials.granted_scopes:
            raise GoogleReadonlyError("google_oauth_scope_denied")
        token = credentials.access_token
        if not token:
            token = self._refresh_access_token(credentials)
        if not token or len(token) > 8192 or any(character.isspace() for character in token):
            raise GoogleReadonlyError("google_credentials_invalid")
        return token

    def _refresh_access_token(self, credentials: GoogleOAuthCredentials) -> str:
        if not all((credentials.refresh_token, credentials.client_id, credentials.client_secret)):
            raise GoogleReadonlyError("google_credentials_missing")
        body = urlencode(
            {
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "refresh_token": credentials.refresh_token,
                "grant_type": "refresh_token",
            }
        ).encode("ascii")
        response = self._request(
            "POST",
            OAUTH_HOST,
            "/token",
            {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
            body,
        )
        data = self._json(response)
        token = data.get("access_token") if isinstance(data, dict) else None
        if not isinstance(token, str):
            raise GoogleReadonlyError("google_refresh_response_invalid")
        return token

    def _request(
        self,
        method: str,
        host: str,
        target: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> HTTPResponse:
        try:
            response = self.transport(
                method,
                host,
                target,
                headers,
                body,
                self.config.timeout_seconds,
                self.config.max_response_bytes,
            )
        except GoogleReadonlyError:
            raise
        except Exception:
            raise GoogleReadonlyError("google_transport_failed") from None
        if (
            not isinstance(response, HTTPResponse)
            or type(response.status) is not int
            or not isinstance(response.body, bytes)
        ):
            raise GoogleReadonlyError("google_transport_response_invalid")
        if len(response.body) > self.config.max_response_bytes:
            raise GoogleReadonlyError("google_response_too_large")
        if response.status != 200:
            raise GoogleReadonlyError(f"google_http_status:{response.status}")
        return response

    @staticmethod
    def _json(response: HTTPResponse) -> dict[str, Any]:
        try:
            value = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise GoogleReadonlyError("google_invalid_json") from None
        if not isinstance(value, dict):
            raise GoogleReadonlyError("google_invalid_json_shape")
        return value

    @staticmethod
    def _bearer_headers(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    def upcoming_events(
        self,
        manifest: dict[str, Any],
        *,
        start: datetime,
        end: datetime,
        timezone: str = "Europe/Amsterdam",
        calendar_id: str = "primary",
        limit: int = 20,
    ) -> dict[str, Any]:
        if (
            not isinstance(start, datetime)
            or not isinstance(end, datetime)
            or start.tzinfo is None
            or end.tzinfo is None
            or start >= end
        ):
            raise GoogleReadonlyError("google_calendar_invalid_time_range")
        if (end.astimezone(UTC) - start.astimezone(UTC)).total_seconds() > 366 * 86400:
            raise GoogleReadonlyError("google_calendar_time_range_too_large")
        if not isinstance(timezone, str):
            raise GoogleReadonlyError("google_calendar_invalid_timezone")
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise GoogleReadonlyError("google_calendar_invalid_timezone") from None
        if not isinstance(calendar_id, str) or not 1 <= len(calendar_id) <= 254:
            raise GoogleReadonlyError("google_calendar_invalid_id")
        limit = _bounded_limit(limit, MAX_ITEMS)
        token = self._preflight(manifest, "calendar", "calendar:event_read", CALENDAR_SCOPE)

        base = f"/calendar/v3/calendars/{quote(calendar_id, safe='')}/events"
        common = {
            "singleEvents": "true",
            "orderBy": "startTime",
            "timeMin": _rfc3339(start),
            "timeMax": _rfc3339(end),
            "timeZone": timezone,
        }
        items: list[dict[str, Any]] = []
        page_token = ""
        pages = 0
        locally_truncated = False
        while len(items) < limit and pages < self.config.max_pages:
            query = {**common, "maxResults": str(min(250, limit - len(items)))}
            if page_token:
                query["pageToken"] = page_token
            data = self._json(self._request("GET", CALENDAR_HOST, f"{base}?{urlencode(query)}", self._bearer_headers(token)))
            raw_items = data.get("items", [])
            if not isinstance(raw_items, list):
                raise GoogleReadonlyError("google_invalid_json_shape")
            remaining = limit - len(items)
            locally_truncated = locally_truncated or len(raw_items) > remaining
            for raw in raw_items[:remaining]:
                items.append(_calendar_event(raw))
            pages += 1
            next_token = data.get("nextPageToken", "")
            if not isinstance(next_token, str) or len(next_token) > 2048:
                raise GoogleReadonlyError("google_invalid_page_token")
            page_token = next_token
            if not page_token:
                break
        return {"items": items, "truncated": bool(page_token) or locally_truncated, "pages_fetched": pages}

    def gmail_metadata(
        self,
        manifest: dict[str, Any],
        *,
        limit: int = 10,
        page_limit: int | None = None,
    ) -> dict[str, Any]:
        limit = _bounded_limit(limit, MAX_GMAIL_GETS)
        pages_allowed = self.config.max_pages if page_limit is None else _bounded_limit(page_limit, self.config.max_pages)
        token = self._preflight(manifest, "mail", "mail:metadata", GMAIL_SCOPE)
        headers = self._bearer_headers(token)
        message_ids: list[str] = []
        page_token = ""
        pages = 0
        locally_truncated = False
        while len(message_ids) < limit and pages < pages_allowed:
            query = {"maxResults": str(min(100, limit - len(message_ids))), "includeSpamTrash": "false"}
            if page_token:
                query["pageToken"] = page_token
            target = f"/gmail/v1/users/me/messages?{urlencode(query)}"
            data = self._json(self._request("GET", GMAIL_HOST, target, headers))
            raw_messages = data.get("messages", [])
            if not isinstance(raw_messages, list):
                raise GoogleReadonlyError("google_invalid_json_shape")
            remaining = limit - len(message_ids)
            locally_truncated = locally_truncated or len(raw_messages) > remaining
            for raw in raw_messages[:remaining]:
                message_id = raw.get("id") if isinstance(raw, dict) else None
                if not isinstance(message_id, str) or not _ID_RE.fullmatch(message_id):
                    raise GoogleReadonlyError("google_gmail_invalid_message_id")
                message_ids.append(message_id)
            pages += 1
            next_token = data.get("nextPageToken", "")
            if not isinstance(next_token, str) or len(next_token) > 2048:
                raise GoogleReadonlyError("google_invalid_page_token")
            page_token = next_token
            if not page_token:
                break

        items = [self._gmail_message(message_id, token) for message_id in message_ids]
        return {"items": items, "truncated": bool(page_token) or locally_truncated, "pages_fetched": pages}

    def _gmail_message(self, message_id: str, token: str) -> dict[str, Any]:
        query = [("format", "metadata"), ("metadataHeaders", "From"), ("metadataHeaders", "Subject"), ("metadataHeaders", "Date")]
        target = f"/gmail/v1/users/me/messages/{message_id}?{urlencode(query)}"
        data = self._json(self._request("GET", GMAIL_HOST, target, self._bearer_headers(token)))
        if data.get("id") != message_id:
            raise GoogleReadonlyError("google_gmail_message_mismatch")
        payload = data.get("payload")
        raw_headers = payload.get("headers", []) if isinstance(payload, dict) else []
        if not isinstance(raw_headers, list):
            raise GoogleReadonlyError("google_invalid_json_shape")
        allowed = {"from": "from", "subject": "subject", "date": "date"}
        result_headers = {value: "" for value in allowed.values()}
        for header in raw_headers:
            if not isinstance(header, dict):
                continue
            name = str(header.get("name") or "").lower()
            value = header.get("value")
            if name in allowed and isinstance(value, str):
                result_headers[allowed[name]] = _text(value, 4096)
        return {
            "id": message_id,
            "thread_id": _text(data.get("threadId"), 128),
            "internal_date": _text(data.get("internalDate"), 32),
            **result_headers,
        }


def _bounded_limit(value: int, maximum: int) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise GoogleReadonlyError("google_invalid_limit")
    return value


def _rfc3339(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _text(value: Any, maximum: int) -> str:
    if not isinstance(value, str):
        return ""
    encoded = value.encode("utf-8")
    if len(encoded) > maximum:
        raise GoogleReadonlyError("google_field_too_large")
    return value


def _calendar_event(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise GoogleReadonlyError("google_invalid_json_shape")
    event_id = raw.get("id")
    if not isinstance(event_id, str) or not _ID_RE.fullmatch(event_id):
        raise GoogleReadonlyError("google_calendar_invalid_event_id")
    start = raw.get("start")
    end = raw.get("end")
    if not isinstance(start, dict) or not isinstance(end, dict):
        raise GoogleReadonlyError("google_calendar_invalid_event_time")
    normalized_start = _event_time(start)
    normalized_end = _event_time(end)
    if ("date" in normalized_start) != ("date" in normalized_end):
        raise GoogleReadonlyError("google_calendar_invalid_event_time")
    return {
        "id": event_id,
        "status": _text(raw.get("status"), 32),
        "summary": _text(raw.get("summary"), 4096),
        "location": _text(raw.get("location"), 4096),
        "start": normalized_start,
        "end": normalized_end,
        "all_day": "date" in normalized_start,
    }


def _event_time(value: dict[str, Any]) -> dict[str, str]:
    if isinstance(value.get("date"), str):
        try:
            datetime.strptime(value["date"], "%Y-%m-%d")
        except ValueError:
            raise GoogleReadonlyError("google_calendar_invalid_event_time") from None
        return {"date": value["date"]}
    date_time = value.get("dateTime")
    if not isinstance(date_time, str):
        raise GoogleReadonlyError("google_calendar_invalid_event_time")
    try:
        parsed = datetime.fromisoformat(date_time.replace("Z", "+00:00"))
    except ValueError:
        raise GoogleReadonlyError("google_calendar_invalid_event_time") from None
    if parsed.tzinfo is None:
        raise GoogleReadonlyError("google_calendar_invalid_event_time")
    result = {"date_time": date_time}
    if isinstance(value.get("timeZone"), str):
        result["time_zone"] = _text(value["timeZone"], 128)
    return result
