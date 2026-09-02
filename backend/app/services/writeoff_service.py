from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.entities import Payable, Receivable
from app.schemas.cashflow import CashflowActionPayload
from app.services.cashflow_service import _safe_date, _serialize_payable, _serialize_receivable


def _lock_subledger_row(db: Session, model, row_id: int):
    return (
        db.query(model)
        .filter(model.id == int(row_id))
        .populate_existing()
        .with_for_update()
        .first()
    )


def write_off_receivable_preserving_cash(
    db: Session,
    receivable_id: int,
    payload: CashflowActionPayload,
):
    row = _lock_subledger_row(db, Receivable, receivable_id)
    if not row:
        raise ValueError('Receivable not found.')
    if float(row.balance_due or 0) <= 0:
        raise ValueError('Receivable has no remaining balance.')

    # A write-off closes the receivable without pretending the forgiven
    # balance was cash collected. The actual settlement history remains in
    # amount_collected and can be reconstructed correctly if reopened later.
    # The parent row is locked so settlement reversal/edit/cancel must serialize
    # with this state transition instead of validating stale state concurrently.
    row.status = 'written_off'
    row.balance_due = 0
    row.closed_at = _safe_date(payload.action_date)
    if payload.reason:
        row.notes = f"{row.notes or ''}\nWrite-off: {payload.reason}".strip()

    db.commit()
    db.refresh(row)
    return _serialize_receivable(row)


def write_off_payable_preserving_cash(
    db: Session,
    payable_id: int,
    payload: CashflowActionPayload,
):
    row = _lock_subledger_row(db, Payable, payable_id)
    if not row:
        raise ValueError('Payable not found.')
    if float(row.balance_due or 0) <= 0:
        raise ValueError('Payable has no remaining balance.')

    # A write-off closes the payable without pretending the forgiven balance
    # was paid. amount_paid remains the actual cash/payment settlement total.
    # The parent row is locked so settlement reversal/edit/cancel must serialize
    # with this state transition instead of validating stale state concurrently.
    row.status = 'written_off'
    row.balance_due = 0
    row.closed_at = _safe_date(payload.action_date)
    if payload.reason:
        row.notes = f"{row.notes or ''}\nWrite-off: {payload.reason}".strip()

    db.commit()
    db.refresh(row)
    return _serialize_payable(row)
