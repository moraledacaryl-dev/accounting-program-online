from datetime import datetime, timezone

from app.services.event_service import _event_no_prefix


def test_event_number_prefix_uses_manila_calendar_date_at_midnight_boundary():
    # 2026-08-30 16:30 UTC is already 2026-08-31 00:30 in Manila.
    assert _event_no_prefix(datetime(2026, 8, 30, 16, 30, tzinfo=timezone.utc)) == 'EVT-20260831'


def test_event_number_prefix_uses_manila_calendar_year_at_new_year_boundary():
    # 2026-12-31 16:30 UTC is already 2027-01-01 00:30 in Manila.
    assert _event_no_prefix(datetime(2026, 12, 31, 16, 30, tzinfo=timezone.utc)) == 'EVT-20270101'


def test_event_number_prefix_converts_naive_injected_datetime_as_utc():
    assert _event_no_prefix(datetime(2026, 8, 30, 16, 30)) == 'EVT-20260831'
