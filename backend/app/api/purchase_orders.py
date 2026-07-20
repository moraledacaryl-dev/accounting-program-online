from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_permissions
from app.db.database import get_db
from app.schemas.procurement import ProcurementStatusAction, PurchaseOrderCreate, PurchaseOrderUpdate
from app.services.operations_integration import publish_operations_event
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
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('purchase_orders.create')),
):
    try:
        item = create_purchase_order(db, payload, username=getattr(user, 'username', None))
        background_tasks.add_task(
            publish_operations_event,
            event_id=f'purchase-order:{item.id}:created',
            event_type='purchase_order.pending',
            title=f'Purchase order {item.po_no} pending review',
            summary=f'Purchase order total: {item.total_amount:,.2f}.',
            priority='High' if (item.total_amount or 0) >= 50000 else 'Normal',
            subject_type='purchase_order',
            subject_id=item.id,
            payload={
                'po_no': item.po_no,
                'po_date': item.po_date,
                'expected_delivery_date': item.expected_delivery_date,
                'payment_terms': item.payment_terms,
                'status': item.status,
                'total_amount': item.total_amount,
                'line_count': len(item.lines),
            },
        )
        return item
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
