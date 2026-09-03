from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.entities import MoneyTransaction
from app.schemas.cashflow import CashflowActionPayload, MoneyTransactionUpdate
from app.services.cashflow_service import (
    approve_money_transaction as _approve_money_transaction,
    cancel_money_transaction as _cancel_money_transaction,
    update_money_transaction as _update_money_transaction,
)


def _lock_money_transaction(db: Session, tx_id: int) -> MoneyTransaction:
    row = (
        db.query(MoneyTransaction)
        .filter(MoneyTransaction.id == int(tx_id))
        .populate_existing()
        .with_for_update()
        .first()
    )
    if not row:
        raise ValueError('Money transaction not found.')
    return row


def update_money_transaction(
    db: Session,
    tx_id: int,
    payload: MoneyTransactionUpdate,
    username: str | None = None,
):
    _lock_money_transaction(db, tx_id)
    return _update_money_transaction(db, tx_id, payload, username=username)


def approve_money_transaction(
    db: Session,
    tx_id: int,
    payload: CashflowActionPayload,
    username: str | None = None,
):
    _lock_money_transaction(db, tx_id)
    return _approve_money_transaction(db, tx_id, payload, username=username)


def cancel_money_transaction(
    db: Session,
    tx_id: int,
    payload: CashflowActionPayload,
    username: str | None = None,
):
    _lock_money_transaction(db, tx_id)
    return _cancel_money_transaction(db, tx_id, payload, username=username)
