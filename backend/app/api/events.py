from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_any_permissions
from app.db.database import get_db
from app.schemas.events import EventActionPayload, EventBookingPayload, EventBookingUpdate, EventPaymentPayload
from app.services.event_service import (
    cancel_event,
    complete_event,
    confirm_event,
    create_event,
    get_event,
    list_events,
    record_event_payment,
    update_event,
)

router = APIRouter()


@router.get('/')
def events_list(
    status: str | None = None,
    q: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = Query(300, ge=1, le=1000),
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('events.view', 'bookings.view', 'cashflow.view')),
):
    return list_events(db, status=status, q=q, start_date=start_date, end_date=end_date, limit=limit)


@router.post('/')
def events_create(
    payload: EventBookingPayload,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('events.manage', 'bookings.create', 'cashflow.money_in')),
):
    try:
        return create_event(db, payload, username=getattr(user, 'username', None))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.get('/{event_id}')
def events_get(
    event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('events.view', 'bookings.view', 'cashflow.view')),
):
    try:
        return get_event(db, event_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.put('/{event_id}')
def events_update(
    event_id: int,
    payload: EventBookingUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('events.manage', 'bookings.edit', 'cashflow.money_in')),
):
    try:
        return update_event(db, event_id, payload, username=getattr(user, 'username', None))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.post('/{event_id}/confirm')
def events_confirm(
    event_id: int,
    payload: EventActionPayload,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('events.manage', 'bookings.edit', 'cashflow.money_in')),
):
    try:
        return confirm_event(db, event_id, payload, username=getattr(user, 'username', None))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.post('/{event_id}/complete')
def events_complete(
    event_id: int,
    payload: EventActionPayload,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('events.manage', 'bookings.edit')),
):
    try:
        return complete_event(db, event_id, payload, username=getattr(user, 'username', None))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.post('/{event_id}/cancel')
def events_cancel(
    event_id: int,
    payload: EventActionPayload,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('events.manage', 'bookings.cancel')),
):
    try:
        return cancel_event(db, event_id, payload, username=getattr(user, 'username', None))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.post('/{event_id}/payments')
def events_payment(
    event_id: int,
    payload: EventPaymentPayload,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('events.manage', 'cashflow.money_in')),
):
    try:
        return record_event_payment(db, event_id, payload, username=getattr(user, 'username', None))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
