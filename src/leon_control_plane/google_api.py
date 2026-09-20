"""Authenticated, bounded HTTP boundary for the inert Google read-only client."""
from datetime import datetime
from typing import Any
import json
from pathlib import Path

from leon_control_plane.connector_registry import classify_connector_action
from leon_control_plane.google_readonly import (
    CALENDAR_SCOPE,
    GMAIL_SCOPE,
    GoogleOAuthCredentials,
    GoogleReadonlyClient,
    GoogleReadonlyConfig,
    GoogleReadonlyError,
)
from leon_control_plane.google_credentials import GoogleCredentialFileProvider

CLIENT_FACTORY = GoogleReadonlyClient
_GOOGLE_CREDENTIAL_KEYS = {
    "GOOGLE_ACCESS_TOKEN", "GOOGLE_REFRESH_TOKEN", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_GRANTED_SCOPES"
}
_GOOGLE_FILE_KEY = "GOOGLE_CREDENTIALS_FILE"
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

class _Provider:
    def __init__(self, credentials): self._credentials = credentials
    def get_credentials(self): return self._credentials
    def __repr__(self): return "<GoogleCredentialProvider redacted>"


def _client(values: dict[str, str], *, enabled: bool):
    provider, credentials = _provider_and_credentials(values)
    keys = {key for key, value in values.items() if value and key in _GOOGLE_CREDENTIAL_KEYS}
    credential_set = bool(credentials and (credentials.access_token or all((credentials.refresh_token, credentials.client_id, credentials.client_secret))))
    # The default manifests use these markers as their required credential gate.
    # They are derived only from a complete usable Google credential set; callers
    # cannot self-declare a connector as configured through arbitrary env keys.
    if credential_set:
        keys.add("CALENDAR_CONNECTOR_TOKEN")
        keys.add("MAIL_CONNECTOR_TOKEN")
    return CLIENT_FACTORY(config=GoogleReadonlyConfig(enabled=enabled, configured_keys=frozenset(keys)), credential_provider=provider)


def _provider_and_credentials(values: dict[str, str]):
    path = values.get(_GOOGLE_FILE_KEY, "").strip()
    if path:
        provider = GoogleCredentialFileProvider(path, repository_root=_REPOSITORY_ROOT)
    else:
        credentials = GoogleOAuthCredentials(
            access_token=values.get("GOOGLE_ACCESS_TOKEN", ""), refresh_token=values.get("GOOGLE_REFRESH_TOKEN", ""),
            client_id=values.get("GOOGLE_CLIENT_ID", ""), client_secret=values.get("GOOGLE_CLIENT_SECRET", ""),
            granted_scopes=frozenset(filter(None, values.get("GOOGLE_GRANTED_SCOPES", "").split()))
        )
        return _Provider(credentials), credentials
    try:
        credentials = provider.get_credentials()
        return _Provider(credentials), credentials
    except Exception:
        return provider, None


def _granted_scopes(values: dict[str, str]) -> set[str]:
    provider, credentials = _provider_and_credentials(values)
    if credentials is not None:
        return set(credentials.granted_scopes)
    return set()


def status(store, values: dict[str, str]) -> dict[str, Any]:
    enabled = values.get("GOOGLE_READONLY_ENABLED", "").lower() in {"1", "true", "yes"}
    _, credentials = _provider_and_credentials(values)
    configured = bool(credentials and (credentials.access_token or all((credentials.refresh_token, credentials.client_id, credentials.client_secret))))
    granted = set(credentials.granted_scopes) if credentials else set()
    return {"ok": True, "enabled": enabled, "configured": configured, "scopes": {"calendar": "https://www.googleapis.com/auth/calendar.events.readonly" in granted, "mail": "https://www.googleapis.com/auth/gmail.metadata" in granted}}


def _permission_check(store, manifest: dict[str, Any], scope: str, values: dict[str, str]) -> dict[str, Any]:
    check = classify_connector_action(
        manifest,
        action_type="read",
        requested_scope=scope,
        present_env_keys=set(_client_configured_keys(values)),
    )
    return check


def _client_configured_keys(values: dict[str, str]) -> set[str]:
    keys = {key for key, value in values.items() if value and key in _GOOGLE_CREDENTIAL_KEYS}
    _, credentials = _provider_and_credentials(values)
    credential_set = bool(credentials and (credentials.access_token or all((credentials.refresh_token, credentials.client_id, credentials.client_secret))))
    if credential_set:
        keys.update({"CALENDAR_CONNECTOR_TOKEN", "MAIL_CONNECTOR_TOKEN"})
    return keys


def preview(store, values: dict[str, str], kind: str, data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise GoogleReadonlyError("google_invalid_request")
    enabled = values.get("GOOGLE_READONLY_ENABLED", "").lower() in {"1", "true", "yes"}
    connector_id = "calendar" if kind == "calendar" else "mail"
    manifest = store.get_connector_manifest(connector_id)
    scope = "calendar:event_read" if kind == "calendar" else "mail:metadata"
    check = _permission_check(store, manifest, scope, values)
    oauth_scope = CALENDAR_SCOPE if kind == "calendar" else GMAIL_SCOPE
    if not enabled:
        check["decision"] = "denied"
        check["allowed"] = False
        check["execution_allowed"] = False
        check["reason"] = "Google read-only connector is disabled."
    elif oauth_scope not in _granted_scopes(values):
        check["decision"] = "denied"
        check["allowed"] = False
        check["execution_allowed"] = False
        check["reason"] = "Required Google OAuth scope is not granted."
    if check.get("decision") != "allowed" or not check.get("execution_allowed"):
        check_id = store.record_connector_permission_check(
            check, actor_type="system", actor_id="google-readonly-preview", connector_executed=False
        )
        raise GoogleReadonlyError(f"google_permission_denied:{check.get('decision', 'denied')}:{check_id}")
    # Record the allowed decision before constructing or invoking the provider.
    # If credentials or transport fail, this remains the truthful audit record.
    store.record_connector_permission_check(
        check, actor_type="system", actor_id="google-readonly-preview", connector_executed=False
    )
    client = _client(values, enabled=enabled)
    if kind == "calendar":
        try:
            start, end = datetime.fromisoformat(str(data.get("start"))), datetime.fromisoformat(str(data.get("end")))
            limit = int(data.get("limit", 20))
        except (TypeError, ValueError):
            raise GoogleReadonlyError("google_calendar_invalid_time_range") from None
        result = client.upcoming_events(manifest, start=start, end=end, timezone=str(data.get("timezone") or "Europe/Amsterdam"), limit=limit)
        result["items"] = [{**item, "source_ref": f"google:calendar:event:{item['id']}"} for item in result.get("items", [])]
    else:
        try:
            limit = int(data.get("limit", 10))
        except (TypeError, ValueError):
            raise GoogleReadonlyError("google_invalid_limit") from None
        result = client.gmail_metadata(manifest, limit=limit)
        result["items"] = [{**item, "source_ref": f"google:gmail:message:{item['id']}"} for item in result.get("items", [])]
    check_id = store.record_connector_permission_check(
        check, actor_type="system", actor_id="google-readonly-preview", connector_executed=True
    )
    return {"ok": True, **result, "permission_check_id": check_id}


def google_request(store, *, method: str, path: str, values: dict[str, str], data: dict[str, Any] | None = None):
    if path == "/api/google/status" and method == "GET": return status(store, values)
    if method == "POST" and path == "/api/google/calendar/preview": return preview(store, values, "calendar", data or {})
    if method == "POST" and path == "/api/google/mail/preview": return preview(store, values, "mail", data or {})
    return None
