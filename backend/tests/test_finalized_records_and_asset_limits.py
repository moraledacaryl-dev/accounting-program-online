from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from app.api import asset_registry, reconciliations, room_folios
from app.db.database import Base
from app.models.entities import (
    Asset, AssetDepreciationLog, AssetDisposalLog, Booking, BookingFolio,
    BookingFolioLine, CashReconciliation, FinancialAccount, JournalEntry,
    JournalLine, Record,
)
from app.schemas.cashflow import CashReconciliationCreate, CashflowActionPayload
from app.schemas.common import AssetDepreciationCreate, AssetDisposalCreate
from app.schemas.guests import (
    BookingFolioAction, BookingFolioLineReverse, BookingFolioLineTransfer,
    BookingFolioLineUpdate,
)
from app.services.cashflow_service import create_cash_reconciliation
from app.services.guest_service import folio_balance_summary, set_folio_status

USER = SimpleNamespace(username='regression-reviewer', role='owner')


@pytest.fixture
def db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, autoflush=False)() as session:
        yield session
    engine.dispose()


def reconciliation_payload(db, **changes):
    account = FinancialAccount(name='Test drawer', code='TEST-DRAWER', account_type='cash_drawer',
                               opening_balance=0, current_balance=0)
    db.add(account)
    db.commit()
    return CashReconciliationCreate(financial_account_id=account.id,
        reconciliation_date='2026-11-01', shift_name='day', actual_counted=0,
        status='closed', notes='Original close',
        lines=[{'line_label': 'Original count', 'amount': 0}], **changes)


@pytest.mark.parametrize('entrypoint', ['post', 'put', 'legacy_service'])
def test_closed_reconciliation_cannot_be_overwritten(db, entrypoint):
    payload = reconciliation_payload(db)
    original = reconciliations.add_reconciliation(payload, db=db, user=USER)
    attempted = payload.model_copy(update={'status': 'counted', 'actual_counted': 99,
                                           'notes': 'Overwrite', 'lines': []})
    if entrypoint == 'legacy_service':
        with pytest.raises(ValueError, match='[Cc]losed'):
            create_cash_reconciliation(db, attempted, username=USER.username)
        db.rollback()
    else:
        with pytest.raises(HTTPException) as rejected:
            if entrypoint == 'post':
                reconciliations.add_reconciliation(attempted, db=db, user=USER)
            else:
                reconciliations.edit_reconciliation(original['id'], attempted, db=db, user=USER)
        assert rejected.value.status_code == 400
    db.expire_all()
    row = db.get(CashReconciliation, original['id'])
    assert row.status == 'closed' and row.locked_at
    assert float(row.actual_counted) == 0
    assert row.notes == 'Original close'
    assert [line.line_label for line in row.lines] == ['Original count']


def test_reversed_reconciliation_can_be_corrected_and_closed_again(db):
    payload = reconciliation_payload(db)
    original = reconciliations.add_reconciliation(payload, db=db, user=USER)
    reconciliations.reverse_reconciliation(original['id'], CashflowActionPayload(reason='Recount'), db=db, user=USER)
    corrected = reconciliations.edit_reconciliation(original['id'], payload.model_copy(update={
        'status': 'counted', 'actual_counted': 25, 'notes': 'Documented variance',
    }), db=db, user=USER)
    assert corrected['status'] == 'counted' and corrected['actual_counted'] == 25
    closed = reconciliations.close_reconciliation(original['id'], CashflowActionPayload(), db=db, user=USER)
    assert closed['status'] == 'closed' and closed['locked_at']


def make_folio(db, status='settled'):
    booking = Booking(guest_name='Synthetic guest', check_in='2026-11-01', check_out='2026-11-02')
    db.add(booking); db.flush()
    folio = BookingFolio(booking_id=booking.id, folio_no=f'FOLIO-{booking.id}', status=status)
    db.add(folio); db.flush()
    charge = BookingFolioLine(folio_id=folio.id, line_type='room_charge', description='Room',
                             quantity=1, unit_price=100, amount=100)
    payment = BookingFolioLine(folio_id=folio.id, line_type='payment', description='Paid', amount=100)
    db.add_all([charge, payment]); db.commit()
    return folio, charge


@pytest.mark.parametrize('status', ['settled', 'closed', 'cancelled'])
@pytest.mark.parametrize('action', ['edit', 'reverse', 'transfer'])
def test_finalized_folio_lines_require_reopening(db, status, action):
    folio, charge = make_folio(db, status)
    target, _ = make_folio(db, 'open')
    original_count = db.query(BookingFolioLine).count()
    with pytest.raises(HTTPException) as rejected:
        if action == 'edit':
            room_folios.edit_room_folio_line(charge.id, BookingFolioLineUpdate(amount=200), db=db, user=USER)
        elif action == 'reverse':
            room_folios.reverse_room_folio_line(charge.id, BookingFolioLineReverse(reason='Correction'), db=db, user=USER)
        else:
            room_folios.transfer_room_folio_line(charge.id, BookingFolioLineTransfer(target_folio_id=target.id), db=db, user=USER)
    assert rejected.value.status_code == 400
    db.expire_all()
    assert db.get(BookingFolio, folio.id).status == status
    assert folio_balance_summary(db.get(BookingFolio, folio.id))['balance'] == 0
    assert float(db.get(BookingFolioLine, charge.id).amount) == 100
    assert db.query(BookingFolioLine).count() == original_count


def test_explicitly_reopened_folio_still_allows_line_correction(db):
    folio, charge = make_folio(db)
    set_folio_status(db, folio.id, BookingFolioAction(status='reopened'))
    room_folios.edit_room_folio_line(charge.id, BookingFolioLineUpdate(quantity=2), db=db, user=USER)
    db.expire_all()
    assert folio_balance_summary(db.get(BookingFolio, folio.id))['balance'] == 100
    assert db.get(BookingFolio, folio.id).status == 'reopened'


def test_open_folio_charge_transfer_preserves_combined_balance(db):
    source, charge = make_folio(db, 'open')
    target, _ = make_folio(db, 'open')
    room_folios.transfer_room_folio_line(charge.id, BookingFolioLineTransfer(target_folio_id=target.id), db=db, user=USER)
    db.expire_all()
    assert folio_balance_summary(db.get(BookingFolio, source.id))['balance'] == -100
    assert folio_balance_summary(db.get(BookingFolio, target.id))['balance'] == 100


def make_asset(db, **changes):
    values = dict(name='Synthetic equipment', acquisition_cost=100, salvage_value=10,
                  useful_life_months=3, operational_status='Active')
    values.update(changes)
    asset = Asset(**values)
    db.add(asset); db.commit()
    return asset


@pytest.mark.parametrize('reset_status', [False, True])
def test_asset_disposal_cannot_duplicate_posted_proceeds(db, reset_status):
    asset = make_asset(db)
    payload = AssetDisposalCreate(disposal_date='2026-11-01', proceeds_amount=50, auto_post_accounting=True)
    asset_registry.dispose_asset(asset.id, payload, db=db, user=USER)
    if reset_status:
        asset.operational_status = 'Active'
        db.commit()
    with pytest.raises(HTTPException) as rejected:
        asset_registry.dispose_asset(asset.id, payload, db=db, user=USER)
    assert rejected.value.status_code == 409
    db.rollback()
    assert db.query(AssetDisposalLog).count() == 1
    assert db.query(Record).count() == db.query(JournalEntry).count() == 1
    assert float(db.query(func.sum(JournalLine.debit)).scalar()) == 50


@pytest.mark.parametrize('batch', [False, True])
def test_automatic_depreciation_caps_last_posting_at_remaining_value(db, batch):
    asset = make_asset(db)
    db.add(AssetDepreciationLog(asset_id=asset.id, period_key='2026-09', amount=80))
    db.commit()
    payload = AssetDepreciationCreate(period_key='2026-10', auto_post_accounting=True)
    result = (asset_registry.depreciate_batch(payload, db=db, user=USER) if batch else
              asset_registry.depreciate_asset(asset.id, payload, db=db, user=USER))
    log = result['created'][0] if batch else result
    assert float(log['amount']) == 10
    assert float(db.query(func.sum(AssetDepreciationLog.amount)).scalar()) == 90
    assert float(db.query(func.sum(JournalLine.debit)).scalar()) == 10
    next_payload = payload.model_copy(update={'period_key': '2026-11'})
    if batch:
        result = asset_registry.depreciate_batch(next_payload, db=db, user=USER)
        assert result['created'] == [] and result['skipped'][0]['reason'] == 'fully_depreciated'
    else:
        with pytest.raises(HTTPException) as rejected:
            asset_registry.depreciate_asset(asset.id, next_payload, db=db, user=USER)
        assert rejected.value.status_code == 400
        db.rollback()
    assert db.query(AssetDepreciationLog).count() == 2
    assert db.query(JournalEntry).count() == 1


@pytest.mark.parametrize('batch', [False, True])
def test_excess_manual_depreciation_rejects_without_partial_postings(db, batch):
    # In batch mode the first asset accepts 50; the second cannot. Neither may post.
    first = make_asset(db, acquisition_cost=200)
    second = make_asset(db, acquisition_cost=40)
    payload = AssetDepreciationCreate(period_key='2026-11', amount=50, auto_post_accounting=True)
    with pytest.raises(HTTPException) as rejected:
        if batch:
            asset_registry.depreciate_batch(payload, db=db, user=USER)
        else:
            asset_registry.depreciate_asset(second.id, payload, db=db, user=USER)
    assert rejected.value.status_code == 400
    db.rollback()
    assert db.query(AssetDepreciationLog).count() == 0
    assert db.query(Record).count() == db.query(JournalEntry).count() == 0


def test_valid_manual_depreciation_and_duplicate_period_behavior_remain(db):
    asset = make_asset(db)
    payload = AssetDepreciationCreate(period_key='2026-11', amount=12.3456, auto_post_accounting=True)
    result = asset_registry.depreciate_asset(asset.id, payload, db=db, user=USER)
    assert float(result['amount']) == 12.3456
    with pytest.raises(HTTPException) as rejected:
        asset_registry.depreciate_asset(asset.id, payload, db=db, user=USER)
    assert rejected.value.status_code == 400
    db.rollback()
    assert db.query(AssetDepreciationLog).count() == 1
    assert db.query(JournalEntry).count() == 1


def test_disposed_asset_cannot_be_depreciated(db):
    asset = make_asset(db)
    asset_registry.dispose_asset(asset.id, AssetDisposalCreate(), db=db, user=USER)
    payload = AssetDepreciationCreate(period_key='2026-11', auto_post_accounting=True)
    with pytest.raises(HTTPException) as rejected:
        asset_registry.depreciate_asset(asset.id, payload, db=db, user=USER)
    assert rejected.value.status_code == 400
    db.rollback()
    assert db.query(AssetDepreciationLog).count() == 0


def test_disposal_posting_failure_does_not_mark_asset_disposed(db, monkeypatch):
    asset = make_asset(db)
    def fail(*args, **kwargs):
        raise ValueError('Synthetic posting failure')
    monkeypatch.setattr(asset_registry, 'create_approved_record', fail)
    with pytest.raises(HTTPException):
        asset_registry.dispose_asset(asset.id, AssetDisposalCreate(proceeds_amount=50,
            auto_post_accounting=True), db=db, user=USER)
    db.expire_all()
    assert db.get(Asset, asset.id).operational_status == 'Active'
    assert db.query(AssetDisposalLog).count() == 0
