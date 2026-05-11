from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permissions
from app.db.database import get_db
from app.schemas.cashflow import CashflowActionPayload, ReceivableCollectPayload, ReceivableCreate
from app.services.cashflow_service import (
    collect_receivable,
    create_receivable,
    list_receivables,
    reopen_receivable,
    reverse_receivable_collection,
    update_receivable,
    write_off_receivable,
)

router = APIRouter()


@router.get('/')
def get_receivables(
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.view')),
    status: str | None = None,
    receivable_type: str | None = None,
    overdue_only: bool = False,
    q: str | None = None,
    limit: int = Query(300, ge=1, le=1000),
):
    return list_receivables(
        db,
        status=status,
        receivable_type=receivable_type,
        overdue_only=overdue_only,
        q=q,
        limit=limit,
    )


@router.post('/')
def add_receivable(
    payload: ReceivableCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.money_in')),
):
    try:
        return create_receivable(db, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put('/{receivable_id}')
def edit_receivable(
    receivable_id: int,
    payload: ReceivableCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.money_in')),
):
    try:
        return update_receivable(db, receivable_id, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/{receivable_id}/collect')
def collect_receivable_payment(
    receivable_id: int,
    payload: ReceivableCollectPayload,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.money_in')),
):
    try:
        return collect_receivable(db, receivable_id, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/{receivable_id}/collections/{transaction_id}/reverse')
def reverse_receivable_collection_payment(
    receivable_id: int,
    transaction_id: int,
    payload: CashflowActionPayload,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.money_in')),
):
    try:
        return reverse_receivable_collection(db, receivable_id, transaction_id, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/{receivable_id}/reopen')
def reopen_receivable_entry(
    receivable_id: int,
    payload: CashflowActionPayload,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.money_in')),
):
    try:
        return reopen_receivable(db, receivable_id, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/{receivable_id}/write-off')
def write_off_receivable_entry(
    receivable_id: int,
    payload: CashflowActionPayload,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.money_in')),
):
    try:
        return write_off_receivable(db, receivable_id, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
