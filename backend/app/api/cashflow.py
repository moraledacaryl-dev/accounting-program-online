from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_any_permissions, require_permissions
from app.core.business_clock import business_today
from app.db.database import get_db
from app.models.entities import MoneyTransaction
from app.schemas.cashflow import CashflowActionPayload, MoneyTransactionCreate, MoneyTransactionUpdate
from app.services.cashflow_service import (
    account_ledger,
    cashflow_summary,
    create_money_transaction,
    delete_money_transaction,
    get_money_transaction,
    list_money_transactions,
    reverse_money_transaction,
)
from app.services.money_transaction_mutation_service import (
    approve_money_transaction,
    cancel_money_transaction,
    update_money_transaction,
)
from app.services.permission_service import get_user_permission_keys
from app.services.settlement_reversal_guard import ensure_linked_settlement_mutable

router = APIRouter()


_DIRECTION_PERMISSION = {
    'in': 'cashflow.money_in',
    'out': 'cashflow.money_out',
}


def _normalize_direction(value: str | None) -> str:
    return (value or '').strip().lower()


def _authorize_cashflow_direction(db: Session, user, direction: str | None):
    normalized = _normalize_direction(direction)
    permission = _DIRECTION_PERMISSION.get(normalized)
    if not permission:
        raise HTTPException(status_code=400, detail='direction must be "in" or "out".')
    if getattr(user, 'role', None) in {'owner', 'admin'}:
        return
    effective = get_user_permission_keys(db, user)
    if permission not in effective:
        raise HTTPException(status_code=403, detail=f'Missing permission: {permission}')


def _transaction_for_direction_auth(db: Session, transaction_id: int) -> MoneyTransaction:
    row = db.query(MoneyTransaction).filter(MoneyTransaction.id == int(transaction_id)).first()
    if not row:
        raise HTTPException(status_code=404, detail='Money transaction not found.')
    return row


@router.get('/summary')
def get_summary(
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.view')),
    date: str | None = None,
):
    return cashflow_summary(db, target_date=(date or '').strip() or business_today())


@router.get('/transactions')
def get_transactions(
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.view')),
    account_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    direction: str | None = None,
    module: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
):
    return list_money_transactions(
        db,
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
        direction=direction,
        module=module,
        status=status,
        q=q,
        limit=limit,
    )


@router.post('/transactions')
def add_transaction(
    payload: MoneyTransactionCreate,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('cashflow.money_in', 'cashflow.money_out')),
):
    _authorize_cashflow_direction(db, user, payload.direction)
    try:
        return create_money_transaction(db, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put('/transactions/{transaction_id}')
def edit_transaction(
    transaction_id: int,
    payload: MoneyTransactionUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('cashflow.money_in', 'cashflow.money_out')),
):
    current = _transaction_for_direction_auth(db, transaction_id)
    _authorize_cashflow_direction(db, user, current.direction)
    if payload.direction is not None and _normalize_direction(payload.direction) != _normalize_direction(current.direction):
        _authorize_cashflow_direction(db, user, payload.direction)
    try:
        ensure_linked_settlement_mutable(db, current)
        return update_money_transaction(db, transaction_id, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete('/transactions/{transaction_id}')
def remove_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('cashflow.money_in', 'cashflow.money_out')),
):
    current = _transaction_for_direction_auth(db, transaction_id)
    _authorize_cashflow_direction(db, user, current.direction)
    try:
        return delete_money_transaction(db, transaction_id)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/transactions/{transaction_id}/approve')
def approve_transaction(
    transaction_id: int,
    payload: CashflowActionPayload,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('cashflow.money_in', 'cashflow.money_out')),
):
    current = _transaction_for_direction_auth(db, transaction_id)
    _authorize_cashflow_direction(db, user, current.direction)
    try:
        return approve_money_transaction(db, transaction_id, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/transactions/{transaction_id}/cancel')
def cancel_transaction(
    transaction_id: int,
    payload: CashflowActionPayload,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('cashflow.money_in', 'cashflow.money_out')),
):
    current = _transaction_for_direction_auth(db, transaction_id)
    _authorize_cashflow_direction(db, user, current.direction)
    try:
        ensure_linked_settlement_mutable(db, current)
        return cancel_money_transaction(db, transaction_id, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/transactions/{transaction_id}/reverse')
def reverse_transaction(
    transaction_id: int,
    payload: CashflowActionPayload,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('cashflow.money_in', 'cashflow.money_out')),
):
    current = _transaction_for_direction_auth(db, transaction_id)
    _authorize_cashflow_direction(db, user, current.direction)
    try:
        ensure_linked_settlement_mutable(db, current)
        return reverse_money_transaction(db, transaction_id, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get('/transactions/{transaction_id}')
def transaction_detail(transaction_id: int, db: Session = Depends(get_db), user=Depends(require_permissions('cashflow.view'))):
    try:
        return get_money_transaction(db, transaction_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get('/accounts/{account_id}/ledger')
def get_account_ledger(
    account_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.view')),
    start_date: str | None = None,
    end_date: str | None = None,
    include_reconciliations: bool = True,
    direction: str | None = None,
    module: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = Query(500, ge=1, le=2000),
):
    try:
        return account_ledger(
            db,
            account_id,
            start_date=start_date,
            end_date=end_date,
            include_reconciliations=include_reconciliations,
            direction=direction,
            module=module,
            status=status,
            q=q,
            limit=limit,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
