from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.entities import FinancialAccount, Payable
from app.models.mutation_idempotency import MutationIdempotency
from app.schemas.cashflow import PayableCreate, PayablePayPayload
from app.services.exact_money_service import normalize_money
from app.services.payable_atomicity_service import (
    create_payable_idempotent,
    pay_payable_idempotent,
)


def make_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    return TestingSession()


def test_repeated_decimal_payments_remain_exact_end_to_end():
    db = make_session()
    account = FinancialAccount(
        name='Pass B Exact Bank',
        code='PASS-B-BANK',
        account_type='bank',
        subtype='test',
        currency='PHP',
        is_active=True,
        requires_daily_reconciliation=False,
        reconciliation_mode='none',
        requires_physical_count=False,
        variance_tolerance=Decimal('0.0000'),
        approval_required_on_variance=False,
        opening_balance=Decimal('1.0000'),
        current_balance=Decimal('1.0000'),
        department='finance',
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    payable_data, replayed = create_payable_idempotent(
        db,
        PayableCreate(
            supplier_name='Pass B Supplier',
            gross_amount=Decimal('0.3000'),
            amount_paid=Decimal('0.0000'),
            bir_include=False,
        ),
        'pass-b-create-0001',
    )
    assert replayed is False
    db.commit()

    for index in range(3):
        _, replayed = pay_payable_idempotent(
            db,
            payable_data['id'],
            PayablePayPayload(
                amount=Decimal('0.1000'),
                financial_account_id=account.id,
                auto_post_accounting=False,
            ),
            f'pass-b-payment-{index:04d}',
            username='pass-b-test',
        )
        assert replayed is False
        db.commit()

    stored = db.get(Payable, payable_data['id'])
    db.refresh(account)

    assert normalize_money(stored.amount_paid) == Decimal('0.3000')
    assert normalize_money(stored.balance_due) == Decimal('0.0000')
    assert stored.status == 'settled'
    assert normalize_money(account.current_balance) == Decimal('0.7000')
    assert db.query(MutationIdempotency).count() == 4


def test_four_decimal_money_quantum_is_preserved_without_float_round_trip():
    assert normalize_money(Decimal('123456789.12345')) == Decimal('123456789.1235')
    assert normalize_money('0.10005') == Decimal('0.1001')
    assert normalize_money('0.00004') == Decimal('0.0000')
