from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_permissions
from app.db.database import get_db
from app.schemas.procurement import ProcurementStatusAction, ReceivingCreate, ReceivingUpdate
from app.services.procurement_service import (
    create_receiving_record,
    delete_receiving_record,
    list_receiving_records,
    set_receiving_status,
    update_receiving_record,
)

router = APIRouter()


@router.get('/')
def get_receiving_records(
    db: Session = Depends(get_db),
    user=Depends(require_permissions('receiving.view')),
    status: str | None = None,
    supplier_id: int | None = None,
):
    return list_receiving_records(db, status=status, supplier_id=supplier_id)


@router.post('/')
def add_receiving_record(
    payload: ReceivingCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('receiving.post')),
):
    try:
        return create_receiving_record(db, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put('/{receiving_id}')
def edit_receiving_record(
    receiving_id: int,
    payload: ReceivingUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('receiving.post')),
):
    try:
        return update_receiving_record(db, receiving_id, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/{receiving_id}/status')
def update_receiving_record_status(
    receiving_id: int,
    payload: ProcurementStatusAction,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('receiving.post')),
):
    try:
        return set_receiving_status(db, receiving_id, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete('/{receiving_id}')
def remove_receiving_record(
    receiving_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('receiving.post')),
):
    try:
        return delete_receiving_record(db, receiving_id)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
