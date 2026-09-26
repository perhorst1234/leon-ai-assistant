"""Durable reply windows for Leon's marketplace conversations."""
from datetime import datetime, timedelta
import hashlib
from zoneinfo import ZoneInfo

AMSTERDAM = ZoneInfo('Europe/Amsterdam')


def reply_due(received_at: float, fingerprint: str, *, latest_hour: int = 23, start_hour: int = 8) -> float:
    """Wait 15–45 minutes; quiet hours take precedence over the two-hour target.

    Stable jitter makes restarts preserve the planned reply time. An evening
    message that cannot fit before closing moves to the next allowed morning.
    """
    if not 0 <= start_hour < latest_hour <= 23:
        raise ValueError('Invalid reply hours')
    delay = 15 + int(hashlib.sha256(fingerprint.encode()).hexdigest()[:8], 16) % 31
    received = datetime.fromtimestamp(received_at, AMSTERDAM)
    planned = received + timedelta(minutes=delay)
    opening = received.replace(hour=start_hour, minute=0, second=0, microsecond=0)
    closing = received.replace(hour=latest_hour, minute=0, second=0, microsecond=0)
    if planned < opening:
        planned = opening + timedelta(minutes=delay)
    elif planned >= closing:
        planned = (opening + timedelta(days=1)) + timedelta(minutes=delay)
    return planned.timestamp()
