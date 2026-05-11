from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_permissions
from app.db.database import get_db
from app.schemas.rooms import RoomCreate, RoomUpdate
from app.services.room_setup_service import create_room, delete_room, list_rooms, update_room

router = APIRouter()


@router.get('/')
def get_rooms(
    db: Session = Depends(get_db),
    user=Depends(require_permissions('room_setup.view')),
    active_only: bool = False,
):
    return list_rooms(db, active_only=active_only)


@router.post('/')
def add_room(
    payload: RoomCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('room_setup.manage')),
):
    try:
        return create_room(db, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put('/{room_id}')
def edit_room(
    room_id: int,
    payload: RoomUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('room_setup.manage')),
):
    try:
        return update_room(db, room_id, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete('/{room_id}')
def remove_room(
    room_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('room_setup.manage')),
):
    try:
        return delete_room(db, room_id)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
