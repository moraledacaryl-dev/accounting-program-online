from __future__ import annotations

from app.services.cashflow_service import _preferred_finance_paths  # noqa: F401
from app.services.accounting_service import PAYMENT_ACCOUNT
from app.services.journal_integrity_service import money


def preview_journal_impact(direction: str, amount: float, payment_method: str | None = None) -> dict:
    """Default cashflow preview; payment accounts share the record-posting map."""
    pay = (payment_method or 'cash').strip().lower() or 'cash'
    if pay == 'bank':
        pay = 'bank_transfer'
    direction_key = (direction or '').strip().lower()
    if direction_key not in {'in', 'out'}:
        raise ValueError('Direction must be in or out.')
    value = money(amount)
    if value <= 0:
        raise ValueError('Amount must be positive.')
    if pay not in PAYMENT_ACCOUNT:
        raise ValueError('Choose a supported payment method.')
    pay_code, pay_name = PAYMENT_ACCOUNT[pay]
    payment = {'code': pay_code, 'name': pay_name, 'amount': float(value)}
    counterpart = {'code': '4000' if direction_key == 'in' else '5000', 'name': 'Revenue' if direction_key == 'in' else 'Operating Expense', 'amount': float(value)}
    return {
        'direction': direction_key,
        'payment_method': pay,
        'debit_line': payment if direction_key == 'in' else counterpart,
        'credit_line': counterpart if direction_key == 'in' else payment,
        'balanced': True,
    }


__all__ = ['preview_journal_impact']
