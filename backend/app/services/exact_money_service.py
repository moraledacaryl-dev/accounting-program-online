from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.entities import FinancialAccount, Payable
from app.services.journal_integrity_service import money

ZERO = Decimal('0.0000')
MONEY_TOLERANCE = Decimal('0.0001')
STRICT_CASH_TYPES = {'cash_drawer', 'petty_cash', 'safe', 'ewallet'}


def normalize_money(value) -> Decimal:
    return money(value)


def serialize_money(value) -> float:
    """Convert exact internal money to the existing JSON-number API boundary."""
    return float(money(value))


def update_payable_balance_exact(db: Session, payable_id: int) -> Payable:
    payable = db.get(Payable, int(payable_id))
    if not payable:
        raise ValueError('Linked payable not found.')

    gross_amount = money(payable.gross_amount)
    amount_paid = money(payable.amount_paid)
    balance_due = money(gross_amount - amount_paid)

    payable.gross_amount = gross_amount
    payable.amount_paid = amount_paid
    if balance_due <= MONEY_TOLERANCE:
        payable.balance_due = ZERO
        payable.status = 'settled'
        payable.closed_at = payable.closed_at or __import__('app.core.business_clock', fromlist=['business_today']).business_today()
    elif amount_paid > ZERO:
        payable.balance_due = balance_due
        payable.status = 'partial'
        payable.closed_at = None
    else:
        payable.balance_due = balance_due
        payable.status = 'open'
        payable.closed_at = None

    db.add(payable)
    return payable


def apply_payable_payment_effect_exact(
    db: Session,
    *,
    payable_id: int,
    financial_account_id: int,
    amount,
    allow_overdraw: bool = False,
) -> tuple[Payable, FinancialAccount]:
    amount = money(amount)
    if amount <= ZERO:
        raise ValueError('Payment amount must be greater than zero.')

    account = (
        db.query(FinancialAccount)
        .filter(FinancialAccount.id == int(financial_account_id))
        .populate_existing()
        .with_for_update()
        .first()
    )
    if not account:
        raise ValueError('Linked financial account not found.')

    payable = (
        db.query(Payable)
        .filter(Payable.id == int(payable_id))
        .populate_existing()
        .with_for_update()
        .first()
    )
    if not payable:
        raise ValueError('Linked payable not found.')

    balance_due = money(payable.balance_due)
    if amount - balance_due > MONEY_TOLERANCE:
        raise ValueError('Payment amount cannot exceed payable balance.')

    current_balance = money(account.current_balance)
    account_type = (account.account_type or '').strip().lower()
    if not allow_overdraw and account_type in STRICT_CASH_TYPES and current_balance < amount:
        raise ValueError('Insufficient account balance for this money-out transaction.')

    account.current_balance = money(current_balance - amount)
    payable.amount_paid = money(money(payable.amount_paid) + amount)
    db.add(account)
    db.add(payable)
    update_payable_balance_exact(db, payable.id)
    return payable, account
