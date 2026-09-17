"""Cancellation changes stay state, never the guest or financial history."""
from __future__ import annotations

import json
from collections.abc import Iterable
from sqlalchemy import and_, exists, func, not_, select
from sqlalchemy.orm import Session
from app.core.business_clock import business_today
from app.models.entities import Beds24BookingMap, Beds24SyncLog, Booking, BookingFolio, Receivable
from app.services.beds24_service import fetch_beds24_bookings

CANCELLED_BOOKING_STATUSES = {'cancelled', 'canceled'}


def ordinary_stay_condition():
    return func.lower(func.coalesce(Booking.status, '')).notin_(CANCELLED_BOOKING_STATUSES)


def ordinary_receivable_condition():
    """Exclude cancelled stay balances; retain separately recorded cancellation fees."""
    cancelled_stay = exists(select(Booking.id).where(
        Booking.id == Receivable.source_id, not_(ordinary_stay_condition()),
    ))
    return not_(and_(
        func.coalesce(Receivable.source_type, '') == 'booking',
        func.coalesce(Receivable.receivable_type, '') == 'guest_balance', cancelled_stay,
    ))


def cancelled_receivable_balance(db: Session, booking_id: int, collected: float) -> float:
    # Retained/cancellation charges must be explicitly classified, not inferred
    # from the old room price or from the existence of a deposit.
    from app.services.guest_service import folio_balance_summary
    folios = db.query(BookingFolio).filter(BookingFolio.booking_id == booking_id).all()
    totals = [folio_balance_summary(folio) for folio in folios]
    non_room_charges = sum(row['collectible_charges'] for row in totals)
    net_payments = max(collected, sum(row['actual_net_payments'] for row in totals), 0)
    return round(max(non_room_charges - net_payments, 0), 4)


def close_cancelled_stay_receivables(db: Session, booking: Booking) -> int:
    """Write off only the uncollectible ordinary stay balance, preserving collected cash."""
    if str(booking.status or '').lower() not in CANCELLED_BOOKING_STATUSES:
        return 0
    rows = db.query(Receivable).filter(
        Receivable.source_type == 'booking', Receivable.source_id == booking.id,
        Receivable.receivable_type == 'guest_balance', Receivable.balance_due > 0,
    ).populate_existing().with_for_update().all()
    if len(rows) > 1 and cancelled_receivable_balance(db, booking.id, 0) > 0:
        raise ValueError('Multiple stay receivables with retained charges require allocation review.')
    changed = 0
    for row in rows:
        remaining = min(float(row.balance_due), cancelled_receivable_balance(db, booking.id, float(row.amount_collected or 0)))
        if remaining == float(row.balance_due):
            continue
        changed += 1
        before = {'receivable_id': row.id, 'gross_amount': float(row.gross_amount or 0),
                  'amount_collected': float(row.amount_collected or 0), 'balance_due': float(row.balance_due or 0),
                  'status': row.status}
        row.balance_due = remaining
        row.status = ('partial' if row.amount_collected else 'open') if remaining else 'written_off'
        row.closed_at = None if remaining else business_today()
        row.notes = f"{row.notes or ''}\nCancelled ordinary stay balance written off; original value and collected payments preserved.".strip()
        db.add(Beds24SyncLog(
            event_type='cancelled_stay_balance', source_type='status_only',
            beds24_booking_id=booking.external_booking_id, local_booking_id=booking.id,
            status='success', message=f'Ordinary stay receivable #{row.id} written off without changing collected payments.',
            payload_json=json.dumps({'before': before, 'after_balance_due': remaining, 'cancelled_stay_adjustment': remaining - before['balance_due']}),
        ))
    return changed


def apply_beds24_cancellation(db: Session, payload: dict, *, source_type='status_only') -> dict:
    """Apply cancellation to an exact existing link in the caller's transaction.

    Names, maps/snapshots, folios, receipts and ledger rows are untouched.
    Unknown bookings are not imported. Mapping disagreement is a hard error.
    """
    bid = str(payload.get('id') or payload.get('bookingId') or '').strip()
    if not bid:
        raise ValueError('An exact Beds24 booking ID is required.')
    result = {'ok': True, 'beds24_booking_id': bid, 'action': 'unchanged', 'status_only': True}
    if str(payload.get('status') or '').strip().lower() not in CANCELLED_BOOKING_STATUSES:
        return result
    rows = db.query(Booking).filter(
        Booking.external_source == 'beds24', Booking.external_booking_id == bid,
    ).populate_existing().with_for_update().all()
    if not rows:
        return {**result, 'action': 'not_linked'}
    if len(rows) != 1:
        raise ValueError(f'Ambiguous local booking link for Beds24 {bid}.')
    booking = rows[0]
    mapping = db.query(Beds24BookingMap).filter(Beds24BookingMap.beds24_booking_id == bid).one_or_none()
    if mapping and mapping.local_booking_id != booking.id:
        raise ValueError(f'Conflicting booking map for Beds24 {bid}.')
    for key, local in [('arrival', booking.check_in), ('departure', booking.check_out)]:
        if payload.get(key) and local and str(payload[key]) != local:
            raise ValueError(f'Beds24 {bid} {key} differs; review before cancellation.')
    for key, expected in [('roomId', mapping.beds24_room_id if mapping else None),
                          ('propertyId', mapping.beds24_property_id if mapping else None)]:
        if payload.get(key) is not None and expected and str(payload[key]) != str(expected):
            raise ValueError(f'Beds24 {bid} {key} differs; review before cancellation.')
    result['local_booking_id'] = booking.id
    result['before_status'] = booking.status
    if str(booking.status or '').lower() in CANCELLED_BOOKING_STATUSES:
        result['receivables_closed'] = close_cancelled_stay_receivables(db, booking)
        return result
    booking.status = 'cancelled'
    result['receivables_closed'] = close_cancelled_stay_receivables(db, booking)
    db.add(Beds24SyncLog(
        event_type='booking_cancellation', source_type=source_type,
        beds24_booking_id=bid, local_booking_id=booking.id, status='success',
        message=f'Applied status-only cancellation to booking #{booking.id}; identity and financial history preserved.',
        payload_json=json.dumps({'before_status': result['before_status'], 'after_status': 'cancelled'}),
    ))
    db.flush()
    return {**result, 'action': 'cancelled', 'after_status': 'cancelled'}


def refresh_beds24_cancellation(db: Session, booking_id: str) -> dict:
    bid = str(booking_id or '').strip()
    if not bid:
        raise ValueError('An exact Beds24 booking ID is required.')
    rows, _, _ = fetch_beds24_bookings(db, booking_id=bid, include_invoice_items=False)
    matches = [row for row in rows if str(row.get('id')) == bid]
    if len(matches) != 1:
        raise ValueError(f'Expected one exact Beds24 booking {bid}.')
    result = apply_beds24_cancellation(db, matches[0])
    db.commit()
    return result


def neutralize_cancelled_beds24_bookings(db: Session, *, beds24_booking_ids: Iterable[str] | None = None) -> dict[str, int]:
    """Retire ordinary balances for explicit IDs; never zero value/cash or delete lines."""
    ids = [str(value).strip() for value in (beds24_booking_ids or []) if str(value).strip()]
    if not ids:
        return {'cancelled_bookings_neutralized': 0, 'beds24_folio_lines_removed': 0, 'receivables_closed': 0}
    bookings = db.query(Booking).filter(Booking.external_source == 'beds24', Booking.external_booking_id.in_(ids)).all()
    count = sum(close_cancelled_stay_receivables(db, booking) for booking in bookings)
    if count:
        db.commit()
    return {'cancelled_bookings_neutralized': 0, 'beds24_folio_lines_removed': 0, 'receivables_closed': count}
