from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch

import pytest

from app.services.beds24_cancellation_reconcile_service import reconcile_beds24_cancellations

NOW = datetime(2026, 10, 18, 8, 0, tzinfo=timezone.utc)
SETTINGS = {'enabled': True, 'manual_sync_only': False}
MODULE = 'app.services.beds24_cancellation_reconcile_service'


def test_reconciliation_scans_modified_bookings_without_arrival_filter_and_only_cancels_linked_rows():
    db = MagicMock()
    payload_one = [
        {'id': 1, 'status': 'confirmed', 'arrival': '2026-12-01'},
        {'id': 2, 'status': 'cancelled', 'arrival': '2026-01-01'},
    ]
    payload_two = [
        {'id': 3, 'status': 'canceled', 'arrival': '2026-07-01'},
    ]
    with patch(f'{MODULE}.load_beds24_settings', return_value=SETTINGS), \
         patch(f'{MODULE}._previous_watermark', return_value=NOW), \
         patch(f'{MODULE}.fetch_beds24_bookings', side_effect=[
             (payload_one, {'nextPageLink': '/bookings?page=2'}, SETTINGS),
             (payload_two, {'data': payload_two}, SETTINGS),
         ]) as fetch, \
         patch(f'{MODULE}.apply_beds24_cancellation', side_effect=[
             {'action': 'cancelled'}, {'action': 'not_linked'},
         ]) as cancel, \
         patch(f'{MODULE}._save_watermark') as save, \
         patch(f'{MODULE}._upsert_sync_log'):
        result = reconcile_beds24_cancellations(db, now=NOW)

    assert result['ok'] is True
    assert result['fetched'] == 3
    assert result['cancelled'] == 1
    assert result['not_linked'] == 1
    assert result['pages'] == 2
    assert fetch.call_count == 2
    assert fetch.call_args_list[0].kwargs['page'] == 1
    assert fetch.call_args_list[1].kwargs['page'] == 2
    assert fetch.call_args_list[0].kwargs['modified_from']
    for fetch_call in fetch.call_args_list:
        assert fetch_call.kwargs['include_invoice_items'] is False
        assert 'arrival_from' not in fetch_call.kwargs
        assert 'arrival_to' not in fetch_call.kwargs
    assert cancel.call_count == 2
    assert cancel.call_args_list[0].args[1] == payload_one[1]
    assert cancel.call_args_list[1].args[1] == payload_two[0]
    save.assert_called_once_with(db, NOW)


def test_reconciliation_wont_move_cursor_after_cancel_error():
    db = MagicMock()
    with patch(f'{MODULE}.load_beds24_settings', return_value=SETTINGS), \
         patch(f'{MODULE}._previous_watermark', return_value=NOW), \
         patch(f'{MODULE}.fetch_beds24_bookings', return_value=(
             [{'id': 10, 'status': 'cancelled'}], {}, SETTINGS,
         )), \
         patch(f'{MODULE}.apply_beds24_cancellation', side_effect=ValueError('mapping conflict')), \
         patch(f'{MODULE}._save_watermark') as save, \
         patch(f'{MODULE}._upsert_sync_log') as log:
        with pytest.raises(RuntimeError, match='need review'):
            reconcile_beds24_cancellations(db, now=NOW)
    save.assert_not_called()
    assert db.rollback.called
    assert log.call_args.kwargs['status'] == 'error'


def test_reconciliation_wont_move_cursor_if_page_limit_hit():
    db = MagicMock()
    with patch(f'{MODULE}.load_beds24_settings', return_value=SETTINGS), \
         patch(f'{MODULE}._previous_watermark', return_value=NOW), \
         patch(f'{MODULE}.fetch_beds24_bookings', return_value=([], {'nextPageLink': 'more'}, SETTINGS)), \
         patch(f'{MODULE}._save_watermark') as save, \
         patch(f'{MODULE}._upsert_sync_log'):
        with pytest.raises(RuntimeError, match='exceeded'):
            reconcile_beds24_cancellations(db, now=NOW, max_pages=2)
    save.assert_not_called()


def test_reconciliation_respects_manual_sync_only_setting():
    db = MagicMock()
    with patch(f'{MODULE}.load_beds24_settings', return_value={'enabled': True, 'manual_sync_only': True}), \
         patch(f'{MODULE}.fetch_beds24_bookings') as fetch:
        result = reconcile_beds24_cancellations(db, now=NOW)
    assert result['skipped'] is True
    fetch.assert_not_called()
