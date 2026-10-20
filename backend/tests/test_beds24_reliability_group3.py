"""Group 3 Beds24: protect cancellation signals, historical completeness and cursor recovery."""
from datetime import datetime, timedelta, timezone
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import Base
from app.models.entities import Booking, Beds24SyncLog, SystemSetting
from app.services import beds24_cancellation_service as cancel
from app.services import beds24_cancellation_reconcile_service as reconcile
from app.services import beds24_sync_service as sync
from scripts import audit_beds24_statuses as audit


NOW = datetime(2026, 10, 20, 14, tzinfo=timezone.utc)
MODULE = 'app.services.beds24_cancellation_reconcile_service'


@pytest.fixture
def db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.mark.parametrize('signal', [
    {'status': 'new', 'subStatus': 'cancelled'},
    {'status': '', 'statusCode': 'canceled'},
    {'status': '', 'subStatus': 'cancelled'},
])
def test_status_only_cancellation_preserves_booking_identity_and_value(db, signal):
    booking = Booking(
        external_source='beds24', external_booking_id='group3-981',
        guest_name='Verified identity', room_name='Grandeur',
        status='confirmed', gross_amount=7800, deposit_amount=3900,
        check_in='2026-09-16', check_out='2026-09-18',
    )
    db.add(booking)
    db.commit()
    remote = {'id': 'group3-981', 'price': 0, 'deposit': 0,
              'firstName': 'Unknown stale guest', **signal}
    result = cancel.apply_beds24_cancellation(db, remote)
    db.commit()
    assert result['action'] == 'cancelled'
    assert booking.status == 'cancelled'
    assert booking.guest_name == 'Verified identity'
    assert booking.room_name == 'Grandeur'
    assert booking.gross_amount == 7800
    assert booking.deposit_amount == 3900
    assert (booking.check_in, booking.check_out) == ('2026-09-16', '2026-09-18')
    assert db.query(Beds24SyncLog).filter(Beds24SyncLog.event_type == 'booking_cancellation').count() == 1


def test_regular_sync_routes_substatus_cancellation_before_guest_or_folio_changes(db):
    booking = Booking(
        external_source='beds24', external_booking_id='group3-982',
        guest_name='Keep original', room_name='Twinspire', status='confirmed',
        gross_amount=2400, deposit_amount=1000,
    )
    db.add(booking)
    db.commit()
    remote = {
        'id': 'group3-982', 'status': 'new', 'subStatus': 'cancelled',
        'firstName': 'Wrong', 'price': 0, 'deposit': 0,
    }
    result = sync.sync_booking_payload(db, remote, clear_existing_mirror=True, force_folio_mirror=True)
    assert result['status_only'] is True
    assert result['action'] == 'cancelled'
    assert booking.status == 'cancelled'
    assert booking.guest_name == 'Keep original'
    assert booking.gross_amount == 2400
    assert booking.deposit_amount == 1000


def test_reconciliation_recognizes_substatus_and_statuscode():
    db = MagicMock()
    bookings = [
        {'id': '200', 'status': 'new', 'subStatus': 'cancelled'},
        {'id': '201', 'status': '', 'statusCode': 'canceled'},
        {'id': '202', 'status': 'confirmed'},
    ]
    with patch(f'{MODULE}.load_beds24_settings', return_value={'enabled': True, 'manual_sync_only': False}), \
         patch(f'{MODULE}._previous_watermark', return_value=NOW), \
         patch(f'{MODULE}.fetch_beds24_bookings', return_value=(bookings, {}, {})), \
         patch(f'{MODULE}.apply_beds24_cancellation', return_value={'action': 'cancelled'}) as apply, \
         patch(f'{MODULE}._save_watermark') as watermark, \
         patch(f'{MODULE}._upsert_sync_log'):
        result = reconcile.reconcile_beds24_cancellations(db, now=NOW)
    assert result['cancelled'] == 2
    assert apply.call_count == 2
    assert watermark.call_count == 1


def test_success_watermark_stays_atomic_if_success_log_fails(db):
    old = '2026-08-01T11:00:00Z'
    db.add(SystemSetting(key=reconcile.STATE_KEY, value_json='{"last_success_utc":"%s"}' % old))
    db.commit()
    original_log = reconcile._upsert_sync_log

    def fail_success_only(*args, **kwargs):
        if kwargs['status'] == 'success':
            raise RuntimeError('log interrupted')
        return original_log(*args, **kwargs)

    with patch(f'{MODULE}.load_beds24_settings', return_value={'enabled': True, 'manual_sync_only': False}), \
         patch(f'{MODULE}.fetch_beds24_bookings', return_value=([], {}, {})), \
         patch(f'{MODULE}._upsert_sync_log', side_effect=fail_success_only):
        with pytest.raises(RuntimeError, match='log interrupted'):
            reconcile.reconcile_beds24_cancellations(db, now=NOW)
    db.expire_all()
    row = db.query(SystemSetting).filter_by(key=reconcile.STATE_KEY).one()
    assert '"2026-08-01T11:00:00Z"' in row.value_json
    assert db.query(Beds24SyncLog).filter(Beds24SyncLog.event_type == 'cancellation_reconciliation', Beds24SyncLog.status == 'error').count() == 1


def test_cursor_older_than_initial_lookback_is_not_clipped(db):
    db.add(SystemSetting(key=reconcile.STATE_KEY, value_json='{"last_success_utc":"2026-07-01T00:00:00Z"}'))
    db.commit()
    previous = reconcile._previous_watermark(db, NOW)
    assert previous == datetime(2026, 6, 30, 23, 45, tzinfo=timezone.utc)
    assert previous < NOW - timedelta(days=30)


@pytest.mark.parametrize('remote', [
    {'status': 'new', 'subStatus': 'cancelled'},
    {'status': '', 'statusCode': 'canceled'},
    {'subStatus': 'cancelled'},
])
def test_historical_audit_detects_cancellation_in_all_supported_status_fields(remote):
    classification, raw = audit.classify_booking(
        [{'status': 'confirmed'}], [{'id': 'group3-1', **remote}],
    )
    assert classification == 'CANCELLATION_MISMATCH'
    assert raw


def test_historical_audit_classifies_empty_status_only_when_all_fields_missing():
    assert audit.classify_booking([{'status': 'confirmed'}], [{'id': 123}])[0] == 'API_ERROR'


def test_historical_audit_completion_marker_is_invalidated_by_new_links():
    def fake_session(bookings):
        db = MagicMock()
        values = MagicMock()
        values.mappings.return_value.all.return_value = bookings
        db.execute.side_effect = lambda sql: values if 'SELECT id, external_booking_id' in str(sql) else MagicMock()
        return db

    settings = {'enabled': True, 'access_token': 'unit-test', 'api_base_url': 'https://example.test'}
    with TemporaryDirectory() as folder:
        report = Path(folder) / 'status.csv'
        marker = Path(folder) / 'status.csv.complete'
        initial = [{'id': 1, 'external_booking_id': '123', 'status': 'confirmed'}]
        grew = initial + [
            {'id': 2, 'external_booking_id': '124', 'status': 'confirmed'},
            {'id': 3, 'external_booking_id': '125', 'status': 'confirmed'},
        ]
        with patch.object(audit, 'SessionLocal', side_effect=[fake_session(initial), fake_session(grew), fake_session(grew)]), \
             patch.object(audit, 'load_beds24_settings', return_value=settings), \
             patch.object(audit, '_api_get', side_effect=[
                 [{'id': '123', 'status': 'confirmed'}],
                 [{'id': '124', 'status': 'confirmed'}],
                 [{'id': '125', 'status': 'confirmed'}],
             ]) as api, \
             patch.object(audit.time, 'sleep'):
            assert audit.run(report, 0.5, 1, complete_marker=marker) == 0
            assert marker.is_file()
            assert audit.run(report, 0.5, 1, complete_marker=marker) == 0
            assert not marker.exists()  # Pending newly imported booking 125.
            assert audit.run(report, 0.5, 1, complete_marker=marker) == 0
            assert marker.is_file()
            assert api.call_count == 3  # Previously completed 123 not re-requested.
            assert '3' in marker.read_text()
