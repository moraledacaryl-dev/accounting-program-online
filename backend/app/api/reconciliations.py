from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permissions
from app.core.settings import settings
from app.db.database import get_db
from app.schemas.cashflow import CashReconciliationCreate, CashflowActionPayload
from app.services.operations_integration import publish_operations_event
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
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.reconcile')),
):
    try:
        item = create_cash_reconciliation(db, payload, username=getattr(user, 'username', None))
        if abs(item.variance or 0) >= settings.operations_reconciliation_variance_threshold:
            background_tasks.add_task(
                publish_operations_event,
                event_id=f'cash-reconciliation:{item.id}:variance:{item.variance}',
                event_type='drawer_reconciliation.pending',
                title='Cash reconciliation variance pending review',
                summary=f'Variance of {item.variance:,.2f} for {item.reconciliation_date}.',
                priority='High',
                subject_type='cash_reconciliation',
                subject_id=item.id,
                payload={
                    'reconciliation_date': item.reconciliation_date,
                    'shift_name': item.shift_name,
                    'expected_closing': item.expected_closing,
                    'actual_counted': item.actual_counted,
                    'variance': item.variance,
                    'status': item.status,
                },
            )
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
