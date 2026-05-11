from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permissions
from app.db.database import get_db
from app.schemas.accounting_setup import ChartAccountCreate, ChartAccountUpdate
from app.services.account_mapping_service import create_chart_account, delete_chart_account, list_chart_accounts, update_chart_account

router = APIRouter()


@router.get('/')
def get_chart_accounts(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    active_only: bool = False,
):
    return list_chart_accounts(db, active_only=active_only)


@router.post('/')
def add_chart_account(
    payload: ChartAccountCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('chart_of_accounts.manage')),
):
    try:
        return create_chart_account(db, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put('/{account_id}')
def edit_chart_account(
    account_id: int,
    payload: ChartAccountUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('chart_of_accounts.manage')),
):
    try:
        return update_chart_account(db, account_id, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete('/{account_id}')
def remove_chart_account(
    account_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('chart_of_accounts.manage')),
):
    try:
        return delete_chart_account(db, account_id)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
