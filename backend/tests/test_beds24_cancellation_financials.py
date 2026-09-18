import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import channel_payout_reconciliation  # register payout tables
from app.db.database import Base
from app.models.entities import (
    Beds24BookingMap, Beds24SyncLog, Booking, BookingChannel, BookingFolio, BookingFolioLine,
    FinancialAccount, Guest, MoneyTransaction, Receivable, Room,
)
from app.services import beds24_cancellation_service as cancellation
from app.services import beds24_sync_service as sync
from app.services.guest_service import folio_balance_summary
from app.services.hospitality_service import _serialize_booking


@pytest.fixture
def db():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def setup_booking(db, status='confirmed'):
    guest = Guest(full_name='Manually Corrected Guest', email='verified@example.test')
    channel = BookingChannel(code='AGO', name='Agoda', is_active=True)
    room = Room(name='Twinspire', room_no='8', is_active=True)
    db.add_all([guest, channel, room]); db.flush()
    booking = Booking(guest=guest, guest_name=guest.full_name, room_id=room.id, channel_id=channel.id,
                      external_source='beds24', external_booking_id='93138380', status=status,
                      check_in='2026-09-16', check_out='2026-09-19', gross_amount=9000,
                      deposit_amount=4500, notes='Verified local notes', room_name='Twinspire')
    db.add(booking); db.flush()
    db.add(Beds24BookingMap(beds24_booking_id='93138380', local_booking_id=booking.id,
                           local_guest_id=guest.id, beds24_room_id='535692', beds24_property_id='253718', raw_snapshot='original snapshot'))
    db.commit()
    return booking


def payload(**overrides):
    return {'id': 93138380, 'status': 'cancelled', 'firstName': 'Unnamed Guest',
            'arrival': '2026-09-16', 'departure': '2026-09-19', 'roomId': 535692,
            'propertyId': 253718, 'price': 0, 'deposit': 0, 'notes': 'stale upstream', **overrides}


def columns(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


@pytest.mark.parametrize('incoming', ['', 'Unnamed Guest', 'Wrong Stale Person'])
def test_cancellation_preserves_all_local_identity_and_booking_fields(db, incoming):
    booking = setup_booking(db)
    before = columns(booking)
    guest_before = columns(booking.guest)
    mapping_before = columns(db.query(Beds24BookingMap).one())
    # Full sync must route cancellations before any guest match or folio rewriting.
    result = sync.sync_booking_payload(db, payload(firstName=incoming), force_folio_mirror=True, clear_existing_mirror=True)
    assert result['status_only'] and result['action'] == 'cancelled'
    assert booking.status == 'cancelled'
    assert {k: v for k, v in columns(booking).items() if k not in {'status', 'updated_at'}} == {k: v for k, v in before.items() if k not in {'status', 'updated_at'}}
    assert columns(booking.guest) == guest_before
    assert columns(db.query(Beds24BookingMap).one()) == mapping_before


def test_repeated_refresh_is_idempotent(db):
    booking = setup_booking(db)
    cancellation.apply_beds24_cancellation(db, payload()); db.commit()
    before = columns(booking)
    assert cancellation.apply_beds24_cancellation(db, payload())['action'] == 'unchanged'
    db.commit()
    assert columns(booking) == before
    assert db.query(Beds24SyncLog).count() == 1


def test_non_cancelled_refresh_does_not_change_anything(db):
    booking = setup_booking(db)
    before = columns(booking)
    assert cancellation.apply_beds24_cancellation(db, payload(status='confirmed'))['action'] == 'unchanged'
    db.commit()
    assert columns(booking) == before
    assert db.query(Beds24SyncLog).count() == 0


@pytest.mark.parametrize('refund,fee,unallocated', [(0, 0, 4500), (4500, 0, 0), (0, 4500, 0)])
def test_real_payment_refund_retained_fee_and_history_survive(db, refund, fee, unallocated):
    booking = setup_booking(db)
    account = FinancialAccount(code='BANK', name='Bank', account_type='bank', current_balance=4500-refund)
    db.add(account); db.flush()
    tx = MoneyTransaction(financial_account_id=account.id, amount=4500, direction='in', status='posted')
    db.add(tx); db.flush()
    folio = BookingFolio(booking=booking, folio_no='F-1')
    db.add(folio); db.flush()
    receivable = Receivable(source_type='booking', source_id=booking.id, receivable_type='guest_balance',
                            gross_amount=9000, amount_collected=4500-refund, balance_due=4500+refund)
    db.add(receivable)
    db.add_all([
        BookingFolioLine(folio=folio, line_type='room_charge', amount=9000, external_source='beds24'),
        BookingFolioLine(folio=folio, line_type='deposit', amount=4500, linked_money_transaction_id=tx.id, external_source='beds24'),
    ])
    if refund:
        refund_tx = MoneyTransaction(financial_account_id=account.id, amount=refund, direction='out', status='posted')
        db.add(refund_tx); db.flush()
        db.add(BookingFolioLine(folio=folio, line_type='refund', amount=refund, linked_money_transaction_id=refund_tx.id))
    if fee:
        db.add(BookingFolioLine(folio=folio, line_type='cancellation_fee', amount=fee))
    db.commit()
    history = {model: [columns(r) for r in db.query(model).all()] for model in [MoneyTransaction, FinancialAccount, BookingFolioLine]}
    cancellation.apply_beds24_cancellation(db, payload()); db.commit()
    cancellation.neutralize_cancelled_beds24_bookings(db, beds24_booking_ids=['93138380'])
    for model, before in history.items():
        assert [columns(r) for r in db.query(model).all()] == before
    assert (receivable.gross_amount, receivable.amount_collected, receivable.balance_due) == (9000, 4500-refund, 0)
    assert receivable.status == 'written_off'
    assert (booking.gross_amount, booking.deposit_amount) == (9000, 4500)
    totals = folio_balance_summary(folio)
    assert totals['balance'] == 0
    assert totals['cancelled_stay_amount'] == 9000
    assert totals['refunds'] == refund
    assert totals['cancellation_fees'] == fee
    assert totals['unallocated_payments'] == unallocated
    assert _serialize_booking(booking)['balance_due'] == 0
    from app.services.cashflow_service import _update_receivable_balance
    _update_receivable_balance(db, receivable.id)
    assert receivable.balance_due == 0
    assert receivable.amount_collected == 4500-refund


def test_no_payment_naturally_has_zero_collected_and_zero_due(db):
    booking = setup_booking(db)
    receivable = Receivable(source_type='booking', source_id=booking.id, gross_amount=9000, amount_collected=0, balance_due=9000)
    db.add(receivable); db.commit()
    cancellation.apply_beds24_cancellation(db, payload()); db.commit()
    assert (receivable.gross_amount, receivable.amount_collected, receivable.balance_due) == (9000, 0, 0)


def test_cancellation_fee_receivable_is_not_written_off(db):
    booking = setup_booking(db)
    fee = Receivable(source_type='booking', source_id=booking.id, receivable_type='cancellation_fee', gross_amount=500, balance_due=500)
    db.add(fee); db.commit()
    cancellation.apply_beds24_cancellation(db, payload()); db.commit()
    assert fee.balance_due == 500
    assert db.query(Receivable).filter(cancellation.ordinary_receivable_condition()).one().id == fee.id


def test_cancelled_inhouse_removed_from_dashboard_occupancy_revenue_and_ota(db, monkeypatch):
    from app.api import dashboard
    from app.api.channel_reconciliation import payout_bookings
    from app.api.reports import _build_management_report
    booking = setup_booking(db, status='checked_in')
    monkeypatch.setattr(dashboard, 'business_today', lambda: '2026-09-16')
    before = dashboard.summary(db=db, user=SimpleNamespace(id=1, role='admin'))
    assert before['in_house_guests'] == 1
    cancellation.apply_beds24_cancellation(db, payload()); db.commit()
    after = dashboard.summary(db=db, user=SimpleNamespace(id=1, role='admin'))
    assert after['in_house_guests'] == 0
    assert after['occupancy_rate'] == 0
    assert after['room_revenue_today'] == 0
    assert after['top_channels'] == []
    assert payout_bookings(channel_id=booking.channel_id, search='', db=db, user=SimpleNamespace(id=1, role='admin')) == []
    report = _build_management_report(db, start_date='2026-09-16', end_date='2026-09-19')
    assert report['rooms']['revenue_by_room_type'] == []


@pytest.mark.parametrize('wrong', [{'roomId': 999}, {'arrival': '2026-09-15'}, {'propertyId': 999}])
def test_mismatched_record_stops_without_changes(db, wrong):
    booking = setup_booking(db)
    with pytest.raises(ValueError, match='differs'):
        cancellation.apply_beds24_cancellation(db, payload(**wrong))
    assert booking.status == 'confirmed'


def test_unlinked_cancelled_booking_is_not_imported(db):
    assert cancellation.apply_beds24_cancellation(db, payload())['action'] == 'not_linked'
    assert db.query(Booking).count() == 0


def test_exact_id_api_response_required(db, monkeypatch):
    booking = setup_booking(db)
    monkeypatch.setattr(cancellation, 'fetch_beds24_bookings', lambda *a, **k: ([payload(id=999)], {}, {}))
    with pytest.raises(ValueError, match='exact'):
        cancellation.refresh_beds24_cancellation(db, '93138380')
    assert booking.status == 'confirmed'


def test_missing_webhook_id_never_bulk_syncs(db, monkeypatch):
    monkeypatch.setattr(sync, 'load_beds24_settings', lambda db: {'webhook_enabled': True})
    monkeypatch.setattr(sync, 'sync_recent_bookings', lambda *a, **k: pytest.fail('Unrelated bulk sync attempted'))
    with pytest.raises(ValueError, match='no booking ID'):
        sync.sync_from_webhook(db, {})


def test_empty_cleanup_scope_does_not_write_off_other_bookings(db):
    booking = setup_booking(db, status='cancelled')
    row = Receivable(source_type='booking', source_id=booking.id, gross_amount=9000, balance_due=9000)
    db.add(row); db.commit()
    cancellation.neutralize_cancelled_beds24_bookings(db, beds24_booking_ids=[])
    assert row.balance_due == 9000


def test_webhook_ids_accept_form_names_and_ignore_invoice_guest_ids():
    assert sync.extract_webhook_booking_ids({'bookid': '93138380'}) == ['93138380']
    assert sync.extract_webhook_booking_ids({'booking_ids': ['93138380', '93050886']}) == ['93050886', '93138380']
    assert sync.extract_webhook_booking_ids({'id': 93138380, 'guest': {'id': 12}, 'invoiceItems': [{'id': 456}]}) == ['93138380']


def test_form_webhook_is_parsed_without_broad_fallback(db, monkeypatch):
    import asyncio
    from starlette.requests import Request
    from app.api import integrations_beds24 as api
    seen = []
    def fake_sync(db, payload, **kwargs):
        seen.append(payload)
        return {'booking_ids': [], 'results': [], 'failed': 0}
    monkeypatch.setattr(api, 'sync_from_webhook', fake_sync)
    async def receive():
        return {'type': 'http.request', 'body': b'bookid=93138380&status=0'}
    request = Request({'type': 'http', 'headers': [(b'content-type', b'application/x-www-form-urlencoded')], 'query_string': b''}, receive)
    asyncio.run(api.beds24_webhook(request, db=db))
    assert seen == [{'bookid': '93138380', 'status': '0'}]


def test_synthetic_ota_settlement_is_not_treated_as_cash_or_retention(db):
    booking = setup_booking(db, status='cancelled')
    folio = BookingFolio(booking=booking, folio_no='SYNTH')
    db.add(folio); db.flush()
    db.add_all([
        BookingFolioLine(folio=folio, line_type='room_charge', amount=9000),
        BookingFolioLine(folio=folio, line_type='deposit', amount=9000, external_source='beds24', external_line_key='beds24:93138380:prepaid_settlement'),
    ])
    db.commit()
    totals = folio_balance_summary(folio)
    assert totals['balance'] == 0
    assert totals['payments'] == 9000  # preserved imported history
    assert totals['actual_net_payments'] == 0
    assert totals['unallocated_payments'] == 0


def test_unpaid_cancellation_fee_survives_in_same_guest_receivable(db):
    booking = setup_booking(db)
    folio = BookingFolio(booking=booking, folio_no='F-FEE')
    db.add(folio); db.flush()
    db.add_all([
        BookingFolioLine(folio=folio, line_type='room_charge', amount=9000),
        BookingFolioLine(folio=folio, line_type='cancellation_fee', amount=1000),
    ])
    receivable = Receivable(source_type='booking', source_id=booking.id, gross_amount=10000, amount_collected=0, balance_due=10000)
    db.add(receivable); db.commit()
    cancellation.apply_beds24_cancellation(db, payload()); db.commit()
    assert receivable.balance_due == 1000
    assert receivable.gross_amount == 10000
    assert receivable.amount_collected == 0
    assert folio_balance_summary(folio)['balance'] == 1000
    from app.services.cashflow_service import _update_receivable_balance
    _update_receivable_balance(db, receivable.id)
    assert receivable.balance_due == 1000
