from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permissions
from app.core.settings import settings
from app.db.database import get_db
from app.schemas.cashflow import CashReconciliationCreate, CashflowActionPayload
from app.services.cashflow_service import (
    approve_cash_reconciliation,
    close_cash_reconciliation,
    list_cash_reconciliations,
    reverse_cash_reconciliation,
    update_cash_reconciliation,
)
from app.services.operations_outbox_service import enqueue_operations_event
from app.services.reconciliation_atomicity_service import create_cash_reconciliation_uncommitted

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
        item = create_cash_reconciliation_uncommitted(
            db,
            payload,
            username=getattr(user, 'username', None),
        )
        variance = float(item.get('variance') or 0)
        if abs(variance) >= settings.operations_reconciliation_variance_threshold:
            enqueue_operations_event(
                db,
                event_id=f"cash-reconciliation:{item['id']}:variance:{variance}",
                event_type='drawer_reconciliation.pending',
                title='Cash reconciliation variance pending review',
                summary=f"Variance of {variance:,.2f} for {item.get('reconciliation_date')}.",
                priority='High',
                subject_type='cash_reconciliation',
                subject_id=item['id'],
                payload={
                    'reconciliation_date': item.get('reconciliation_date'),
                    'shift_name': item.get('shift_name'),
                    'expected_closing': item.get('expected_closing'),
                    'actual_counted': item.get('actual_counted'),
                    'variance': variance,
                    'status': item.get('status'),
                },
            )
        db.commit()
        return item
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
