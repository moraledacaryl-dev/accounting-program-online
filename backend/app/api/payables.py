from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permissions
from app.db.database import get_db
from app.schemas.cashflow import CashflowActionPayload, PayableCreate, PayablePayPayload
from app.services.operations_integration import is_due_or_overdue
from app.services.operations_outbox_service import enqueue_operations_event
from app.services.cashflow_service import (
    list_payables,
    reopen_payable,
    reverse_payable_payment,
    update_payable,
    write_off_payable,
)
from app.services.payable_atomicity_service import (
    IdempotencyConflict,
    create_payable_idempotent,
    pay_payable_idempotent,
)

router = APIRouter()


@router.get('/')
def get_payables(
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.view')),
    status: str | None = None,
    payable_type: str | None = None,
    overdue_only: bool = False,
    q: str | None = None,
    limit: int = Query(300, ge=1, le=1000),
):
    return list_payables(
        db,
        status=status,
        payable_type=payable_type,
        overdue_only=overdue_only,
        q=q,
        limit=limit,
    )


@router.post('/')
def add_payable(
    payload: PayableCreate,
    idempotency_key: str | None = Header(default=None, alias='Idempotency-Key'),
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.money_out')),
):
    try:
        item, replayed = create_payable_idempotent(db, payload, idempotency_key)

        balance_due = float(item.get('balance_due') or 0)
        due_date = item.get('due_date')
        if not replayed and balance_due > 0 and is_due_or_overdue(due_date):
            enqueue_operations_event(
                db,
                event_id=f"payable:{item['id']}:due:{due_date}",
                event_type='payable.due',
                title=f"Payable due: {item.get('supplier_name') or 'Unspecified supplier'}",
                summary=f'Balance due: {balance_due:,.2f} on {due_date}.',
                priority='High',
                subject_type='payable',
                subject_id=item['id'],
                payload={
                    'supplier_name': item.get('supplier_name'),
                    'payable_type': item.get('payable_type'),
                    'bill_date': item.get('bill_date'),
                    'due_date': due_date,
                    'gross_amount': item.get('gross_amount'),
                    'balance_due': balance_due,
                    'status': item.get('status'),
                },
            )

        db.commit()
        return item
    except IdempotencyConflict as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put('/{payable_id}')
def edit_payable(
    payable_id: int,
    payload: PayableCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.money_out')),
):
    try:
        return update_payable(db, payable_id, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/{payable_id}/pay')
def pay_payable_balance(
    payable_id: int,
    payload: PayablePayPayload,
    idempotency_key: str | None = Header(default=None, alias='Idempotency-Key'),
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.money_out')),
):
    try:
        result, _ = pay_payable_idempotent(
            db,
            payable_id,
            payload,
            idempotency_key,
            username=getattr(user, 'username', None),
        )
        db.commit()
        return result
    except IdempotencyConflict as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/{payable_id}/payments/{transaction_id}/reverse')
def reverse_payable_payment_entry(
    payable_id: int,
    transaction_id: int,
    payload: CashflowActionPayload,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.money_out')),
):
    try:
        return reverse_payable_payment(db, payable_id, transaction_id, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/{payable_id}/reopen')
def reopen_payable_entry(
    payable_id: int,
    payload: CashflowActionPayload,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.money_out')),
):
    try:
        return reopen_payable(db, payable_id, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/{payable_id}/write-off')
def write_off_payable_entry(
    payable_id: int,
    payload: CashflowActionPayload,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.money_out')),
):
    try:
        return write_off_payable(db, payable_id, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
