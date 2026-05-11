from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_permissions
from app.db.database import get_db
from app.schemas.procurement import ProcurementStatusAction, PurchaseOrderCreate, PurchaseOrderUpdate
from app.services.procurement_service import (
    create_purchase_order,
    delete_purchase_order,
    list_purchase_orders,
    set_purchase_order_status,
    update_purchase_order,
)

router = APIRouter()


@router.get('/')
def get_purchase_orders(
    db: Session = Depends(get_db),
    user=Depends(require_permissions('purchase_orders.view')),
    status: str | None = None,
    supplier_id: int | None = None,
):
    return list_purchase_orders(db, status=status, supplier_id=supplier_id)


@router.post('/')
def add_purchase_order(
    payload: PurchaseOrderCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('purchase_orders.create')),
):
    try:
        return create_purchase_order(db, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put('/{po_id}')
def edit_purchase_order(
    po_id: int,
    payload: PurchaseOrderUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('purchase_orders.create')),
):
    try:
        return update_purchase_order(db, po_id, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/{po_id}/status')
def update_purchase_order_status(
    po_id: int,
    payload: ProcurementStatusAction,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('purchase_orders.approve')),
):
    try:
        return set_purchase_order_status(db, po_id, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete('/{po_id}')
def remove_purchase_order(
    po_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('purchase_orders.approve')),
):
    try:
        return delete_purchase_order(db, po_id)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
