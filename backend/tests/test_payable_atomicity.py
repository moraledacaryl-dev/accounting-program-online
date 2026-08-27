from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.payables import add_payable, pay_payable_balance
from app.db.database import Base
from app.models.entities import FinancialAccount, MoneyTransaction, Payable
from app.models.mutation_idempotency import MutationIdempotency
from app.schemas.cashflow import PayableCreate, PayablePayPayload
from app.services.payable_atomicity_service import create_payable_idempotent


USER = SimpleNamespace(username='owner', role='owner')


def make_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    return TestingSession()


def payable_payload(**overrides):
    data = {
        'supplier_name': 'Pass 64 Supplier',
        'payable_type': 'supplier_bill',
        'bill_date': '2026-08-27',
        'due_date': '2026-09-15',
        'gross_amount': 1000,
        'amount_paid': 0,
        'status': 'open',
        'notes': 'Pass 64 payable atomicity test',
        'bir_include': False,
    }
    data.update(overrides)
    return PayableCreate(**data)


def test_payable_create_returns_success_after_commit_and_replay_does_not_duplicate():
    db = make_session()
    key = 'pass64-create-replay-0001'

    first = add_payable(
        payload=payable_payload(),
        background_tasks=BackgroundTasks(),
        idempotency_key=key,
        db=db,
        user=USER,
    )
    replay = add_payable(
        payload=payable_payload(),
        background_tasks=BackgroundTasks(),
        idempotency_key=key,
        db=db,
        user=USER,
    )

    assert first['id'] == replay['id']
    assert first['balance_due'] == 1000
    assert db.query(Payable).count() == 1
    assert db.query(MutationIdempotency).count() == 1


def test_payable_create_same_key_different_payload_is_conflict():
    db = make_session()
    key = 'pass64-create-conflict-0001'

    add_payable(
        payload=payable_payload(),
        background_tasks=BackgroundTasks(),
        idempotency_key=key,
        db=db,
        user=USER,
    )

    with pytest.raises(HTTPException) as exc_info:
        add_payable(
            payload=payable_payload(gross_amount=1250),
            background_tasks=BackgroundTasks(),
            idempotency_key=key,
            db=db,
            user=USER,
        )

    assert exc_info.value.status_code == 409
    assert 'different request' in str(exc_info.value.detail)
    assert db.query(Payable).count() == 1


def test_payable_create_rolls_back_without_partial_liability_or_idempotency_record():
    db = make_session()

    item, replayed = create_payable_idempotent(
        db,
        payable_payload(),
        'pass64-create-rollback-0001',
    )

    assert replayed is False
    assert item['id']
    assert db.query(Payable).count() == 1
    assert db.query(MutationIdempotency).count() == 1

    db.rollback()

    assert db.query(Payable).count() == 0
    assert db.query(MutationIdempotency).count() == 0


def test_payable_payment_replay_applies_cash_and_balance_effect_once():
    db = make_session()
    account = FinancialAccount(
        name='Pass 64 Bank',
        code='P64-BANK',
        account_type='bank',
        subtype='test',
        currency='PHP',
        is_active=True,
        requires_daily_reconciliation=False,
        reconciliation_mode='none',
        requires_physical_count=False,
        variance_tolerance=0,
        approval_required_on_variance=False,
        opening_balance=1000,
        current_balance=1000,
        department='finance',
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    payable = add_payable(
        payload=payable_payload(),
        background_tasks=BackgroundTasks(),
        idempotency_key='pass64-payment-create-0001',
        db=db,
        user=USER,
    )

    payment = PayablePayPayload(
        amount=250,
        payment_date='2026-08-27',
        financial_account_id=account.id,
        payment_method='bank_transfer',
        reference_no='PASS64-PAY-1',
        auto_post_accounting=False,
    )
    key = 'pass64-payment-replay-0001'

    first = pay_payable_balance(
        payable_id=payable['id'],
        payload=payment,
        idempotency_key=key,
        db=db,
        user=USER,
    )
    replay = pay_payable_balance(
        payable_id=payable['id'],
        payload=payment,
        idempotency_key=key,
        db=db,
        user=USER,
    )

    db.refresh(account)
    stored = db.get(Payable, payable['id'])

    assert replay['transaction']['id'] == first['transaction']['id']
    assert db.query(MoneyTransaction).filter(MoneyTransaction.payable_id == payable['id']).count() == 1
    assert float(stored.amount_paid or 0) == 250
    assert float(stored.balance_due or 0) == 750
    assert float(account.current_balance or 0) == 750


def test_payable_payment_same_key_different_amount_is_conflict_without_second_effect():
    db = make_session()
    account = FinancialAccount(
        name='Pass 64 Bank Conflict',
        code='P64-BANK-C',
        account_type='bank',
        subtype='test',
        currency='PHP',
        is_active=True,
        requires_daily_reconciliation=False,
        reconciliation_mode='none',
        requires_physical_count=False,
        variance_tolerance=0,
        approval_required_on_variance=False,
        opening_balance=1000,
        current_balance=1000,
        department='finance',
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    payable = add_payable(
        payload=payable_payload(),
        background_tasks=BackgroundTasks(),
        idempotency_key='pass64-payment-conflict-create',
        db=db,
        user=USER,
    )
    key = 'pass64-payment-conflict-0001'

    pay_payable_balance(
        payable_id=payable['id'],
        payload=PayablePayPayload(amount=100, financial_account_id=account.id),
        idempotency_key=key,
        db=db,
        user=USER,
    )

    with pytest.raises(HTTPException) as exc_info:
        pay_payable_balance(
            payable_id=payable['id'],
            payload=PayablePayPayload(amount=200, financial_account_id=account.id),
            idempotency_key=key,
            db=db,
            user=USER,
        )

    assert exc_info.value.status_code == 409
    db.refresh(account)
    stored = db.get(Payable, payable['id'])
    assert float(stored.amount_paid or 0) == 100
    assert float(stored.balance_due or 0) == 900
    assert float(account.current_balance or 0) == 900
    assert db.query(MoneyTransaction).filter(MoneyTransaction.payable_id == payable['id']).count() == 1


def test_payable_mutations_require_idempotency_key():
    db = make_session()

    with pytest.raises(HTTPException) as exc_info:
        add_payable(
            payload=payable_payload(),
            background_tasks=BackgroundTasks(),
            idempotency_key=None,
            db=db,
            user=USER,
        )

    assert exc_info.value.status_code == 400
    assert 'Idempotency-Key header is required' in str(exc_info.value.detail)
    assert db.query(Payable).count() == 0
