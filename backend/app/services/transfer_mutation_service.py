from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.entities import AccountTransfer, FinancialAccount
from app.schemas.cashflow import AccountTransferUpdate, CashflowActionPayload
from app.services.cashflow_service import (
    approve_transfer as _approve_transfer,
    cancel_transfer as _cancel_transfer,
    update_transfer as _update_transfer,
)


def _lock_transfer(db: Session, transfer_id: int) -> AccountTransfer:
    row = (
        db.query(AccountTransfer)
        .filter(AccountTransfer.id == int(transfer_id))
        .populate_existing()
        .with_for_update()
        .first()
    )
    if not row:
        raise ValueError('Transfer not found.')
    return row


def _lock_accounts(db: Session, account_ids) -> dict[int, FinancialAccount]:
    normalized = sorted({int(account_id) for account_id in account_ids if account_id is not None})
    if not normalized:
        return {}
    rows = (
        db.query(FinancialAccount)
        .filter(FinancialAccount.id.in_(normalized))
        .order_by(FinancialAccount.id.asc())
        .populate_existing()
        .with_for_update()
        .all()
    )
    by_id = {int(row.id): row for row in rows}
    missing = [account_id for account_id in normalized if account_id not in by_id]
    if missing:
        raise ValueError('Transfer financial account not found.')
    return by_id


def update_transfer(
    db: Session,
    transfer_id: int,
    payload: AccountTransferUpdate,
    username: str | None = None,
):
    """Serialize edits on the transfer row and every old/new cash account involved."""

    row = _lock_transfer(db, transfer_id)
    data = payload.model_dump(exclude_unset=True)
    account_ids = {
        int(row.from_account_id),
        int(row.to_account_id),
    }
    if data.get('from_account_id') is not None:
        account_ids.add(int(data['from_account_id']))
    if data.get('to_account_id') is not None:
        account_ids.add(int(data['to_account_id']))
    _lock_accounts(db, account_ids)
    return _update_transfer(db, transfer_id, payload, username=username)


def approve_transfer(
    db: Session,
    transfer_id: int,
    payload: CashflowActionPayload,
    username: str | None = None,
):
    """Prevent concurrent approvals from applying the transfer balance effect twice."""

    row = _lock_transfer(db, transfer_id)
    _lock_accounts(db, {row.from_account_id, row.to_account_id})
    return _approve_transfer(db, transfer_id, payload, username=username)


def cancel_transfer(db: Session, transfer_id: int, payload: CashflowActionPayload):
    """Prevent concurrent cancellation/edit/approval from racing balance restoration."""

    row = _lock_transfer(db, transfer_id)
    _lock_accounts(db, {row.from_account_id, row.to_account_id})
    return _cancel_transfer(db, transfer_id, payload)
