from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.entities import MoneyTransaction, Payable, Receivable


_POSTING_STATUSES = {'approved', 'posted'}


def ensure_linked_settlement_mutable(db: Session, tx: MoneyTransaction) -> None:
    """Prevent implicit reopening of a written-off AR/AP through transaction mutation.

    Editing, cancelling, or reversing a posted linked settlement removes its cash
    effect and recomputes the linked subledger balance. If the parent has already
    been written off, that recomputation would silently replace the explicit
    written-off state with open/partial. Require an explicit parent reopen first
    so the accounting state transition remains intentional and auditable.
    """

    status = (tx.status or '').strip().lower()
    if status not in _POSTING_STATUSES:
        return

    if tx.receivable_id:
        receivable = db.get(Receivable, int(tx.receivable_id))
        if receivable and (receivable.status or '').strip().lower() == 'written_off':
            raise ValueError(
                'Linked receivable is written off. Reopen the receivable before editing, cancelling, or reversing its collection.'
            )

    if tx.payable_id:
        payable = db.get(Payable, int(tx.payable_id))
        if payable and (payable.status or '').strip().lower() == 'written_off':
            raise ValueError(
                'Linked payable is written off. Reopen the payable before editing, cancelling, or reversing its payment.'
            )
