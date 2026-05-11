from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_permissions
from app.db.database import get_db
from app.schemas.guests import (
    BookingFolioAction,
    BookingFolioCreate,
    BookingFolioLineCreate,
    BookingFolioLineUpdate,
    BookingFolioUpdate,
)
from app.services.guest_service import (
    add_folio_line,
    create_folio,
    delete_folio_line,
    get_folio,
    list_folios,
    set_folio_status,
    update_folio,
    update_folio_line,
)

router = APIRouter()


@router.get('/')
def get_room_folios(
    db: Session = Depends(get_db),
    user=Depends(require_permissions('folios.view')),
    booking_id: int | None = None,
    guest_id: int | None = None,
    status: str | None = None,
):
    return list_folios(db, booking_id=booking_id, guest_id=guest_id, status=status)


@router.get('/{folio_id}')
def get_room_folio(folio_id: int, db: Session = Depends(get_db), user=Depends(require_permissions('folios.view'))):
    try:
        return get_folio(db, folio_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post('/')
def add_room_folio(
    payload: BookingFolioCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('folios.manage')),
):
    try:
        return create_folio(db, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put('/{folio_id}')
def edit_room_folio(
    folio_id: int,
    payload: BookingFolioUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('folios.manage')),
):
    try:
        return update_folio(db, folio_id, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/{folio_id}/status')
def update_room_folio_status(
    folio_id: int,
    payload: BookingFolioAction,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('folios.manage')),
):
    try:
        return set_folio_status(db, folio_id, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/{folio_id}/lines')
def add_room_folio_line(
    folio_id: int,
    payload: BookingFolioLineCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('folios.manage')),
):
    try:
        return add_folio_line(db, folio_id, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put('/lines/{folio_line_id}')
def edit_room_folio_line(
    folio_line_id: int,
    payload: BookingFolioLineUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('folios.manage')),
):
    try:
        return update_folio_line(db, folio_line_id, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete('/lines/{folio_line_id}')
def remove_room_folio_line(
    folio_line_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('folios.manage')),
):
    try:
        return delete_folio_line(db, folio_line_id)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
