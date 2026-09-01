from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.entities import Payable, Receivable
from app.schemas.cashflow import CashflowActionPayload
from app.services.cashflow_service import reverse_payable_payment, reverse_receivable_collection


def reverse_receivable_collection_with_state_guard(
    db: Session,
    receivable_id: int,
    transaction_id: int,
    payload: CashflowActionPayload,
    username: str | None = None,
):
    receivable = db.get(Receivable, int(receivable_id))
    if not receivable:
        raise ValueError('Receivable not found.')
    if (receivable.status or '').strip().lower() == 'written_off':
        raise ValueError('Reopen the written-off receivable before reversing a collection.')
    return reverse_receivable_collection(
        db,
        receivable_id,
        transaction_id,
        payload,
        username=username,
    )


def reverse_payable_payment_with_state_guard(
    db: Session,
    payable_id: int,
    transaction_id: int,
    payload: CashflowActionPayload,
    username: str | None = None,
):
    payable = db.get(Payable, int(payable_id))
    if not payable:
        raise ValueError('Payable not found.')
    if (payable.status or '').strip().lower() == 'written_off':
        raise ValueError('Reopen the written-off payable before reversing a payment.')
    return reverse_payable_payment(
        db,
        payable_id,
        transaction_id,
        payload,
        username=username,
    )
