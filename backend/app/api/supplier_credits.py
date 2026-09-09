from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permissions
from app.db.database import get_db
from app.schemas.supplier_credits import SupplierCreditApplyPayload, SupplierCreditReversePayload
from app.services.supplier_credit_reversal_service import (
    SupplierCreditReversalIdempotencyConflict,
    list_supplier_credits_with_reversals,
    reverse_supplier_credit_application,
)
from app.services.supplier_credit_service import (
    SupplierCreditIdempotencyConflict,
    apply_supplier_credit,
)


router = APIRouter()


@router.get('/')
def get_supplier_credits(
    status: str | None = None,
    supplier_name: str | None = None,
    limit: int = Query(300, ge=1, le=1000),
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.view')),
):
    return list_supplier_credits_with_reversals(
        db,
        status=status,
        supplier_name=supplier_name,
        limit=limit,
    )


@router.post('/{credit_id}/apply')
def apply_credit(
    credit_id: int,
    payload: SupplierCreditApplyPayload,
    idempotency_key: str | None = Header(default=None, alias='Idempotency-Key'),
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.money_out')),
):
    try:
        result = apply_supplier_credit(
            db,
            credit_id,
            payload,
            idempotency_key,
            username=getattr(user, 'username', None),
            user=user,
        )
        db.commit()
        return result
    except SupplierCreditIdempotencyConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.post('/applications/{application_id}/reverse')
def reverse_credit_application(
    application_id: int,
    payload: SupplierCreditReversePayload,
    idempotency_key: str | None = Header(default=None, alias='Idempotency-Key'),
    db: Session = Depends(get_db),
    user=Depends(require_permissions('cashflow.money_out')),
):
    try:
        result = reverse_supplier_credit_application(
            db,
            application_id,
            payload,
            idempotency_key,
            username=getattr(user, 'username', None),
            user=user,
        )
        db.commit()
        return result
    except SupplierCreditReversalIdempotencyConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
