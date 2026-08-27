from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.business_clock import BUSINESS_TIMEZONE_NAME, business_now, business_today
from app.db.database import Base
from app.models.entities import FinancialAccount
from app.schemas import cashflow as cashflow_schemas
from app.schemas.cashflow import (
    AccountTransferCreate,
    CashflowActionPayload,
    CashflowSummaryQuery,
    MoneyTransactionCreate,
    PayableCreate,
    PayablePayPayload,
    ReceivableCollectPayload,
    ReceivableCreate,
)
from app.services import payable_atomicity_service


def make_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    return TestingSession()


def test_business_clock_uses_asia_manila_and_flips_at_1600_utc():
    before = datetime(2026, 8, 26, 15, 59, 59, tzinfo=timezone.utc)
    boundary = datetime(2026, 8, 26, 16, 0, 0, tzinfo=timezone.utc)

    assert BUSINESS_TIMEZONE_NAME == 'Asia/Manila'
    assert business_today(before) == '2026-08-26'
    assert business_today(boundary) == '2026-08-27'
    assert business_now(boundary).utcoffset().total_seconds() == 8 * 60 * 60


def test_business_clock_treats_injected_naive_datetime_as_utc():
    assert business_today(datetime(2026, 8, 26, 16, 30, 0)) == '2026-08-27'


def test_financial_request_models_default_missing_dates_to_business_day(monkeypatch):
    monkeypatch.setattr(cashflow_schemas, 'business_today', lambda: '2026-08-27')

    assert MoneyTransactionCreate(direction='in', financial_account_id=1, amount=10).transaction_date == '2026-08-27'
    assert AccountTransferCreate(from_account_id=1, to_account_id=2, amount=10).transfer_date == '2026-08-27'
    assert CashflowActionPayload().action_date == '2026-08-27'
    assert ReceivableCreate(counterparty_name='Guest', gross_amount=10).transaction_date == '2026-08-27'
    assert ReceivableCollectPayload(amount=10, financial_account_id=1).collection_date == '2026-08-27'
    assert PayableCreate(supplier_name='Supplier', gross_amount=10).bill_date == '2026-08-27'
    assert PayablePayPayload(amount=10, financial_account_id=1).payment_date == '2026-08-27'
    assert CashflowSummaryQuery().date == '2026-08-27'


def test_financial_request_models_replace_explicit_null_or_blank_dates(monkeypatch):
    monkeypatch.setattr(cashflow_schemas, 'business_today', lambda: '2026-08-27')

    assert MoneyTransactionCreate(transaction_date=None, direction='out', financial_account_id=1, amount=10).transaction_date == '2026-08-27'
    assert AccountTransferCreate(transfer_date='', from_account_id=1, to_account_id=2, amount=10).transfer_date == '2026-08-27'
    assert ReceivableCreate(counterparty_name='Guest', gross_amount=10, transaction_date=' ').transaction_date == '2026-08-27'
    assert PayableCreate(supplier_name='Supplier', gross_amount=10, bill_date=None).bill_date == '2026-08-27'


def test_payable_create_defaults_to_manila_business_date(monkeypatch):
    db = make_session()
    monkeypatch.setattr(payable_atomicity_service, 'business_today', lambda: '2026-08-27')
    monkeypatch.setattr(cashflow_schemas, 'business_today', lambda: '2026-08-27')

    item, replayed = payable_atomicity_service.create_payable_idempotent(
        db,
        PayableCreate(
            supplier_name='Manila Clock Supplier',
            gross_amount=500,
            bill_date=None,
        ),
        'pass65-create-business-date',
    )

    assert replayed is False
    assert item['bill_date'] == '2026-08-27'
    assert item['posted_at'] == '2026-08-27'


def test_payable_payment_defaults_to_manila_business_date(monkeypatch):
    db = make_session()
    monkeypatch.setattr(payable_atomicity_service, 'business_today', lambda: '2026-08-27')
    monkeypatch.setattr(cashflow_schemas, 'business_today', lambda: '2026-08-27')

    account = FinancialAccount(
        name='Manila Clock Bank',
        code='P65-BANK',
        account_type='bank',
        currency='PHP',
        is_active=True,
        opening_balance=1000,
        current_balance=1000,
        requires_daily_reconciliation=False,
        reconciliation_mode='none',
        requires_physical_count=False,
        variance_tolerance=0,
        approval_required_on_variance=False,
    )
    db.add(account)
    db.flush()

    payable, _ = payable_atomicity_service.create_payable_idempotent(
        db,
        PayableCreate(
            supplier_name='Manila Clock Supplier',
            gross_amount=500,
            bill_date=None,
        ),
        'pass65-payment-create-date',
    )

    result, replayed = payable_atomicity_service.pay_payable_idempotent(
        db,
        payable['id'],
        PayablePayPayload(
            amount=100,
            payment_date=None,
            financial_account_id=account.id,
            auto_post_accounting=False,
        ),
        'pass65-payment-business-date',
        username='owner',
    )

    assert replayed is False
    assert result['transaction']['transaction_date'] == '2026-08-27'
    assert result['transaction']['posted_at'] == '2026-08-27'
