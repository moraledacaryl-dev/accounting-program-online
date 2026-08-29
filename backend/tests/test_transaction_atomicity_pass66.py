from __future__ import annotations

import inspect

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.entities import EventPayment, FinancialAccount, JournalEntry, MoneyTransaction, Receivable
from app.schemas.events import EventActionPayload, EventBookingPayload, EventLinePayload, EventPaymentPayload
from app.services import event_service, procurement_service
from app.services.cashflow_service import ensure_default_financial_accounts
from app.services.event_service import confirm_event, create_event, record_event_payment


def make_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    return TestingSession()


def test_event_payment_late_failure_rolls_back_cash_receivable_and_payment(monkeypatch):
    db = make_session()
    ensure_default_financial_accounts(db)
    account = db.query(FinancialAccount).filter(FinancialAccount.code == 'BNK-01').one()

    event = create_event(
        db,
        EventBookingPayload(
            event_name='Pass 66 Atomic Event',
            client_name='Atomicity Client',
            event_date='2026-08-29',
            lines=[
                EventLinePayload(
                    line_type='package',
                    description='Atomicity package',
                    quantity=1,
                    unit_price=5000,
                )
            ],
        ),
        username='pass66',
    )
    confirmed = confirm_event(
        db,
        event['id'],
        EventActionPayload(action_date='2026-08-29'),
        username='pass66',
    )

    receivable_id = confirmed['receivable_id']
    receivable = db.get(Receivable, receivable_id)
    opening_account = float(account.current_balance or 0)
    opening_collected = float(receivable.amount_collected or 0)
    opening_due = float(receivable.balance_due or 0)

    def fail_after_collection(*args, **kwargs):
        raise RuntimeError('pass66 late event journal failure')

    monkeypatch.setattr(event_service, '_post_event_payment_journal', fail_after_collection)

    with pytest.raises(RuntimeError, match='pass66 late event journal failure'):
        record_event_payment(
            db,
            event['id'],
            EventPaymentPayload(
                payment_date='2026-08-29',
                amount=2000,
                financial_account_id=account.id,
                payment_method='bank_transfer',
                reference_no='PASS66-FAIL',
            ),
            username='pass66',
        )

    db.rollback()
    db.expire_all()

    account_after = db.get(FinancialAccount, account.id)
    receivable_after = db.get(Receivable, receivable_id)

    assert float(account_after.current_balance or 0) == opening_account
    assert float(receivable_after.amount_collected or 0) == opening_collected
    assert float(receivable_after.balance_due or 0) == opening_due
    assert db.query(EventPayment).count() == 0
    assert db.query(MoneyTransaction).filter(MoneyTransaction.receivable_id == receivable_id).count() == 0
    assert db.query(JournalEntry).filter(JournalEntry.reference_no.like('EVTPAY-%')).count() == 0


def test_nested_financial_helpers_are_explicitly_non_committing_in_composite_workflows():
    event_payment_source = inspect.getsource(event_service.record_event_payment)
    event_receivable_source = inspect.getsource(event_service._sync_event_receivable)
    receiving_source = inspect.getsource(procurement_service._maybe_create_payable_from_receiving)

    assert 'confirm_event(' in event_payment_source and 'commit=False' in event_payment_source
    assert 'collect_receivable(' in event_payment_source and 'commit=False' in event_payment_source
    assert 'create_receivable(' in event_receivable_source and 'commit=False' in event_receivable_source
    assert 'create_payable(' in receiving_source and 'commit=False' in receiving_source
