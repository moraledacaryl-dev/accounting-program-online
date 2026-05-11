from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permissions
from app.db.database import get_db
from app.schemas.cashflow import AccountTransferCreate, AccountTransferUpdate, CashflowActionPayload
from app.services.cashflow_service import (
    approve_transfer,
    cancel_transfer,
    create_transfer,
    delete_transfer,
    list_transfers,
    reverse_transfer,
    update_transfer,
)

router = APIRouter()


@router.get('/')
def get_transfers(
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.view')),
    account_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
):
    return list_transfers(db, account_id=account_id, start_date=start_date, end_date=end_date, limit=limit)


@router.post('/')
def add_transfer(
    payload: AccountTransferCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.transfers')),
):
    try:
        return create_transfer(db, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put('/{transfer_id}')
def edit_transfer(
    transfer_id: int,
    payload: AccountTransferUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.transfers')),
):
    try:
        return update_transfer(db, transfer_id, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete('/{transfer_id}')
def remove_transfer(
    transfer_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.transfers')),
):
    try:
        return delete_transfer(db, transfer_id)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/{transfer_id}/approve')
def approve_transfer_entry(
    transfer_id: int,
    payload: CashflowActionPayload,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.transfers')),
):
    try:
        return approve_transfer(db, transfer_id, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/{transfer_id}/cancel')
def cancel_transfer_entry(
    transfer_id: int,
    payload: CashflowActionPayload,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.transfers')),
):
    try:
        return cancel_transfer(db, transfer_id, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/{transfer_id}/reverse')
def reverse_transfer_entry(
    transfer_id: int,
    payload: CashflowActionPayload,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.transfers')),
):
    try:
        return reverse_transfer(db, transfer_id, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
