from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_permissions
from app.db.database import get_db
from app.schemas.common import BookingCreate, BookingUpdate, RoomBreakfastCreate
from app.services.hospitality_service import (
    create_booking_with_accounting,
    create_room_breakfast_log,
    list_bookings,
    list_room_breakfast_logs,
    update_booking_with_accounting,
)

router = APIRouter()


@router.get('/bookings')
def bookings(db: Session = Depends(get_db), user=Depends(require_permissions('bookings.view'))):
    return list_bookings(db)


@router.post('/bookings')
def add_booking(
    payload: BookingCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('bookings.create')),
):
    try:
        return create_booking_with_accounting(db, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put('/bookings/{booking_id}')
def edit_booking(
    booking_id: int,
    payload: BookingUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('bookings.edit')),
):
    try:
        return update_booking_with_accounting(db, booking_id, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get('/breakfast-logs')
def breakfast_logs(db: Session = Depends(get_db), user=Depends(require_permissions('bookings.view'))):
    return list_room_breakfast_logs(db)


@router.post('/breakfast-logs')
def add_breakfast_log(
    payload: RoomBreakfastCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('staff_meals.manage')),
):
    try:
        return create_room_breakfast_log(db, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
