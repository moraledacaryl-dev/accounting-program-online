from concurrent.futures import ThreadPoolExecutor
from threading import Event, get_ident
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import event, func

from app.api.asset_registry import depreciate_asset, dispose_asset
from app.db.database import SessionLocal, engine
from app.models.entities import (
    Asset, AssetDepreciationLog, AssetDisposalLog, Booking, BookingFolio,
    BookingFolioLine, CashReconciliation, FinancialAccount,
)
from app.schemas.cashflow import CashReconciliationCreate, CashflowActionPayload
from app.schemas.common import AssetDepreciationCreate, AssetDisposalCreate
from app.schemas.guests import BookingFolioLineUpdate, BookingFolioSettlement
from app.services.cashflow_service import close_cash_reconciliation, update_cash_reconciliation
from app.services.guest_service import settle_folio, update_folio_line
from app.services.reconciliation_atomicity_service import create_cash_reconciliation_uncommitted

pytestmark = pytest.mark.skipif(engine.dialect.name != 'postgresql', reason='PostgreSQL CI lane only')
USER = SimpleNamespace(username='finalized-record-ci', role='owner')


def _overlap(first, second, preload, written_table):
    """Make request two hold stale data before request one writes and commits.

    The second request must wait for the first row lock and refresh its cached
    state before applying business validation. Events bound the overlap; no sleeps.
    """
    second_loaded, first_written, second_locking = Event(), Event(), Event()
    threads = {}

    def observe_after(_conn, _cursor, statement, _params, _context, _many):
        sql = statement.strip().lower()
        if get_ident() == threads.get('first') and sql.startswith((f'insert into {written_table}', f'update {written_table}')):
            first_written.set()
            assert second_locking.wait(10), 'Second request did not attempt its row lock'

    def observe_before(_conn, _cursor, statement, _params, _context, _many):
        if get_ident() == threads.get('second') and 'for update' in statement.lower():
            second_locking.set()

    def run_first():
        threads['first'] = get_ident()
        assert second_loaded.wait(10)
        with SessionLocal() as db:
            return first(db)

    def run_second():
        threads['second'] = get_ident()
        with SessionLocal() as db:
            cached = preload(db)  # Retain strong references in SQLAlchemy's identity map.
            second_loaded.set()
            assert first_written.wait(10)
            try:
                return second(db)
            finally:
                db.rollback()
                assert cached

    event.listen(engine, 'after_cursor_execute', observe_after)
    event.listen(engine, 'before_cursor_execute', observe_before)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            one, two = pool.submit(run_first), pool.submit(run_second)
            result = one.result(timeout=30)
            try:
                return result, two.result(timeout=30)
            except (ValueError, HTTPException) as exc:
                return result, exc
    finally:
        event.remove(engine, 'after_cursor_execute', observe_after)
        event.remove(engine, 'before_cursor_execute', observe_before)


def test_concurrent_asset_disposal_posts_only_once_with_stale_session():
    marker = uuid4().hex[:12]
    with SessionLocal() as db:
        asset = Asset(name=f'Disposal race {marker}', acquisition_cost=100)
        db.add(asset); db.commit(); asset_id = asset.id
    payload = AssetDisposalCreate(disposal_date='2026-11-01', proceeds_amount=50, auto_post_accounting=True)
    first, second = _overlap(
        lambda db: dispose_asset(asset_id, payload, db=db, user=USER),
        lambda db: dispose_asset(asset_id, payload, db=db, user=USER),
        lambda db: [db.get(Asset, asset_id)], 'asset_disposal_logs',
    )
    assert first['id']
    assert isinstance(second, HTTPException) and second.status_code == 409
    with SessionLocal() as db:
        assert db.query(AssetDisposalLog).filter_by(asset_id=asset_id).count() == 1


def test_concurrent_depreciation_cannot_exceed_remaining_value():
    marker = uuid4().hex[:12]
    with SessionLocal() as db:
        asset = Asset(name=f'Depreciation race {marker}', acquisition_cost=100, salvage_value=10, useful_life_months=3)
        db.add(asset); db.commit(); asset_id = asset.id
    one = AssetDepreciationCreate(period_key='2026-10', amount=60, auto_post_accounting=True)
    two = one.model_copy(update={'period_key': '2026-11'})
    first, second = _overlap(
        lambda db: depreciate_asset(asset_id, one, db=db, user=USER),
        lambda db: depreciate_asset(asset_id, two, db=db, user=USER),
        lambda db: [db.get(Asset, asset_id)], 'asset_depreciation_logs',
    )
    assert float(first['amount']) == 60
    assert isinstance(second, HTTPException) and second.status_code == 400
    with SessionLocal() as db:
        assert float(db.query(func.sum(AssetDepreciationLog.amount)).filter_by(asset_id=asset_id).scalar()) == 60
        assert db.query(AssetDepreciationLog).filter_by(asset_id=asset_id).count() == 1


@pytest.mark.parametrize('upsert', [False, True])
def test_concurrent_reconciliation_close_prevents_stale_overwrite(upsert):
    marker = uuid4().hex[:12]
    with SessionLocal() as db:
        account = FinancialAccount(name=f'Close race {marker}', code=f'CLOSE-{marker}', account_type='cash_drawer',
                                   opening_balance=0, current_balance=0)
        db.add(account); db.flush()
        row = CashReconciliation(financial_account_id=account.id, reconciliation_date='2026-11-01',
                                 status='counted', actual_counted=0, variance=0)
        db.add(row); db.commit(); row_id, account_id = row.id, account.id
    attempted = CashReconciliationCreate(financial_account_id=account_id, reconciliation_date='2026-11-01',
                                        status='counted', actual_counted=99)
    def overwrite(db):
        if upsert:
            result = create_cash_reconciliation_uncommitted(db, attempted, username=USER.username)
            db.commit()
            return result
        return update_cash_reconciliation(db, row_id, attempted, username=USER.username)
    first, second = _overlap(
        lambda db: close_cash_reconciliation(db, row_id, CashflowActionPayload(), username=USER.username),
        overwrite, lambda db: [db.get(CashReconciliation, row_id)], 'cash_reconciliations',
    )
    assert first['status'] == 'closed'
    assert isinstance(second, ValueError) and 'Closed' in str(second)
    with SessionLocal() as db:
        row = db.get(CashReconciliation, row_id)
        assert row.status == 'closed' and row.locked_at and float(row.actual_counted) == 0


def test_concurrent_folio_settlement_prevents_stale_line_edit():
    marker = uuid4().hex[:12]
    with SessionLocal() as db:
        booking = Booking(guest_name=f'Settlement race {marker}')
        db.add(booking); db.flush()
        folio = BookingFolio(booking_id=booking.id, folio_no=f'RACE-{marker}', status='open')
        db.add(folio); db.flush()
        charge = BookingFolioLine(folio_id=folio.id, line_type='room_charge', description='Room', amount=100)
        db.add_all([charge, BookingFolioLine(folio_id=folio.id, line_type='payment', description='Paid', amount=100)])
        db.commit(); folio_id, line_id = folio.id, charge.id
    first, second = _overlap(
        lambda db: settle_folio(db, folio_id, BookingFolioSettlement()),
        lambda db: update_folio_line(db, line_id, BookingFolioLineUpdate(amount=200)),
        lambda db: [db.get(BookingFolio, folio_id), db.get(BookingFolioLine, line_id)], 'booking_folios',
    )
    assert first['status'] == 'settled'
    assert isinstance(second, ValueError) and 'Reopen' in str(second)
    with SessionLocal() as db:
        assert db.get(BookingFolio, folio_id).status == 'settled'
        assert float(db.get(BookingFolioLine, line_id).amount) == 100
