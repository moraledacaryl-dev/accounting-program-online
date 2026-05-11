from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permissions
from app.db.database import get_db
from app.schemas.cashflow import CashReconciliationCreate, CashflowActionPayload
from app.services.cashflow_service import (
    approve_cash_reconciliation,
    close_cash_reconciliation,
    create_cash_reconciliation,
    list_cash_reconciliations,
    reverse_cash_reconciliation,
    update_cash_reconciliation,
)

router = APIRouter()


@router.get('/')
def get_reconciliations(
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.reconcile')),
    account_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    status: str | None = None,
    limit: int = Query(300, ge=1, le=1000),
):
    return list_cash_reconciliations(
        db,
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
        status=status,
        limit=limit,
    )


@router.post('/')
def add_reconciliation(
    payload: CashReconciliationCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.reconcile')),
):
    try:
        return create_cash_reconciliation(db, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put('/{reconciliation_id}')
def edit_reconciliation(
    reconciliation_id: int,
    payload: CashReconciliationCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.reconcile')),
):
    try:
        return update_cash_reconciliation(db, reconciliation_id, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/{reconciliation_id}/approve')
def approve_reconciliation(
    reconciliation_id: int,
    payload: CashflowActionPayload,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.reconcile')),
):
    try:
        return approve_cash_reconciliation(db, reconciliation_id, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/{reconciliation_id}/close')
def close_reconciliation(
    reconciliation_id: int,
    payload: CashflowActionPayload,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.reconcile')),
):
    try:
        return close_cash_reconciliation(db, reconciliation_id, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/{reconciliation_id}/reverse')
def reverse_reconciliation(
    reconciliation_id: int,
    payload: CashflowActionPayload,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.reconcile')),
):
    try:
        return reverse_cash_reconciliation(db, reconciliation_id, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
