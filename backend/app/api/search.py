from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.entities import Booking, BookingFolio, EventBooking, Guest, MoneyTransaction, Room, SaleOrder

router = APIRouter()


def _contains(column, term: str):
    return func.lower(func.coalesce(column, '')).like(f'%{term}%')


def _result(kind: str, label: str, subtitle: str, href: str, record_id: int | None = None) -> dict:
    return {
        'type': kind,
        'label': label,
        'subtitle': subtitle,
        'href': href,
        'id': record_id,
    }


@router.get('/')
def global_search(
    q: str = Query('', min_length=0, max_length=120),
    limit: int = Query(8, ge=1, le=25),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    term = (q or '').strip().lower()
    if len(term) < 2:
        return {'query': q, 'results': []}

    results: list[dict] = []
    numeric_id = int(term) if term.isdigit() else None

    booking_filters = [
        _contains(Booking.guest_name, term),
        _contains(Booking.room_name, term),
        _contains(Booking.external_booking_id, term),
        _contains(Booking.channel, term),
    ]
    if numeric_id is not None:
        booking_filters.append(Booking.id == numeric_id)
    bookings = (
        db.query(Booking)
        .filter(or_(*booking_filters))
        .order_by(Booking.id.desc())
        .limit(limit)
        .all()
    )
    for row in bookings:
        results.append(_result(
            'booking',
            f'BOOK-{row.id} · {row.guest_name}',
            f'{row.room_name or "No room"} · {row.check_in or "-"} to {row.check_out or "-"} · {row.status}',
            f'/bookings/{row.id}',
            row.id,
        ))

    guest_filters = [
        _contains(Guest.full_name, term),
        _contains(Guest.email, term),
        _contains(Guest.phone, term),
        _contains(Guest.company, term),
    ]
    if numeric_id is not None:
        guest_filters.append(Guest.id == numeric_id)
    guests = (
        db.query(Guest)
        .filter(or_(*guest_filters))
        .order_by(Guest.id.desc())
        .limit(limit)
        .all()
    )
    for row in guests:
        subtitle_parts = [part for part in [row.phone, row.email, row.company] if part]
        results.append(_result(
            'guest',
            row.full_name,
            ' · '.join(subtitle_parts) or 'Guest profile',
            f'/guests/{row.id}',
            row.id,
        ))

    folio_filters = [
        _contains(BookingFolio.folio_no, term),
        _contains(BookingFolio.status, term),
    ]
    if numeric_id is not None:
        folio_filters.extend([BookingFolio.id == numeric_id, BookingFolio.booking_id == numeric_id])
    folios = (
        db.query(BookingFolio)
        .filter(or_(*folio_filters))
        .order_by(BookingFolio.id.desc())
        .limit(limit)
        .all()
    )
    for row in folios:
        results.append(_result(
            'folio',
            row.folio_no,
            f'BOOK-{row.booking_id} · {row.status}',
            f'/room-folios/{row.id}',
            row.id,
        ))

    event_filters = [
        _contains(EventBooking.event_no, term),
        _contains(EventBooking.event_name, term),
        _contains(EventBooking.client_name, term),
        _contains(EventBooking.venue, term),
    ]
    if numeric_id is not None:
        event_filters.append(EventBooking.id == numeric_id)
    event_rows = (
        db.query(EventBooking)
        .filter(or_(*event_filters))
        .order_by(EventBooking.id.desc())
        .limit(limit)
        .all()
    )
    for row in event_rows:
        results.append(_result(
            'event',
            f'{row.event_no} · {row.event_name}',
            f'{row.client_name} · {row.event_date or "-"} · {row.status}',
            '/events',
            row.id,
        ))

    rooms = (
        db.query(Room)
        .filter(or_(_contains(Room.room_no, term), _contains(Room.name, term), _contains(Room.status, term)))
        .order_by(Room.room_no.asc())
        .limit(limit)
        .all()
    )
    for row in rooms:
        results.append(_result(
            'room',
            row.name or row.room_no,
            f'Room {row.room_no} · {row.status}',
            '/rooms',
            row.id,
        ))

    sale_filters = [
        _contains(SaleOrder.order_no, term),
        _contains(SaleOrder.counterparty, term),
        _contains(SaleOrder.payment_method, term),
    ]
    if numeric_id is not None:
        sale_filters.append(SaleOrder.id == numeric_id)
    sales = (
        db.query(SaleOrder)
        .filter(or_(*sale_filters))
        .order_by(SaleOrder.id.desc())
        .limit(limit)
        .all()
    )
    for row in sales:
        results.append(_result(
            'sale',
            row.order_no,
            f'{row.order_date or "-"} · {row.payment_method or "-"} · {float(row.net_amount or 0):,.2f}',
            '/restaurant-ops',
            row.id,
        ))

    money_filters = [
        _contains(MoneyTransaction.reference_no, term),
        _contains(MoneyTransaction.counterparty_name, term),
        _contains(MoneyTransaction.category, term),
        _contains(MoneyTransaction.notes, term),
    ]
    if numeric_id is not None:
        money_filters.append(MoneyTransaction.id == numeric_id)
    money_rows = (
        db.query(MoneyTransaction)
        .filter(or_(*money_filters))
        .order_by(MoneyTransaction.id.desc())
        .limit(limit)
        .all()
    )
    for row in money_rows:
        results.append(_result(
            'cashflow',
            row.reference_no or f'Transaction #{row.id}',
            f'{row.transaction_date or "-"} · {row.direction} · {float(row.amount or 0):,.2f}',
            '/cashflow',
            row.id,
        ))

    return {'query': q, 'results': results[:limit]}
