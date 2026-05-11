from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permissions
from app.db.database import get_db
from app.schemas.guests import GuestCreate, GuestMergePayload, GuestUpdate
from app.services.guest_service import create_guest, get_guest, guest_history, list_guests, merge_guests, search_guests, update_guest

router = APIRouter()


@router.get('/')
def get_guest_list(
    db: Session = Depends(get_db),
    user=Depends(require_permissions('guests.view')),
    q: str | None = None,
    vip_only: bool = False,
    active_only: bool = True,
    limit: int = Query(300, ge=1, le=2000),
):
    return list_guests(db, q=q, vip_only=vip_only, active_only=active_only, limit=limit)


@router.get('/search')
def guest_search(
    q: str,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('guests.view')),
    limit: int = Query(30, ge=1, le=200),
):
    return search_guests(db, q=q, limit=limit)


@router.get('/{guest_id}')
def guest_detail(guest_id: int, db: Session = Depends(get_db), user=Depends(require_permissions('guests.view'))):
    try:
        return get_guest(db, guest_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get('/{guest_id}/history')
def guest_detail_history(guest_id: int, db: Session = Depends(get_db), user=Depends(require_permissions('guests.view'))):
    try:
        return guest_history(db, guest_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post('/')
def add_guest(
    payload: GuestCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('guests.create')),
):
    try:
        return create_guest(db, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put('/{guest_id}')
def edit_guest(
    guest_id: int,
    payload: GuestUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('guests.edit')),
):
    try:
        return update_guest(db, guest_id, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/merge')
def merge_guest_records(
    payload: GuestMergePayload,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('guests.edit')),
):
    try:
        return merge_guests(db, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
