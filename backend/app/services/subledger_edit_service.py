from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.subledger_edit_guard import (
    ensure_payable_edit_preserves_settlement,
    ensure_receivable_edit_preserves_settlement,
)


def update_receivable_safely(db: Session, receivable_id: int, payload):
    """Serialize an ordinary receivable edit against settlement/write-off workflows."""
    ensure_receivable_edit_preserves_settlement(db, receivable_id, payload)
    # Import lazily to avoid a module cycle while keeping the invariant at the
    # reusable service boundary instead of only in the HTTP route.
    from app.services.cashflow_service import update_receivable

    return update_receivable(db, receivable_id, payload)


def update_payable_safely(db: Session, payable_id: int, payload):
    """Serialize an ordinary payable edit against settlement/write-off workflows."""
    ensure_payable_edit_preserves_settlement(db, payable_id, payload)
    from app.services.cashflow_service import update_payable

    return update_payable(db, payable_id, payload)
