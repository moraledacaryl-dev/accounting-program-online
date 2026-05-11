from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_permissions
from app.db.database import get_db
from app.schemas.rooms import RoomTypeCreate, RoomTypeUpdate
from app.services.room_setup_service import create_room_type, delete_room_type, list_room_types, update_room_type

router = APIRouter()


@router.get('/')
def get_room_types(
    db: Session = Depends(get_db),
    user=Depends(require_permissions('room_setup.view')),
    active_only: bool = False,
):
    return list_room_types(db, active_only=active_only)


@router.post('/')
def add_room_type(
    payload: RoomTypeCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('room_setup.manage')),
):
    try:
        return create_room_type(db, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put('/{room_type_id}')
def edit_room_type(
    room_type_id: int,
    payload: RoomTypeUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('room_setup.manage')),
):
    try:
        return update_room_type(db, room_type_id, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete('/{room_type_id}')
def remove_room_type(
    room_type_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('room_setup.manage')),
):
    try:
        return delete_room_type(db, room_type_id)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
