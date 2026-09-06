from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Any

from leon_control_plane.secret_scanner import contains_secret

WRITE_ACTIONS = {
    "write",
    "send",
    "create_event",
    "update_event",
    "delete_event",
    "respond_to_event",
    "connect_account",
    "install_mcp",
}

WRITE_SIGNALS = [
    "stuur",
    "send",
    "verstuur",
    "maak event",
    "maak calendar",
    "create event",
    "zet in mijn agenda",
    "delete",
    "verwijder",
    "rsvp",
    "accept invite",
    "koppel",
    "connect",
    "installeer",
    "install",
]

DEFAULT_SAMPLE_DATA: dict[str, Any] = {
    "timezone": "Europe/Amsterdam",
    "workday_start": "09:00",
    "workday_end": "17:00",
    "duration_minutes": 45,
    "events": [
        {
            "id": "sample-school-math",
            "calendar_id": "sample-school",
            "title": "Wiskunde",
            "start": "2026-08-03T09:00:00+02:00",
            "end": "2026-08-03T10:30:00+02:00",
            "source": "sample_calendar",
        },
        {
            "id": "sample-work-block",
            "calendar_id": "sample-personal",
            "title": "Focusblok project",
            "start": "2026-08-03T13:00:00+02:00",
            "end": "2026-08-03T14:30:00+02:00",
            "source": "sample_calendar",
        },
        {
            "id": "sample-conflict-call",
            "calendar_id": "sample-personal",
            "title": "Projectcall",
            "start": "2026-08-03T10:00:00+02:00",
            "end": "2026-08-03T11:00:00+02:00",
            "source": "sample_calendar",
        },
    ],
    "emails": [
        {
            "id": "sample-mail-deadline",
            "from": "mentor@example.invalid",
            "subject": "Deadline verslag vrijdag",
            "received_at": "2026-08-01T10:00:00+02:00",
            "snippet": "Kun je vrijdag je verslag inleveren? Plan vandaag even een werkblok.",
        },
        {
            "id": "sample-mail-meeting",
            "from": "team@example.invalid",
            "subject": "Afspraak projectbespreking",
            "received_at": "2026-08-01T11:20:00+02:00",
            "snippet": "We zoeken maandagmiddag 45 minuten voor een projectbespreking.",
        },
    ],
}


def _contains_secret(value: Any) -> bool:
    return contains_secret(value)


def _parse_dt(value: str) -> datetime:
    text = str(value).strip()
    if not text:
        raise ValueError("datetime value is required")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError("datetime value must include timezone offset")
    return parsed


def _parse_day(value: str) -> datetime:
    parsed = _parse_dt(value)
    return datetime.combine(parsed.date(), time(0, 0), tzinfo=parsed.tzinfo)


def _parse_hhmm(value: str, default: time) -> time:
    text = str(value or "").strip()
    if not text:
        return default
    hour, minute = text.split(":", 1)
    return time(int(hour), int(minute))


def _event_window(event: dict[str, Any]) -> tuple[datetime, datetime]:
    start = _parse_dt(str(event.get("start") or ""))
    end = _parse_dt(str(event.get("end") or ""))
    if end <= start:
        raise ValueError(f"event {event.get('id') or event.get('title') or ''} has end before start")
    return start, end


def _overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end


def _merge_busy_windows(events: list[dict[str, Any]], start: datetime, end: datetime) -> list[tuple[datetime, datetime, dict[str, Any]]]:
    windows: list[tuple[datetime, datetime, dict[str, Any]]] = []
    for event in events:
        event_start, event_end = _event_window(event)
        if _overlaps(start, end, event_start, event_end):
            windows.append((max(start, event_start), min(end, event_end), event))
    return sorted(windows, key=lambda item: (item[0], item[1], str(item[2].get("id") or "")))


def _free_slots(
    *,
    events: list[dict[str, Any]],
    horizon_start: datetime,
    horizon_end: datetime,
    workday_start: time,
    workday_end: time,
    duration: timedelta,
) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    day = horizon_start.date()
    while day <= horizon_end.date():
        day_start = datetime.combine(day, workday_start, tzinfo=horizon_start.tzinfo)
        day_end = datetime.combine(day, workday_end, tzinfo=horizon_start.tzinfo)
        window_start = max(horizon_start, day_start)
        window_end = min(horizon_end, day_end)
        if window_end - window_start >= duration:
            cursor = window_start
            for busy_start, busy_end, _event in _merge_busy_windows(events, window_start, window_end):
                if busy_start - cursor >= duration:
                    slots.append(
                        {
                            "start": cursor.isoformat(),
                            "end": busy_start.isoformat(),
                            "duration_minutes": int((busy_start - cursor).total_seconds() // 60),
                        }
                    )
                cursor = max(cursor, busy_end)
            if window_end - cursor >= duration:
                slots.append(
                    {
                        "start": cursor.isoformat(),
                        "end": window_end.isoformat(),
                        "duration_minutes": int((window_end - cursor).total_seconds() // 60),
                    }
                )
        day = day + timedelta(days=1)
    return slots[:8]


def _email_signals(emails: list[dict[str, Any]]) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for email in emails:
        subject = str(email.get("subject") or "")
        snippet = str(email.get("snippet") or "")
        combined = f"{subject} {snippet}".lower()
        kind = ""
        if any(token in combined for token in ["deadline", "inlever", "due", "vrijdag"]):
            kind = "deadline_or_task"
        elif any(token in combined for token in ["afspraak", "meeting", "bespreking", "schedule"]):
            kind = "meeting_candidate"
        if kind:
            signals.append(
                {
                    "email_id": str(email.get("id") or ""),
                    "kind": kind,
                    "subject": subject[:160],
                    "confidence": 0.74 if kind == "meeting_candidate" else 0.68,
                }
            )
    return signals


def _conflicts(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    windows = [(_event_window(event)[0], _event_window(event)[1], event) for event in events]
    windows.sort(key=lambda item: (item[0], item[1]))
    for idx, (start, end, event) in enumerate(windows):
        for other_start, other_end, other in windows[idx + 1 :]:
            if other_start >= end:
                break
            if _overlaps(start, end, other_start, other_end):
                conflicts.append(
                    {
                        "event_ids": [str(event.get("id") or ""), str(other.get("id") or "")],
                        "titles": [str(event.get("title") or ""), str(other.get("title") or "")],
                        "overlap_start": max(start, other_start).isoformat(),
                        "overlap_end": min(end, other_end).isoformat(),
                    }
                )
    return conflicts


def build_planner_preview(raw: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = dict(raw or {})
    if _contains_secret(raw):
        raise ValueError("Planner preview input must not contain secret-like values")

    requested_action = str(raw.get("requested_action") or "preview").strip().lower()
    request_text = str(raw.get("request") or raw.get("prompt") or "").strip()
    data = dict(DEFAULT_SAMPLE_DATA)
    data.update(dict(raw.get("sample_data") or {}))

    horizon_start = _parse_day(str(raw.get("horizon_start") or "2026-08-03T00:00:00+02:00"))
    horizon_end = _parse_dt(str(raw.get("horizon_end") or "2026-08-04T00:00:00+02:00"))
    workday_start = _parse_hhmm(str(data.get("workday_start") or ""), time(9, 0))
    workday_end = _parse_hhmm(str(data.get("workday_end") or ""), time(17, 0))
    duration = timedelta(minutes=max(15, min(240, int(raw.get("duration_minutes") or data.get("duration_minutes") or 45))))
    events = [dict(item) for item in data.get("events", [])]
    emails = [dict(item) for item in data.get("emails", [])]

    write_like_request = requested_action in WRITE_ACTIONS or any(signal in request_text.lower() for signal in WRITE_SIGNALS)
    decision = "preview_ready"
    approval_required = False
    required_gate = ""
    if write_like_request:
        decision = "write_or_connect_denied_preview_only"
        approval_required = True
        required_gate = "approval_card_required_before_external_write_or_connect"

    free_slots = _free_slots(
        events=events,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        workday_start=workday_start,
        workday_end=workday_end,
        duration=duration,
    )
    signals = _email_signals(emails)
    conflicts = _conflicts(events)
    suggested_slot = free_slots[0] if free_slots else None
    proposals: list[dict[str, Any]] = []
    if suggested_slot:
        proposals.append(
            {
                "proposal_id": "preview-calendar-block-1",
                "action_type": "calendar_event_preview",
                "title": "Concept planningblok",
                "start": suggested_slot["start"],
                "end": (
                    _parse_dt(suggested_slot["start"]) + duration
                ).isoformat(),
                "source": "sample_calendar_and_mail",
                "source_event_ids": [str(item.get("id") or "") for item in events],
                "source_email_ids": [item["email_id"] for item in signals],
                "reasoning": "First available sample-data slot that satisfies duration and avoids detected busy windows.",
                "risk_note": "Preview only. A real calendar write would affect an external account and requires approval.",
                "required_approval_gate": "approved_write_gated_manifest_and_consumed_calendar_write_approval",
                "confidence": 0.72 if signals else 0.61,
                "execution_allowed": False,
                "write_allowed_now": False,
                "requires_approval_before_write": True,
            }
        )

    return {
        "decision": decision,
        "request": request_text,
        "requested_action": requested_action,
        "execution_allowed": False,
        "external_calls_made": False,
        "mcp_servers_installed": False,
        "accounts_connected": False,
        "secret_values_read": False,
        "write_allowed_now": False,
        "approval_required": approval_required,
        "required_gate": required_gate,
        "policy": "read_only_sample_data_preview_only",
        "horizon": {"start": horizon_start.isoformat(), "end": horizon_end.isoformat()},
        "input_summary": {
            "event_count": len(events),
            "email_count": len(emails),
            "duration_minutes": int(duration.total_seconds() // 60),
            "timezone": str(data.get("timezone") or "unknown"),
            "sample_data_only": True,
        },
        "conflicts": conflicts,
        "free_slots": free_slots,
        "email_signals": signals,
        "proposals": proposals,
        "denied_actions": [
            "install_mcp_server",
            "connect_gmail_or_calendar",
            "send_email",
            "create_update_delete_calendar_event",
            "rsvp_or_invite_attendees",
            "read_raw_secret",
        ],
        "approval_required_for": ["install", "connect", "write", "send_email", "calendar_mutation"],
        "next_safe_step": "review_preview_or_create_sandbox_plan_before_any_real_account_connection",
    }
