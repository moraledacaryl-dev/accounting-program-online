from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permissions
from app.db.database import get_db
from app.schemas.cashflow import FinancialAccountCreate, FinancialAccountUpdate
from app.services.cashflow_service import (
    create_financial_account,
    ensure_default_financial_accounts,
    list_financial_accounts,
    update_financial_account,
)

router = APIRouter()


@router.get('/')
def get_accounts(
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.view')),
    account_type: str | None = None,
    only_active: bool = False,
    on_date: str | None = None,
):
    return list_financial_accounts(db, account_type=account_type, only_active=only_active, on_date=on_date)


@router.post('/')
def add_account(
    payload: FinancialAccountCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.transfers')),
):
    try:
        return create_financial_account(db, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get('/{account_id}')
def get_account(account_id: int, db: Session = Depends(get_db), user=Depends(require_permissions('cashflow.view'))):
    rows = list_financial_accounts(db)
    for row in rows:
        if int(row.get('id') or 0) == int(account_id):
            return row
    raise HTTPException(status_code=404, detail='Financial account not found.')


@router.put('/{account_id}')
def edit_account(
    account_id: int,
    payload: FinancialAccountUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.transfers')),
):
    try:
        return update_financial_account(db, account_id, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/bootstrap-defaults')
def bootstrap_defaults(
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.transfers')),
):
    created = ensure_default_financial_accounts(db)
    return {'created': created}
