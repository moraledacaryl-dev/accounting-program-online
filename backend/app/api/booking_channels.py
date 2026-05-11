from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_permissions
from app.db.database import get_db
from app.schemas.rooms import BookingChannelCreate, BookingChannelUpdate
from app.services.room_setup_service import create_booking_channel, delete_booking_channel, list_booking_channels, update_booking_channel

router = APIRouter()


@router.get('/')
def get_booking_channels(
    db: Session = Depends(get_db),
    user=Depends(require_permissions('room_setup.view')),
    active_only: bool = False,
):
    return list_booking_channels(db, active_only=active_only)


@router.post('/')
def add_booking_channel(
    payload: BookingChannelCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('room_setup.manage')),
):
    try:
        return create_booking_channel(db, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put('/{channel_id}')
def edit_booking_channel(
    channel_id: int,
    payload: BookingChannelUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('room_setup.manage')),
):
    try:
        return update_booking_channel(db, channel_id, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete('/{channel_id}')
def remove_booking_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('room_setup.manage')),
):
    try:
        return delete_booking_channel(db, channel_id)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
