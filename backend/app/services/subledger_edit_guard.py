from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.entities import Payable, Receivable


TOLERANCE = 0.0001


def _as_float(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _lock_subledger_row(db: Session, model, row_id: int):
    return (
        db.query(model)
        .filter(model.id == int(row_id))
        .populate_existing()
        .with_for_update()
        .first()
    )


def ensure_receivable_edit_preserves_settlement(db: Session, receivable_id: int, payload) -> None:
    row = _lock_subledger_row(db, Receivable, receivable_id)
    if not row:
        raise ValueError('Receivable not found.')

    stored_collected = _as_float(row.amount_collected)
    requested_collected = _as_float(payload.amount_collected)
    if abs(requested_collected - stored_collected) > TOLERANCE:
        raise ValueError(
            'amount_collected is transaction-derived and cannot be edited directly. '
            'Use the collection/reversal workflow.'
        )

    requested_gross = max(_as_float(payload.gross_amount), 0.0)
    if requested_gross + TOLERANCE < stored_collected:
        raise ValueError('gross_amount cannot be less than actual amount_collected.')

    status = (row.status or '').strip().lower()
    if status == 'written_off':
        raise ValueError('Reopen the receivable before editing a written-off receivable.')
    if status == 'settled' and abs(requested_gross - _as_float(row.gross_amount)) > TOLERANCE:
        raise ValueError('Reopen the receivable before changing the gross amount of a settled receivable.')


def ensure_payable_edit_preserves_settlement(db: Session, payable_id: int, payload) -> None:
    row = _lock_subledger_row(db, Payable, payable_id)
    if not row:
        raise ValueError('Payable not found.')

    stored_paid = _as_float(row.amount_paid)
    requested_paid = _as_float(payload.amount_paid)
    if abs(requested_paid - stored_paid) > TOLERANCE:
        raise ValueError(
            'amount_paid is transaction-derived and cannot be edited directly. '
            'Use the payment/reversal workflow.'
        )

    requested_gross = max(_as_float(payload.gross_amount), 0.0)
    if requested_gross + TOLERANCE < stored_paid:
        raise ValueError('gross_amount cannot be less than actual amount_paid.')

    status = (row.status or '').strip().lower()
    if status == 'written_off':
        raise ValueError('Reopen the payable before editing a written-off payable.')
    if status == 'settled' and abs(requested_gross - _as_float(row.gross_amount)) > TOLERANCE:
        raise ValueError('Reopen the payable before changing the gross amount of a settled payable.')
