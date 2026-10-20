"""Settlement integrity: exact amounts, replay safety, RBAC and rollback."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import reports
from app.db.database import Base
from app.models.entities import JournalEntry, MoneyTransaction, Record, RecordSettlement
from app.models.mutation_idempotency import MutationIdempotency
from app.schemas.common import RecordSettlementCreate
from app.services import record_settlement_atomicity_service as atomic


OWNER = SimpleNamespace(username='audit-owner', role='owner')


@pytest.fixture
def db():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session
    engine.dispose()


def record(db, *, direction='income', amount=100, status='approved', payment_method='on_account'):
    row = Record(
        module_slug='events', module_name='Events', category='Venue',
        bucket='Rental', item='Service', name='Example invoice',
        amount=amount, direction=direction, workflow_status=status,
        payment_method=payment_method, transaction_date='2026-10-01',
    )
    db.add(row)
    db.commit()
    return row


def payload(row, *, amount=30, reference='REF-001', day='2026-10-20'):
    return RecordSettlementCreate(
        record_id=row.id, amount=amount, reference_no=reference,
        settlement_date=day, payment_method='bank_transfer',
    )


def post(db, row, *, key='group2-idempotency-0001', **changes):
    return reports.create_settlement(
        payload=payload(row, **changes),
        idempotency_key=key, db=db, user=OWNER,
    )


def test_replay_preserves_result_and_does_not_duplicate_or_post_cash(db):
    row = record(db)
    first = post(db, row)
    assert first['outstanding_before'] == 100
    assert first['outstanding_after'] == 70
    assert first['replayed'] is False
    assert first['posting_effect'] == 'settlement_evidence_only'

    second = post(db, row)
    assert second['replayed'] is True
    assert second['settlement']['id'] == first['settlement']['id']
    assert second['outstanding_before'] == first['outstanding_before']
    assert second['outstanding_after'] == first['outstanding_after']
    assert db.query(RecordSettlement).count() == 1
    assert db.query(MutationIdempotency).count() == 1
    assert db.query(MoneyTransaction).count() == 0
    assert db.query(JournalEntry).count() == 0

    third = post(db, row, key='group2-idempotency-0002', reference='REF-002', amount=20)
    replay = post(db, row)
    assert third['outstanding_after'] == 50
    assert replay['outstanding_after'] == 70  # Original historical result.


def test_same_idempotency_key_with_changed_payload_is_conflict(db):
    row = record(db)
    post(db, row)
    with pytest.raises(HTTPException) as err:
        post(db, row, amount=31)
    assert err.value.status_code == 409
    assert db.query(RecordSettlement).count() == 1


def test_missing_or_short_idempotency_key_is_rejected_without_writes(db):
    row = record(db)
    for key in (None, 'short'):
        with pytest.raises(HTTPException) as err:
            post(db, row, key=key)
        assert err.value.status_code == 400
    assert db.query(RecordSettlement).count() == 0
    assert db.query(MutationIdempotency).count() == 0


def test_overpayment_and_fully_settled_invoice_rejected(db):
    row = record(db)
    post(db, row, amount=75)
    with pytest.raises(HTTPException) as err:
        post(db, row, key='group2-overpay-0002', reference='REF-002', amount=26)
    assert err.value.status_code == 409
    assert db.query(RecordSettlement).count() == 1
    assert db.query(MutationIdempotency).count() == 1

    post(db, row, key='group2-overpay-0003', reference='REF-003', amount=25)
    with pytest.raises(HTTPException) as err:
        post(db, row, key='group2-overpay-0004', reference='REF-004', amount=1)
    assert err.value.status_code == 409
    assert db.query(RecordSettlement).count() == 2


def test_duplicate_reference_different_key_is_rejected(db):
    row = record(db)
    post(db, row)
    with pytest.raises(HTTPException) as err:
        post(db, row, key='group2-different-key', reference=' ref-001 ', amount=15)
    assert err.value.status_code == 409
    assert 'reference' in str(err.value.detail).lower()
    assert db.query(RecordSettlement).count() == 1


def test_invalid_record_states_amount_precision_and_dates_rollback(db):
    draft = record(db, status='draft')
    immediate = record(db, payment_method='cash')
    normal = record(db)
    cases = [
        (draft, {}, 'group2-draft-record'),
        (immediate, {}, 'group2-noncredit-record'),
        (normal, {'amount': -1}, 'group2-negative-pay'),
        (normal, {'amount': 0.00001}, 'group2-too-precise'),
        (normal, {'day': '2026-02-30'}, 'group2-invalid-date'),
    ]
    for row, changes, key in cases:
        with pytest.raises(HTTPException) as err:
            post(db, row, key=key, **changes)
        assert err.value.status_code == 400
    assert db.query(RecordSettlement).count() == 0
    assert db.query(MutationIdempotency).count() == 0


def test_locked_period_or_late_failure_rolls_back_reservation(db, monkeypatch):
    row = record(db)
    def blocked(*args, **kwargs):
        raise ValueError('BIR period locked')
    monkeypatch.setattr(atomic, 'ensure_date_unlocked', blocked)
    with pytest.raises(HTTPException) as err:
        post(db, row)
    assert err.value.status_code == 400
    assert db.query(RecordSettlement).count() == 0
    assert db.query(MutationIdempotency).count() == 0


@pytest.mark.parametrize(('direction', 'permissions', 'allowed'), [
    ('income', {'cashflow.money_in'}, True),
    ('income', {'cashflow.money_out'}, False),
    ('expense', {'cashflow.money_out'}, True),
    ('expense', {'cashflow.money_in'}, False),
    ('asset', {'cashflow.money_in'}, False),
    ('asset', {'cashflow.money_in', 'cashflow.money_out'}, True),
])
def test_settlement_direction_permissions(db, monkeypatch, direction, permissions, allowed):
    row = record(db, direction=direction)
    monkeypatch.setattr(reports, 'get_user_permission_keys', lambda *_: permissions)
    user = SimpleNamespace(username='finance-user', role='cashier')
    kwargs = dict(payload=payload(row), idempotency_key=f'group2-{direction}-permissions', db=db, user=user)
    if allowed:
        assert reports.create_settlement(**kwargs)['outstanding_after'] == 70
    else:
        with pytest.raises(HTTPException) as err:
            reports.create_settlement(**kwargs)
        assert err.value.status_code == 403
        assert db.query(RecordSettlement).count() == 0


def test_decimal_precision_prevents_partial_peso_drift(db):
    row = record(db, amount=0.3)
    post(db, row, amount=0.1)
    post(db, row, amount=0.1, reference='REF-002', key='group2-decimal-0002')
    result = post(db, row, amount=0.1, reference='REF-003', key='group2-decimal-0003')
    assert result['outstanding_after'] == 0
    assert db.query(RecordSettlement).count() == 3
