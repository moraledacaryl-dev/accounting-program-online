from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_permissions
from app.db.database import get_db
from app.schemas.procurement import ProcurementStatusAction, PurchaseRequestCreate, PurchaseRequestUpdate
from app.services.procurement_service import (
    create_purchase_order_from_request,
    create_purchase_request,
    delete_purchase_request,
    list_purchase_requests,
    set_purchase_request_status,
    update_purchase_request,
)

router = APIRouter()


@router.get('/')
def get_purchase_requests(
    db: Session = Depends(get_db),
    user=Depends(require_permissions('purchase_requests.view')),
    status: str | None = None,
    supplier_id: int | None = None,
):
    return list_purchase_requests(db, status=status, supplier_id=supplier_id)


@router.post('/')
def add_purchase_request(
    payload: PurchaseRequestCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('purchase_requests.create')),
):
    try:
        return create_purchase_request(db, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put('/{pr_id}')
def edit_purchase_request(
    pr_id: int,
    payload: PurchaseRequestUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('purchase_requests.create')),
):
    try:
        return update_purchase_request(db, pr_id, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/{pr_id}/status')
def update_purchase_request_status(
    pr_id: int,
    payload: ProcurementStatusAction,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('purchase_requests.approve')),
):
    try:
        return set_purchase_request_status(db, pr_id, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/{pr_id}/convert-to-po')
def convert_purchase_request_to_po(
    pr_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('purchase_orders.create')),
):
    try:
        return create_purchase_order_from_request(db, pr_id, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete('/{pr_id}')
def remove_purchase_request(
    pr_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('purchase_requests.approve')),
):
    try:
        return delete_purchase_request(db, pr_id)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
