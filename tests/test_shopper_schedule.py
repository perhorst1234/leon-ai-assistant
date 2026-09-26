from datetime import datetime

from leon_control_plane.shopper_schedule import AMSTERDAM, reply_due


def stamp(value):
    return datetime.fromisoformat(value).replace(tzinfo=AMSTERDAM).timestamp()


def test_daytime_reply_is_delayed_and_within_two_hours():
    received = stamp('2026-09-26T14:00:00')
    due = reply_due(received, 'seller-message-1')
    assert 15 * 60 <= due - received <= 45 * 60
    assert reply_due(received, 'seller-message-1') == due


def test_late_evening_reply_moves_to_next_morning():
    due = datetime.fromtimestamp(reply_due(stamp('2026-09-26T22:55:00'), 'late'), AMSTERDAM)
    assert due.day == 27 and due.hour == 8


def test_quiet_hours_and_dst_transition():
    due = datetime.fromtimestamp(reply_due(stamp('2026-10-25T01:30:00'), 'dst'), AMSTERDAM)
    assert due.day == 25 and due.hour == 8
