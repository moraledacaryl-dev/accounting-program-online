from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_permissions
from app.db.database import get_db
from app.schemas.payroll_periods import PayrollImportCreate, PayrollPeriodCreate, PayrollPeriodUpdate, PayrollPostAction
from app.services.payroll_period_service import (
    create_payroll_period,
    delete_payroll_period,
    get_payroll_period,
    import_payroll_lines,
    list_payroll_periods,
    post_payroll_period,
    update_payroll_period,
)

router = APIRouter()


@router.get('/')
def get_periods(
    db: Session = Depends(get_db),
    user=Depends(require_permissions('payroll_periods.view')),
    status: str | None = None,
    limit: int = 200,
):
    return list_payroll_periods(db, status=status, limit=limit)


@router.get('/{period_id}')
def get_period(
    period_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('payroll_periods.view')),
):
    try:
        return get_payroll_period(db, period_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post('/')
def add_period(
    payload: PayrollPeriodCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('payroll_periods.manage')),
):
    try:
        return create_payroll_period(db, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put('/{period_id}')
def edit_period(
    period_id: int,
    payload: PayrollPeriodUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('payroll_periods.manage')),
):
    try:
        return update_payroll_period(db, period_id, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/import')
def import_period_lines(
    payload: PayrollImportCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('payroll_periods.manage')),
):
    try:
        return import_payroll_lines(db, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/{period_id}/post')
def post_period(
    period_id: int,
    payload: PayrollPostAction,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('payroll_periods.manage')),
):
    try:
        return post_payroll_period(db, period_id, username=getattr(user, 'username', None), post_date=payload.post_date)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete('/{period_id}')
def remove_period(
    period_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('payroll_periods.manage')),
):
    try:
        return delete_payroll_period(db, period_id)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
