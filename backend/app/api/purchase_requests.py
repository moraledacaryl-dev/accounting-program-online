from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_permissions
from app.db.database import get_db
from app.schemas.procurement import ProcurementStatusAction, PurchaseRequestCreate, PurchaseRequestUpdate
from app.services.operations_integration import publish_operations_event
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
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('purchase_requests.create')),
):
    try:
        item = create_purchase_request(db, payload, username=getattr(user, 'username', None))
        estimated_total = sum((line.quantity or 0) * (line.estimated_unit_cost or 0) for line in item.lines)
        background_tasks.add_task(
            publish_operations_event,
            event_id=f'purchase-request:{item.id}:created',
            event_type='purchase_request.pending',
            title=f'Purchase request {item.request_no} pending review',
            summary=f'{item.department or "General"} requested an estimated {estimated_total:,.2f}.',
            priority='High' if estimated_total >= 50000 else 'Normal',
            subject_type='purchase_request',
            subject_id=item.id,
            payload={
                'request_no': item.request_no,
                'department': item.department,
                'needed_by_date': item.needed_by_date,
                'status': item.status,
                'estimated_total': estimated_total,
                'line_count': len(item.lines),
            },
        )
        return item
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
