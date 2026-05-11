from __future__ import annotations

from app.services.cashflow_service import _preferred_finance_paths  # noqa: F401


def preview_journal_impact(direction: str, amount: float, payment_method: str | None = None) -> dict:
    pay = (payment_method or 'cash').strip().lower() or 'cash'
    direction_key = (direction or '').strip().lower()
    if direction_key not in {'in', 'out'}:
        direction_key = 'in'

    if direction_key == 'in':
        debit = {'code': '1000', 'name': 'Cash and Cash Equivalents', 'amount': float(amount or 0)}
        credit = {'code': '4000', 'name': 'Revenue', 'amount': float(amount or 0)}
    else:
        debit = {'code': '5000', 'name': 'Operating Expense', 'amount': float(amount or 0)}
        credit = {'code': '1000', 'name': 'Cash and Cash Equivalents', 'amount': float(amount or 0)}

    if pay in {'bank_transfer', 'bank'}:
        if direction_key == 'in':
            debit = {'code': '1010', 'name': 'Bank', 'amount': float(amount or 0)}
        else:
            credit = {'code': '1010', 'name': 'Bank', 'amount': float(amount or 0)}

    return {
        'direction': direction_key,
        'payment_method': pay,
        'debit_line': debit,
        'credit_line': credit,
        'balanced': round(float(debit['amount']), 4) == round(float(credit['amount']), 4),
    }


__all__ = ['preview_journal_impact']
