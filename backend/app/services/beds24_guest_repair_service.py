from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.entities import Beds24BookingMap, Booking, Guest


_PLACEHOLDER_GUEST_NAMES = {
    'unnamedguest',
    'unknown',
    'unknownguest',
    'guest',
    'noguest',
    'n/a',
    'na',
    'none',
    'tba',
    'pending',
}


def _norm(value: Any) -> str:
    return str(value or '').strip()


def _canonical_guest_name(value: Any) -> str:
    text = unicodedata.normalize('NFKC', _norm(value))
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'^[\W_]+|[\W_]+$', '', text, flags=re.UNICODE).strip()
    return text.casefold()


def _is_placeholder_guest_name(value: Any) -> bool:
    text = _canonical_guest_name(value)
    if not text:
        return True
    compact = re.sub(r'[\W_]+', '', text, flags=re.UNICODE)
    return compact in _PLACEHOLDER_GUEST_NAMES


def _compose_guest_name(payload: dict[str, Any]) -> tuple[str, str | None, str | None]:
    first_name = _norm(payload.get('firstName') or payload.get('guestFirstName'))
    last_name = _norm(payload.get('lastName') or payload.get('guestLastName'))
    if first_name or last_name:
        full_name = ' '.join(value for value in (first_name, last_name) if value).strip()
        return full_name, first_name or None, last_name or None

    fallback = _norm(payload.get('guestName'))
    if fallback:
        return fallback, None, None
    return '', None, None


def _safe_snapshot(raw_snapshot: str | None) -> dict[str, Any]:
    if not raw_snapshot:
        return {}
    try:
        payload = json.loads(raw_snapshot)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def repair_beds24_placeholder_guest_names(
    db: Session,
    *,
    beds24_booking_ids: list[str] | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> dict[str, Any]:
    """Upgrade placeholder booking/guest names from freshly synced Beds24 snapshots.

    This is deliberately non-destructive: only blank/placeholder local names are
    eligible. A real local guest name is never overwritten by Beds24.
    """
    query = (
        db.query(Beds24BookingMap)
        .join(Booking, Booking.id == Beds24BookingMap.local_booking_id)
        .filter(func.lower(func.coalesce(Booking.status, "")).notin_(["cancelled", "canceled"]))
    )

    normalized_ids = sorted({str(value).strip() for value in (beds24_booking_ids or []) if str(value).strip()})
    if normalized_ids:
        query = query.filter(Beds24BookingMap.beds24_booking_id.in_(normalized_ids))
    if from_date:
        query = query.filter(Booking.check_in >= str(from_date))
    if to_date:
        query = query.filter(Booking.check_in <= str(to_date))

    rows = query.order_by(Beds24BookingMap.id.asc()).all()
    scanned = eligible = repaired = skipped_no_name = preserved_real_guest = 0

    for mapping in rows:
        booking = db.get(Booking, int(mapping.local_booking_id)) if mapping.local_booking_id else None
        if not booking or not _is_placeholder_guest_name(booking.guest_name):
            continue

        eligible += 1
        payload = _safe_snapshot(mapping.raw_snapshot)
        incoming_name, incoming_first, incoming_last = _compose_guest_name(payload)
        if not incoming_name or _is_placeholder_guest_name(incoming_name):
            skipped_no_name += 1
            continue

        guest = db.get(Guest, int(booking.guest_id)) if booking.guest_id else None
        if guest and not _is_placeholder_guest_name(guest.full_name):
            # Preserve a real local/manual guest identity if one already exists.
            booking.guest_name = guest.full_name
            preserved_real_guest += 1
        else:
            booking.guest_name = incoming_name
            if guest:
                guest.full_name = incoming_name
                if incoming_first and not _norm(guest.first_name):
                    guest.first_name = incoming_first
                if incoming_last and not _norm(guest.last_name):
                    guest.last_name = incoming_last
                db.add(guest)

        db.add(booking)
        repaired += 1

    scanned = len(rows)
    if repaired:
        db.commit()

    return {
        'scanned': scanned,
        'eligible_placeholders': eligible,
        'repaired': repaired,
        'skipped_no_name_in_snapshot': skipped_no_name,
        'preserved_real_guest': preserved_real_guest,
    }
