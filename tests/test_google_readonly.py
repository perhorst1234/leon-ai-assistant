from __future__ import annotations

from datetime import datetime
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from leon_control_plane.connector_registry import DEFAULT_CONNECTOR_MANIFESTS
from leon_control_plane.google_readonly import (
    CALENDAR_HOST,
    CALENDAR_SCOPE,
    GMAIL_HOST,
    GMAIL_SCOPE,
    OAUTH_HOST,
    GoogleOAuthCredentials,
    GoogleReadonlyClient,
    GoogleReadonlyConfig,
    GoogleReadonlyError,
    HTTPResponse,
)


def manifest(connector_id: str, **updates):
    original = next(item for item in DEFAULT_CONNECTOR_MANIFESTS if item["connector_id"] == connector_id)
    return {**original, **updates}


class Credentials:
    def __init__(self, value: GoogleOAuthCredentials):
        self.value = value
        self.calls = 0

    def get_credentials(self):
        self.calls += 1
        return self.value


class Transport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, method, host, target, headers, body, timeout, max_bytes):
        self.calls.append((method, host, target, dict(headers), body, timeout, max_bytes))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def response(value, *, status=200):
    body = value if isinstance(value, bytes) else json.dumps(value).encode()
    return HTTPResponse(status, body)


def client(scope, transport, *, credentials=None, configured_keys=None, **config):
    provider = Credentials(
        credentials
        or GoogleOAuthCredentials(access_token="runtime-token", granted_scopes=frozenset({scope}))
    )
    return (
        GoogleReadonlyClient(
            config=GoogleReadonlyConfig(
                enabled=True,
                configured_keys=frozenset(configured_keys or (
                    {"CALENDAR_CONNECTOR_TOKEN"} if scope == CALENDAR_SCOPE else {"MAIL_CONNECTOR_TOKEN"}
                )),
                **config,
            ),
            credential_provider=provider,
            transport=transport,
        ),
        provider,
    )


def calendar_range():
    return (
        datetime.fromisoformat("2026-10-24T22:30:00+02:00"),
        datetime.fromisoformat("2026-10-26T10:30:00+01:00"),
    )


def test_default_disabled_and_denied_manifest_never_touch_credentials_or_network():
    transport = Transport([])
    provider = Credentials(GoogleOAuthCredentials(access_token="private"))
    disabled = GoogleReadonlyClient(credential_provider=provider, transport=transport)
    start, end = calendar_range()

    with pytest.raises(GoogleReadonlyError, match="^google_connector_disabled$"):
        disabled.upcoming_events(manifest("calendar"), start=start, end=end)
    assert provider.calls == 0

    enabled = GoogleReadonlyClient(
        config=GoogleReadonlyConfig(enabled=True), credential_provider=provider, transport=transport
    )
    with pytest.raises(GoogleReadonlyError, match="^google_permission_denied:denied$"):
        enabled.upcoming_events(manifest("calendar", status="disabled"), start=start, end=end)
    assert provider.calls == 0
    assert transport.calls == []


def test_missing_configuration_and_wrong_manifest_or_scope_do_not_call_network():
    transport = Transport([])
    start, end = calendar_range()
    missing = GoogleReadonlyClient(config=GoogleReadonlyConfig(enabled=True), transport=transport)
    with pytest.raises(GoogleReadonlyError, match="^google_permission_denied:waiting_for_secret$"):
        missing.upcoming_events(manifest("calendar"), start=start, end=end)

    wrong, provider = client(CALENDAR_SCOPE, transport)
    with pytest.raises(GoogleReadonlyError, match="^google_manifest_mismatch$"):
        wrong.upcoming_events(manifest("mail"), start=start, end=end)
    assert provider.calls == 0

    denied, provider = client(GMAIL_SCOPE, transport, configured_keys={"CALENDAR_CONNECTOR_TOKEN"})
    with pytest.raises(GoogleReadonlyError, match="^google_oauth_scope_denied$"):
        denied.upcoming_events(manifest("calendar"), start=start, end=end)
    assert provider.calls == 1
    assert transport.calls == []


@pytest.mark.parametrize("connector_id", ["calendar", "mail"])
def test_default_manifest_requires_explicit_runtime_key_before_credentials_or_network(connector_id):
    transport = Transport([])
    provider = Credentials(
        GoogleOAuthCredentials(
            access_token="private-token",
            granted_scopes=frozenset({CALENDAR_SCOPE, GMAIL_SCOPE}),
        )
    )
    google = GoogleReadonlyClient(
        config=GoogleReadonlyConfig(enabled=True),
        credential_provider=provider,
        transport=transport,
    )

    with pytest.raises(GoogleReadonlyError, match="^google_permission_denied:waiting_for_secret$") as failure:
        if connector_id == "calendar":
            start, end = calendar_range()
            google.upcoming_events(manifest("calendar"), start=start, end=end)
        else:
            google.gmail_metadata(manifest("mail"))

    assert "CONNECTOR_TOKEN" not in str(failure.value)
    assert "private-token" not in str(failure.value)
    assert provider.calls == 0
    assert transport.calls == []


def test_calendar_uses_fixed_endpoint_utc_bounds_timezone_and_preserves_all_day():
    transport = Transport(
        [
            response(
                {
                    "items": [
                        {
                            "id": "timed_1",
                            "status": "confirmed",
                            "summary": "DST appointment",
                            "description": "must not leave the adapter",
                            "start": {"dateTime": "2026-10-25T02:30:00+02:00", "timeZone": "Europe/Amsterdam"},
                            "end": {"dateTime": "2026-10-25T02:30:00+01:00", "timeZone": "Europe/Amsterdam"},
                        },
                        {
                            "id": "day_1",
                            "summary": "Holiday",
                            "start": {"date": "2026-10-25"},
                            "end": {"date": "2026-10-26"},
                        },
                    ]
                }
            )
        ]
    )
    google, _ = client(CALENDAR_SCOPE, transport)
    start, end = calendar_range()

    result = google.upcoming_events(manifest("calendar"), start=start, end=end, limit=2)

    assert result == {
        "items": [
            {
                "id": "timed_1",
                "status": "confirmed",
                "summary": "DST appointment",
                "location": "",
                "start": {"date_time": "2026-10-25T02:30:00+02:00", "time_zone": "Europe/Amsterdam"},
                "end": {"date_time": "2026-10-25T02:30:00+01:00", "time_zone": "Europe/Amsterdam"},
                "all_day": False,
            },
            {
                "id": "day_1",
                "status": "",
                "summary": "Holiday",
                "location": "",
                "start": {"date": "2026-10-25"},
                "end": {"date": "2026-10-26"},
                "all_day": True,
            },
        ],
        "truncated": False,
        "pages_fetched": 1,
    }
    method, host, target, headers, body, timeout, max_bytes = transport.calls[0]
    query = parse_qs(urlsplit(target).query)
    assert (method, host, urlsplit(target).path) == (
        "GET",
        CALENDAR_HOST,
        "/calendar/v3/calendars/primary/events",
    )
    assert query == {
        "singleEvents": ["true"],
        "orderBy": ["startTime"],
        "timeMin": ["2026-10-24T20:30:00Z"],
        "timeMax": ["2026-10-26T09:30:00Z"],
        "timeZone": ["Europe/Amsterdam"],
        "maxResults": ["2"],
    }
    assert headers == {"Authorization": "Bearer runtime-token", "Accept": "application/json"}
    assert body is None and timeout == 10 and max_bytes > 0


def test_calendar_pagination_is_bounded_and_reports_truncation():
    transport = Transport(
        [
            response({"items": [{"id": "one", "start": {"date": "2026-10-25"}, "end": {"date": "2026-10-26"}}], "nextPageToken": "page-2"}),
            response({"items": [{"id": "two", "start": {"date": "2026-10-26"}, "end": {"date": "2026-10-27"}}], "nextPageToken": "page-3"}),
        ]
    )
    google, _ = client(CALENDAR_SCOPE, transport, max_pages=2)
    start, end = calendar_range()

    result = google.upcoming_events(manifest("calendar"), start=start, end=end, limit=5)

    assert [item["id"] for item in result["items"]] == ["one", "two"]
    assert result["truncated"] is True
    assert result["pages_fetched"] == 2
    assert len(transport.calls) == 2
    assert parse_qs(urlsplit(transport.calls[1][2]).query)["pageToken"] == ["page-2"]


def test_gmail_lists_without_q_then_gets_metadata_headers_only():
    transport = Transport(
        [
            response({"messages": [{"id": "m_1"}]}),
            response(
                {
                    "id": "m_1",
                    "threadId": "thread_1",
                    "internalDate": "1780000000000",
                    "snippet": "must not leave the adapter",
                    "payload": {
                        "body": {"data": "private-body"},
                        "headers": [
                            {"name": "From", "value": "Sender <sender@example.test>"},
                            {"name": "Subject", "value": "Planning"},
                            {"name": "Date", "value": "Wed, 9 Sep 2026 10:00:00 +0200"},
                            {"name": "To", "value": "private@example.test"},
                        ],
                    },
                }
            ),
        ]
    )
    google, _ = client(GMAIL_SCOPE, transport)

    result = google.gmail_metadata(manifest("mail"), limit=1)

    assert result == {
        "items": [
            {
                "id": "m_1",
                "thread_id": "thread_1",
                "internal_date": "1780000000000",
                "from": "Sender <sender@example.test>",
                "subject": "Planning",
                "date": "Wed, 9 Sep 2026 10:00:00 +0200",
            }
        ],
        "truncated": False,
        "pages_fetched": 1,
    }
    list_call, get_call = transport.calls
    list_query = parse_qs(urlsplit(list_call[2]).query)
    get_query = parse_qs(urlsplit(get_call[2]).query)
    assert (list_call[0], list_call[1], urlsplit(list_call[2]).path) == (
        "GET",
        GMAIL_HOST,
        "/gmail/v1/users/me/messages",
    )
    assert "q" not in list_query
    assert list_query == {"maxResults": ["1"], "includeSpamTrash": ["false"]}
    assert (get_call[0], get_call[1], urlsplit(get_call[2]).path) == (
        "GET",
        GMAIL_HOST,
        "/gmail/v1/users/me/messages/m_1",
    )
    assert get_query == {"format": ["metadata"], "metadataHeaders": ["From", "Subject", "Date"]}


def test_refresh_token_exchange_is_one_fixed_post_and_secret_never_appears_in_result():
    private = "refresh-private-value"
    transport = Transport(
        [
            response({"access_token": "fresh-access", "expires_in": 3600, "token_type": "Bearer"}),
            response({"messages": []}),
        ]
    )
    credentials = GoogleOAuthCredentials(
        refresh_token=private,
        client_id="client-id",
        client_secret="client-secret",
        granted_scopes=frozenset({GMAIL_SCOPE}),
    )
    google, _ = client(GMAIL_SCOPE, transport, credentials=credentials)

    result = google.gmail_metadata(manifest("mail"))

    oauth, api = transport.calls
    assert (oauth[0], oauth[1], oauth[2]) == ("POST", OAUTH_HOST, "/token")
    form = parse_qs(oauth[4].decode())
    assert form == {
        "client_id": ["client-id"],
        "client_secret": ["client-secret"],
        "refresh_token": [private],
        "grant_type": ["refresh_token"],
    }
    assert api[3]["Authorization"] == "Bearer fresh-access"
    assert private not in repr(result)
    assert private not in repr(credentials)
    assert len(transport.calls) == 2


@pytest.mark.parametrize(
    ("transport_response", "error"),
    [
        (response({}, status=302), "google_http_status:302"),
        (response({}, status=429), "google_http_status:429"),
        (response(b"not-json"), "google_invalid_json"),
        (response(b"x" * 2049), "google_response_too_large"),
        (TimeoutError("private provider detail"), "google_transport_failed"),
    ],
)
def test_failures_are_bounded_stable_and_never_retried(transport_response, error):
    transport = Transport([transport_response])
    google, _ = client(GMAIL_SCOPE, transport, max_response_bytes=2048)

    with pytest.raises(GoogleReadonlyError, match=f"^{error}$"):
        google.gmail_metadata(manifest("mail"))

    assert len(transport.calls) == 1


def test_input_and_provider_shapes_are_rejected_before_extra_calls():
    start, end = calendar_range()
    transport = Transport([])
    google, provider = client(CALENDAR_SCOPE, transport)
    with pytest.raises(GoogleReadonlyError, match="^google_calendar_invalid_time_range$"):
        google.upcoming_events(manifest("calendar"), start=start.replace(tzinfo=None), end=end)
    with pytest.raises(GoogleReadonlyError, match="^google_calendar_invalid_timezone$"):
        google.upcoming_events(manifest("calendar"), start=start, end=end, timezone="Mars/Olympus")
    assert provider.calls == 0
    assert transport.calls == []

    bad_id_transport = Transport([response({"messages": [{"id": "../escape"}]})])
    gmail, _ = client(GMAIL_SCOPE, bad_id_transport)
    with pytest.raises(GoogleReadonlyError, match="^google_gmail_invalid_message_id$"):
        gmail.gmail_metadata(manifest("mail"))
    assert len(bad_id_transport.calls) == 1


def test_limits_prevent_unbounded_calls():
    transport = Transport([])
    gmail, _ = client(GMAIL_SCOPE, transport)
    with pytest.raises(GoogleReadonlyError, match="^google_invalid_limit$"):
        gmail.gmail_metadata(manifest("mail"), limit=21)
    assert transport.calls == []
