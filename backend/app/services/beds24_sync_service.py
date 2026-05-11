from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.core.settings import settings as app_settings
from app.models.entities import (
    Beds24BookingMap,
    Beds24GuestMap,
    Beds24SyncLog,
    Booking,
    BookingFolio,
    BookingFolioLine,
    BookingChannel,
    GuestMergeHistory,
    Guest,
    Receivable,
    Room,
)
from app.services.beds24_service import Beds24ApiError, fetch_beds24_bookings, load_beds24_settings
from app.services.guest_service import ensure_booking_folio


STATUS_MAP = {
    'new': 'confirmed',
    'reserved': 'confirmed',
    'confirmed': 'confirmed',
    'booked': 'confirmed',
    'arrived': 'checked_in',
    'checkedin': 'checked_in',
    'checked_in': 'checked_in',
    'inhouse': 'checked_in',
    'in_house': 'checked_in',
    'staying': 'checked_in',
    'checkedout': 'checked_out',
    'checked_out': 'checked_out',
    'departed': 'checked_out',
    'completed': 'checked_out',
    'cancelled': 'cancelled',
    'canceled': 'cancelled',
    'noshow': 'no_show',
    'no_show': 'no_show',
}

WEBHOOK_SECRET_HEADER_KEYS = (
    'x-beds24-secret',
    'x-webhook-secret',
    'x-api-key',
)

RESET_MODE_BEDS24_BOOKINGS = 'beds24_imported_bookings'
RESET_MODE_BEDS24_FOLIOS = 'beds24_imported_folios'
RESET_MODE_BEDS24_GUESTS = 'beds24_imported_guests_unlinked'
RESET_MODE_BEDS24_ALL = 'beds24_all'
RESET_MODE_LOCAL_TEST_FULL = 'local_test_full'
RESET_MODES = {
    RESET_MODE_BEDS24_BOOKINGS,
    RESET_MODE_BEDS24_FOLIOS,
    RESET_MODE_BEDS24_GUESTS,
    RESET_MODE_BEDS24_ALL,
    RESET_MODE_LOCAL_TEST_FULL,
}


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def _norm(value: Any) -> str:
    return str(value or '').strip()


def _norm_lower(value: Any) -> str:
    return _norm(value).lower()


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
    return compact in {
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


def _guest_name_is_distinct_enough(value: Any) -> bool:
    text = _canonical_guest_name(value)
    if _is_placeholder_guest_name(text):
        return False
    pieces = [piece for piece in text.split(' ') if piece]
    common_single_names = {'john', 'jane', 'maria', 'juan', 'guest', 'test'}
    if len(pieces) <= 1 and (len(text) < 8 or text in common_single_names):
        return False
    return True


def _as_int(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() == '':
            return None
        return int(value)
    except Exception:
        return None


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or str(value).strip() == '':
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _safe_json_dump(value: Any) -> str:
    try:
        return json.dumps(value or {}, ensure_ascii=True, separators=(',', ':'))
    except Exception:
        return '{}'


def _safe_json_load(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        out = json.loads(value)
        return out if isinstance(out, dict) else {}
    except Exception:
        return {}


def _extract_booking_id(payload: dict[str, Any]) -> str:
    for key in ('id', 'bookingId', 'booking_id', 'bookId', 'book_id'):
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ''


def _extract_channel_source(payload: dict[str, Any]) -> str:
    for key in ('referer', 'channel', 'apiSource', 'originalOTA', 'originalReferer', 'source'):
        value = _norm(payload.get(key))
        if value:
            return value
    return 'Beds24'


def _compose_guest_name(payload: dict[str, Any]) -> tuple[str, str]:
    first_name = _norm(payload.get('firstName'))
    last_name = _norm(payload.get('lastName'))
    if first_name and last_name:
        return f'{first_name} {last_name}'.strip(), 'firstName+lastName'
    if first_name:
        return first_name, 'firstName_only'
    if last_name:
        return last_name, 'lastName_only'

    legacy_first = _norm(payload.get('guestFirstName'))
    legacy_last = _norm(payload.get('guestLastName'))
    if legacy_first and legacy_last:
        return f'{legacy_first} {legacy_last}'.strip(), 'legacy_guestFirstName+guestLastName'
    if legacy_first:
        return legacy_first, 'legacy_guestFirstName_only'
    if legacy_last:
        return legacy_last, 'legacy_guestLastName_only'

    fallback = _norm(payload.get('guestName'))
    if fallback:
        return fallback, 'guestName_fallback'
    return 'Unnamed Guest', 'unnamed_fallback'


def _extract_guest_value(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = _norm(payload.get(key))
        if value:
            return value
    return ''


def _extract_check_in(payload: dict[str, Any]) -> str:
    return _extract_guest_value(payload, 'arrival', 'checkIn')


def _extract_check_out(payload: dict[str, Any]) -> str:
    return _extract_guest_value(payload, 'departure', 'checkOut')


def _extract_booking_time(payload: dict[str, Any]) -> str:
    return _extract_guest_value(payload, 'bookingTime', 'modifiedTime')


def _map_status(raw_status: Any, raw_sub_status: Any = None, raw_status_code: Any = None) -> str:
    status = _norm_lower(raw_status)
    sub_status = _norm_lower(raw_sub_status)
    status_code = _norm_lower(raw_status_code)

    for value in (sub_status, status, status_code):
        if not value:
            continue
        mapped = STATUS_MAP.get(value)
        if mapped:
            return mapped
        if value in {'cancelled', 'canceled'}:
            return 'cancelled'
        if value in {'no_show', 'noshow'}:
            return 'no_show'

    return 'confirmed'


def _append_unique_line(base: str | None, line: str | None) -> str | None:
    text = _norm(base)
    next_line = _norm(line)
    if not next_line:
        return text or None
    if not text:
        return next_line
    if next_line.lower() in text.lower():
        return text
    return f'{text}\n{next_line}'.strip()


def _compose_booking_note(payload: dict[str, Any]) -> str | None:
    note: str | None = None
    for key in ('comments', 'notes', 'message', 'groupNote', 'guestComments'):
        note = _append_unique_line(note, payload.get(key))
    return note


def _upsert_sync_log(
    db: Session,
    *,
    event_type: str,
    source_type: str,
    status: str,
    message: str,
    beds24_booking_id: str | None = None,
    local_booking_id: int | None = None,
    payload: Any = None,
) -> dict[str, Any]:
    row = Beds24SyncLog(
        event_type=_norm(event_type) or 'sync',
        source_type=_norm(source_type) or 'manual',
        beds24_booking_id=_norm(beds24_booking_id) or None,
        local_booking_id=local_booking_id,
        status=_norm(status) or 'info',
        message=_norm(message) or 'Beds24 sync event.',
        payload_json=_safe_json_dump(payload) if payload is not None else None,
        processed_at=_now_iso(),
    )
    db.add(row)
    db.commit()
    return {
        'id': row.id,
        'event_type': row.event_type,
        'source_type': row.source_type,
        'status': row.status,
        'message': row.message,
        'beds24_booking_id': row.beds24_booking_id,
        'local_booking_id': row.local_booking_id,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'processed_at': row.processed_at,
    }


def list_sync_logs(db: Session, *, limit: int = 200, status: str | None = None, source_type: str | None = None):
    query = db.query(Beds24SyncLog)
    if status:
        query = query.filter(Beds24SyncLog.status == _norm(status))
    if source_type:
        query = query.filter(Beds24SyncLog.source_type == _norm(source_type))
    rows = query.order_by(Beds24SyncLog.id.desc()).limit(max(1, min(int(limit or 200), 2000))).all()
    return [
        {
            'id': row.id,
            'event_type': row.event_type,
            'source_type': row.source_type,
            'beds24_booking_id': row.beds24_booking_id,
            'local_booking_id': row.local_booking_id,
            'status': row.status,
            'message': row.message,
            'payload_json': row.payload_json,
            'created_at': row.created_at.isoformat() if row.created_at else None,
            'processed_at': row.processed_at,
        }
        for row in rows
    ]


def _normalize_phone(value: str | None) -> str:
    text = _norm(value)
    if not text:
        return ''
    return ''.join(ch for ch in text if ch.isdigit() or ch == '+')


def _guest_identity_hash(payload: dict[str, Any]) -> str:
    first_name = _extract_guest_value(payload, 'firstName', 'guestFirstName')
    last_name = _extract_guest_value(payload, 'lastName', 'guestLastName')
    email = _extract_guest_value(payload, 'email', 'guestEmail')
    phone = _extract_guest_value(payload, 'phone', 'guestPhone')
    mobile = _extract_guest_value(payload, 'mobile', 'guestMobile')
    booking_id = _extract_booking_id(payload)

    pieces = [
        _norm_lower(email),
        _normalize_phone(phone),
        _normalize_phone(mobile),
        _norm_lower(first_name),
        _norm_lower(last_name),
        _norm_lower(_extract_guest_value(payload, 'company', 'guestCompany')),
    ]
    if not any(pieces):
        pieces.append(_norm_lower(booking_id))
    digest = hashlib.sha1('|'.join(pieces).encode('utf-8')).hexdigest()
    return f'beds24:{digest}'


def _beds24_guest_stable_keys(payload: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for key in ('guestId', 'guest_id', 'guestID', 'guestCode', 'guestKey', 'bookerId', 'customerId'):
        value = _norm(payload.get(key))
        if value:
            keys.append(f'beds24:{key}:{value}')
    return keys


def _guest_sort_key(row: Guest) -> tuple[int, int, int]:
    active_score = 0 if bool(row.is_active) else 1
    has_contact_score = 0 if (_norm(row.email) or _norm(row.phone)) else 1
    return (active_score, has_contact_score, int(row.id or 0))


def _find_guest_by_map(db: Session, keys: list[str]) -> Guest | None:
    for key in keys:
        row = db.query(Beds24GuestMap).filter(Beds24GuestMap.beds24_guest_key == key).first()
        if row and row.local_guest:
            return row.local_guest
    return None


def _lookup_explicit_int_map(raw_map: dict[str, Any], key: str | None) -> int | None:
    value = _norm(key)
    if not value:
        return None

    direct = raw_map.get(value)
    if direct is not None:
        try:
            return int(direct)
        except Exception:
            return None

    lowered = value.lower()
    for map_key, map_value in (raw_map or {}).items():
        if _norm_lower(map_key) != lowered:
            continue
        try:
            return int(map_value)
        except Exception:
            return None
    return None


def _find_guest_exact_email(db: Session, email: str) -> Guest | None:
    if not email:
        return None
    return db.query(Guest).filter(func.lower(Guest.email) == email.lower()).first()


def _find_guest_exact_phone(db: Session, phone: str) -> Guest | None:
    if not phone:
        return None
    return db.query(Guest).filter(Guest.phone == phone).first()


def _find_guest_name_phone(db: Session, full_name: str, phone: str) -> Guest | None:
    if not full_name or not phone:
        return None
    return db.query(Guest).filter(func.lower(Guest.full_name) == full_name.lower(), Guest.phone == phone).first()


def _find_guest_name_email(db: Session, full_name: str, email: str) -> Guest | None:
    if not full_name or not email:
        return None
    return db.query(Guest).filter(func.lower(Guest.full_name) == full_name.lower(), func.lower(Guest.email) == email.lower()).first()


def _find_guest_normalized_name(db: Session, full_name: str) -> Guest | None:
    canonical = _canonical_guest_name(full_name)
    if not canonical or not _guest_name_is_distinct_enough(full_name):
        return None
    candidates = (
        db.query(Guest)
        .filter(Guest.is_active == True)
        .all()
    )
    matches = [row for row in candidates if _canonical_guest_name(row.full_name) == canonical]
    if not matches:
        return None
    matches.sort(key=_guest_sort_key)
    return matches[0]


def _match_or_create_guest(db: Session, payload: dict[str, Any], *, auto_create_guest: bool) -> tuple[Guest | None, str]:
    email = _extract_guest_value(payload, 'email', 'guestEmail')
    phone = _extract_guest_value(payload, 'phone', 'guestPhone')
    mobile = _extract_guest_value(payload, 'mobile', 'guestMobile')
    full_name, _name_strategy = _compose_guest_name(payload)

    mapped = _find_guest_by_map(db, _beds24_guest_stable_keys(payload))
    if mapped:
        return mapped, 'beds24_guest_map'

    match = _find_guest_exact_email(db, email)
    if match:
        return match, 'exact_email'

    match = _find_guest_exact_phone(db, phone)
    if match:
        return match, 'exact_phone'

    match = _find_guest_exact_phone(db, mobile)
    if match:
        return match, 'exact_mobile'

    match = _find_guest_name_phone(db, full_name, phone)
    if match:
        return match, 'name_plus_phone'

    match = _find_guest_name_email(db, full_name, email)
    if match:
        return match, 'name_plus_email'

    match = _find_guest_normalized_name(db, full_name)
    if match:
        return match, 'normalized_name'

    if not auto_create_guest:
        return None, 'not_created_auto_create_disabled'

    if _is_placeholder_guest_name(full_name):
        return None, 'skipped_placeholder_guest'

    row = Guest(
        first_name=_extract_guest_value(payload, 'firstName', 'guestFirstName') or None,
        last_name=_extract_guest_value(payload, 'lastName', 'guestLastName') or None,
        full_name=full_name,
        phone=phone or mobile or None,
        email=email or None,
        address=_extract_guest_value(payload, 'address', 'guestAddress') or None,
        city=_extract_guest_value(payload, 'city', 'guestCity') or None,
        nationality=_extract_guest_value(payload, 'country2', 'country', 'guestCountry2', 'guestCountry') or None,
        birthday=None,
        company=_extract_guest_value(payload, 'company', 'guestCompany') or None,
        vip_flag=False,
        status_tags=None,
        notes=_append_unique_line(
            _append_unique_line(None, payload.get('comments') or payload.get('guestComments')),
            payload.get('notes'),
        ),
        is_active=True,
    )
    db.add(row)
    db.flush()
    return row, 'created_new_guest'


def _upsert_guest_map(db: Session, guest_key: str, guest_id: int, strategy: str):
    row = db.query(Beds24GuestMap).filter(Beds24GuestMap.beds24_guest_key == guest_key).first()
    if not row:
        row = Beds24GuestMap(
            beds24_guest_key=guest_key,
            local_guest_id=guest_id,
        )
    row.local_guest_id = int(guest_id)
    row.matching_strategy = _norm(strategy) or None
    row.last_synced_at = _now_iso()
    db.add(row)


def _upsert_guest_maps(db: Session, payload: dict[str, Any], guest_id: int, strategy: str):
    for key in [*_beds24_guest_stable_keys(payload), _guest_identity_hash(payload)]:
        _upsert_guest_map(db, key, guest_id, strategy)


def _update_guest_non_destructive(guest: Guest | None, payload: dict[str, Any]):
    if not guest:
        return
    if not _norm(guest.email):
        guest.email = _extract_guest_value(payload, 'email', 'guestEmail') or guest.email
    if not _norm(guest.phone):
        guest.phone = _extract_guest_value(payload, 'phone', 'mobile', 'guestPhone', 'guestMobile') or guest.phone
    if not _norm(guest.address):
        guest.address = _extract_guest_value(payload, 'address', 'guestAddress') or guest.address
    if not _norm(guest.city):
        guest.city = _extract_guest_value(payload, 'city', 'guestCity') or guest.city
    if not _norm(guest.company):
        guest.company = _extract_guest_value(payload, 'company', 'guestCompany') or guest.company
    if not _norm(guest.nationality):
        guest.nationality = _extract_guest_value(payload, 'country2', 'country', 'guestCountry2', 'guestCountry') or guest.nationality
    db_guest_notes = _norm(guest.notes)
    incoming_note = _compose_booking_note(payload)
    if not db_guest_notes and incoming_note:
        guest.notes = incoming_note


def _resolve_room(db: Session, settings: dict[str, Any], payload: dict[str, Any]) -> tuple[Room | None, list[str]]:
    warnings: list[str] = []
    room_id_raw = _norm(payload.get('roomId'))
    unit_id_raw = _norm(payload.get('unitId'))
    room_name = _norm(payload.get('roomName'))
    unit_name = _norm(payload.get('unitName'))

    room_map_by_room_id = settings.get('room_map_by_room_id') or {}
    room_map_by_unit_id = settings.get('room_map_by_unit_id') or {}
    auto_link_room = bool(settings.get('auto_link_room'))

    resolved: Room | None = None
    local_id = room_map_by_room_id.get(room_id_raw) if room_id_raw else None
    if local_id:
        resolved = db.get(Room, int(local_id))
    if not resolved:
        local_id = room_map_by_unit_id.get(unit_id_raw) if unit_id_raw else None
        if local_id:
            resolved = db.get(Room, int(local_id))

    if not resolved and auto_link_room:
        for candidate in (unit_name, room_name):
            value = _norm(candidate)
            if not value:
                continue
            resolved = (
                db.query(Room)
                .filter(Room.is_active == True)
                .filter(or_(func.lower(Room.name) == value.lower(), func.lower(Room.room_no) == value.lower()))
                .first()
            )
            if resolved:
                break

    if not resolved and (room_id_raw or unit_id_raw or room_name or unit_name):
        warnings.append('room mapping unresolved')
    return resolved, warnings


def _resolve_channel(db: Session, settings: dict[str, Any], payload: dict[str, Any]) -> tuple[BookingChannel | None, str, list[str]]:
    warnings: list[str] = []
    candidate_sources = [
        _extract_guest_value(payload, 'referer'),
        _extract_guest_value(payload, 'channel'),
        _extract_guest_value(payload, 'apiSource'),
        _extract_guest_value(payload, 'originalOTA'),
        _extract_guest_value(payload, 'originalReferer'),
    ]
    candidate_sources = [value for value in candidate_sources if value]
    source = candidate_sources[0] if candidate_sources else _extract_channel_source(payload)
    channel_map = settings.get('channel_map_by_source') or {}
    auto_link_channel = bool(settings.get('auto_link_channel'))

    resolved: BookingChannel | None = None
    for value in candidate_sources or [source]:
        mapped_id = _lookup_explicit_int_map(channel_map, value)
        if mapped_id:
            resolved = db.get(BookingChannel, mapped_id)
            if resolved:
                source = value
                break

    if not resolved and auto_link_channel:
        for value in candidate_sources or [source]:
            lookup = value.lower()
            resolved = (
                db.query(BookingChannel)
                .filter(BookingChannel.is_active == True)
                .filter(or_(func.lower(BookingChannel.name) == lookup, func.lower(BookingChannel.code) == lookup))
                .first()
            )
            if resolved:
                source = value
                break

    if not resolved and source:
        warnings.append('channel mapping unresolved')
    return resolved, source or 'Beds24', warnings


def _channel_is_prepaid(channel: BookingChannel | None) -> bool:
    if not channel:
        return False
    if bool(getattr(channel, 'is_prepaid', False)):
        return True
    mode = _norm_lower(getattr(channel, 'settlement_mode', None))
    if mode in {'prepaid', 'ota_prepaid', 'prepaid_ota', 'ota_payout', 'net_payout'}:
        return True
    return False


def _resolve_property_reference(settings: dict[str, Any], payload: dict[str, Any]) -> tuple[str | None, list[str]]:
    property_id = _norm(payload.get('propertyId'))
    if not property_id:
        return None, []
    auto_link_property = bool(settings.get('auto_link_property'))
    property_map = settings.get('property_map_by_id') or {}

    resolved = property_map.get(property_id)
    if not resolved:
        for map_key, map_value in property_map.items():
            if _norm(map_key) == property_id:
                resolved = map_value
                break
    warnings: list[str] = []
    should_warn_unresolved = auto_link_property or bool(property_map)
    if should_warn_unresolved and not _norm(resolved):
        warnings.append('property mapping unresolved')
    return (_norm(resolved) or None), warnings


def _upsert_receivable_mirror(db: Session, booking: Booking, payload: dict[str, Any]):
    charges = _as_float(payload.get('totalCharges'), _as_float(payload.get('price'), 0))
    payments = _as_float(payload.get('totalPayments'), 0)
    declared_balance = _as_float(payload.get('totalBalance'), charges - payments)

    gross_amount = max(charges, 0)
    amount_collected = max(min(payments, gross_amount), 0)
    balance_due = max(declared_balance, max(gross_amount - amount_collected, 0))

    receivable = (
        db.query(Receivable)
        .filter(
            Receivable.source_type == 'booking',
            Receivable.source_id == booking.id,
            Receivable.receivable_type == 'guest_balance',
        )
        .first()
    )
    if not receivable:
        receivable = Receivable(
            source_type='booking',
            source_id=booking.id,
            counterparty_name=booking.guest_name,
            receivable_type='guest_balance',
            transaction_date=booking.check_in or booking.check_out,
            due_date=booking.check_out,
            gross_amount=gross_amount,
            amount_collected=amount_collected,
            balance_due=balance_due,
            status='open',
            posted_at=booking.check_in or booking.check_out,
            notes='Beds24 mirrored receivable.',
            bir_include=False,
        )
    else:
        receivable.counterparty_name = booking.guest_name
        receivable.transaction_date = booking.check_in or receivable.transaction_date
        receivable.due_date = booking.check_out or receivable.due_date
        receivable.gross_amount = gross_amount
        receivable.amount_collected = amount_collected
        receivable.balance_due = balance_due
        receivable.notes = _append_unique_line(receivable.notes, 'Beds24 mirrored receivable.')
    if balance_due <= 0.0001:
        receivable.status = 'closed'
        receivable.closed_at = booking.check_out or _now_iso()[:10]
    else:
        receivable.status = 'open'
        receivable.closed_at = None
    db.add(receivable)


def _invoice_amount(raw: dict[str, Any]) -> float:
    for key in ('amount', 'value', 'total', 'price', 'gross', 'net'):
        if key in raw:
            return _as_float(raw.get(key), 0)
    return 0.0


def _invoice_line_total(raw: dict[str, Any]) -> float | None:
    # Beds24 often sends `lineTotal` with sign semantics
    # (e.g. payment rows can have negative lineTotal).
    for key in ('lineTotal', 'line_total'):
        if key not in raw:
            continue
        try:
            return float(raw.get(key))
        except Exception:
            return None
    return None


def _invoice_description(raw: dict[str, Any], fallback: str) -> str:
    for key in ('description', 'name', 'title', 'item', 'type', 'detail'):
        text = _norm(raw.get(key))
        if text:
            return text
    return fallback


def _extract_invoice_item_entries(payload: dict[str, Any], beds24_booking_id: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []

    def add_items(items: Any, *, parent_kind: str, parent_key: str):
        if not isinstance(items, list):
            return
        for index, row in enumerate(items):
            if not isinstance(row, dict):
                continue
            amount = _invoice_amount(row)
            line_total = _invoice_line_total(row)
            signed_amount = line_total if line_total is not None and abs(line_total) > 0.0001 else amount
            if abs(signed_amount) < 0.0001:
                continue
            row_id = _norm(row.get('id') or row.get('lineId') or row.get('itemId') or row.get('uid') or row.get('key'))
            if row_id:
                external_key = f'beds24:{beds24_booking_id}:invoice:{parent_key}:{row_id}'
            else:
                # Fallback key intentionally avoids amount/lineTotal so re-sync updates
                # the same mirror line even when values change.
                external_key = f'beds24:{beds24_booking_id}:invoice:{parent_key}:idx:{index}'

            description = _invoice_description(row, f'Beds24 {parent_kind.title()}')
            kind = _norm_lower(row.get('type') or row.get('kind') or row.get('entryType') or parent_kind)
            if not kind:
                kind = parent_kind
            has_negative_line_total = line_total is not None and line_total < 0

            lower_desc = description.lower()
            is_payment_like_kind = kind in {'payment', 'payments', 'deposit', 'deposits', 'paid'}
            is_refund_like_kind = kind in {'refund', 'refunded', 'reversal', 'reversed'}

            if is_refund_like_kind:
                line_type = 'refund'
                amount = abs(line_total) if line_total is not None and abs(line_total) > 0.0001 else abs(amount)
            elif is_payment_like_kind or has_negative_line_total or amount < 0:
                line_type = 'deposit' if 'deposit' in lower_desc else 'payment'
                amount = abs(line_total) if line_total is not None and abs(line_total) > 0.0001 else abs(amount)
            else:
                line_type = 'room_charge' if 'room' in lower_desc and 'tax' not in lower_desc else 'manual_charge'
                if line_total is not None and abs(line_total) > 0.0001:
                    amount = abs(line_total)
            entries.append(
                {
                    'external_line_key': external_key,
                    'line_type': line_type,
                    'description': description,
                    'amount': round(abs(amount), 4),
                }
            )

    for key, parent_kind in (
        ('invoiceItems', 'charge'),
        ('invoiceCharges', 'charge'),
        ('invoicePayments', 'payment'),
    ):
        add_items(payload.get(key), parent_kind=parent_kind, parent_key=key)

    invoice = payload.get('invoice')
    if isinstance(invoice, dict):
        for key, parent_kind in (
            ('items', 'charge'),
            ('charges', 'charge'),
            ('payments', 'payment'),
            ('lines', 'charge'),
        ):
            add_items(invoice.get(key), parent_kind=parent_kind, parent_key=f'invoice.{key}')

    return entries


def _summary_folio_entries(payload: dict[str, Any], beds24_booking_id: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    check_in = _extract_check_in(payload) or _now_iso()[:10]
    rate_description = _extract_guest_value(payload, 'rateDescription')

    room_amount = _as_float(payload.get('price'), 0)
    if abs(room_amount) > 0.0001:
        description = 'Room Charge'
        if rate_description:
            description = f'{description} ({rate_description})'
        entries.append(
            {
                'external_line_key': f'beds24:{beds24_booking_id}:room_charge',
                'line_type': 'room_charge',
                'description': description,
                'amount': round(room_amount, 4),
                'transaction_date': check_in,
            }
        )

    tax_amount = _as_float(payload.get('tax'), 0)
    if abs(tax_amount) > 0.0001:
        entries.append(
            {
                'external_line_key': f'beds24:{beds24_booking_id}:tax',
                'line_type': 'manual_charge',
                'description': 'Tax',
                'amount': round(tax_amount, 4),
                'transaction_date': check_in,
            }
        )

    deposit_amount = _as_float(payload.get('deposit'), 0)
    if abs(deposit_amount) > 0.0001:
        entries.append(
            {
                'external_line_key': f'beds24:{beds24_booking_id}:deposit',
                'line_type': 'deposit',
                'description': 'Beds24 Deposit / Payment',
                'amount': round(abs(deposit_amount), 4),
                'transaction_date': check_in,
            }
        )

    return entries


def _apply_prepaid_settlement_if_missing(
    entries: list[dict[str, Any]],
    beds24_booking_id: str,
    *,
    force_prepaid_settlement: bool,
) -> list[dict[str, Any]]:
    if not force_prepaid_settlement:
        return entries

    has_payment_lines = any(_norm_lower(row.get('line_type')) in {'payment', 'deposit'} for row in entries)
    if has_payment_lines:
        return entries

    charge_total = 0.0
    for row in entries:
        line_type = _norm_lower(row.get('line_type'))
        if line_type in {'room_charge', 'manual_charge', 'package_charge', 'extra_person', 'extra_bed', 'breakfast_addon'}:
            charge_total += _as_float(row.get('amount'), 0)
    if charge_total <= 0.0001:
        return entries

    entries.append(
        {
            'external_line_key': f'beds24:{beds24_booking_id}:prepaid_settlement',
            'line_type': 'deposit',
            'description': 'Prepaid OTA settlement',
            'amount': round(abs(charge_total), 4),
        }
    )
    return entries


def _build_folio_entries(payload: dict[str, Any], beds24_booking_id: str, *, force_prepaid_settlement: bool = False) -> list[dict[str, Any]]:
    invoice_entries = _extract_invoice_item_entries(payload, beds24_booking_id)
    if invoice_entries:
        return _apply_prepaid_settlement_if_missing(
            invoice_entries,
            beds24_booking_id,
            force_prepaid_settlement=force_prepaid_settlement,
        )
    summary_entries = _summary_folio_entries(payload, beds24_booking_id)
    return _apply_prepaid_settlement_if_missing(
        summary_entries,
        beds24_booking_id,
        force_prepaid_settlement=force_prepaid_settlement,
    )


def _is_legacy_beds24_line(line: BookingFolioLine, booking: Booking) -> bool:
    created_by = _norm_lower(line.created_by)
    if not created_by.startswith('beds24'):
        return False
    reference_no = _norm(line.reference_no)
    if reference_no != f'BOOK-{booking.id}':
        return False
    notes = _norm_lower(line.notes)
    if 'auto-created from booking' in notes:
        return True
    if _norm_lower(line.description) in {'booking deposit', f'room charge for booking #{booking.id}'}:
        return True
    return False


def _upsert_folio_mirror(
    db: Session,
    booking: Booking,
    payload: dict[str, Any],
    *,
    triggered_by: str | None = None,
    clear_existing_mirror: bool = False,
    force_prepaid_settlement: bool = False,
) -> dict[str, Any]:
    folio = ensure_booking_folio(db, booking, username=triggered_by or 'beds24_sync', create_default_lines=False)
    beds24_booking_id = _extract_booking_id(payload) or _norm(booking.external_booking_id) or str(booking.id)
    entries = _build_folio_entries(
        payload,
        beds24_booking_id,
        force_prepaid_settlement=force_prepaid_settlement,
    )
    desired_by_key = {entry['external_line_key']: entry for entry in entries if entry.get('external_line_key')}
    now_date = _extract_check_in(payload) or booking.check_in or _now_iso()[:10]

    existing_lines = (
        db.query(BookingFolioLine)
        .filter(BookingFolioLine.folio_id == folio.id)
        .all()
    )

    legacy_removed = 0
    for line in existing_lines:
        # Cleanup old Beds24-generated default lines from earlier mirror behavior.
        if _is_legacy_beds24_line(line, booking):
            db.delete(line)
            legacy_removed += 1

    mirror_lines = [line for line in existing_lines if _norm_lower(line.external_source) == 'beds24' and _norm(line.external_line_key)]
    if clear_existing_mirror:
        for line in mirror_lines:
            db.delete(line)
        mirror_lines = []

    by_key = {line.external_line_key: line for line in mirror_lines if line.external_line_key}

    upserted = 0
    for key, entry in desired_by_key.items():
        line = by_key.get(key)
        if not line:
            line = BookingFolioLine(
                folio_id=folio.id,
                external_source='beds24',
                external_line_key=key,
                created_by=triggered_by or 'beds24_sync',
            )
        line.line_type = entry.get('line_type') or 'manual_charge'
        line.description = _norm(entry.get('description')) or 'Beds24 Mirror Line'
        line.quantity = 1
        line.unit_price = round(_as_float(entry.get('amount'), 0), 4)
        line.amount = round(_as_float(entry.get('amount'), 0), 4)
        line.transaction_date = _norm(entry.get('transaction_date')) or now_date
        line.reference_no = key
        line.notes = _append_unique_line(line.notes, 'Beds24 mirrored line')
        line.external_source = 'beds24'
        line.external_line_key = key
        db.add(line)
        upserted += 1

    stale_keys = [line.external_line_key for line in mirror_lines if line.external_line_key not in desired_by_key]
    for key in stale_keys:
        line = by_key.get(key)
        if line:
            db.delete(line)

    return {
        'folio_id': folio.id,
        'upserted_lines': upserted,
        'removed_lines': len(stale_keys) + legacy_removed,
        'legacy_lines_removed': legacy_removed,
    }


def sync_booking_payload(
    db: Session,
    booking_payload: dict[str, Any],
    *,
    source_type: str = 'manual',
    triggered_by: str | None = None,
    clear_existing_mirror: bool = False,
    force_folio_mirror: bool = False,
) -> dict[str, Any]:
    beds24_id = _extract_booking_id(booking_payload)
    if not beds24_id:
        raise ValueError('Beds24 booking payload does not contain booking id.')

    settings = load_beds24_settings(db)
    warnings: list[str] = []
    guest_name, guest_name_strategy = _compose_guest_name(booking_payload)
    check_in = _extract_check_in(booking_payload)
    check_out = _extract_check_out(booking_payload)
    booking_time = _extract_booking_time(booking_payload)
    booking_note = _compose_booking_note(booking_payload)

    map_row = db.query(Beds24BookingMap).filter(Beds24BookingMap.beds24_booking_id == beds24_id).first()
    guest, strategy = _match_or_create_guest(db, booking_payload, auto_create_guest=bool(settings.get('auto_create_guest')))
    _update_guest_non_destructive(guest, booking_payload)
    if guest:
        _upsert_guest_maps(db, booking_payload, guest.id, strategy)
    else:
        warnings.append('guest not linked')
        if strategy == 'skipped_placeholder_guest':
            warnings.append('placeholder guest not auto-merged')

    room, room_warnings = _resolve_room(db, settings, booking_payload)
    warnings.extend(room_warnings)
    channel, channel_name, channel_warnings = _resolve_channel(db, settings, booking_payload)
    warnings.extend(channel_warnings)
    channel_prepaid = _channel_is_prepaid(channel)
    property_ref, property_warnings = _resolve_property_reference(settings, booking_payload)
    warnings.extend(property_warnings)

    booking = None
    if map_row and map_row.local_booking_id:
        booking = db.get(Booking, int(map_row.local_booking_id))
    if not booking:
        booking = (
            db.query(Booking)
            .filter(
                Booking.external_source == 'beds24',
                Booking.external_booking_id == beds24_id,
            )
            .first()
        )

    booking_existed = bool(booking)
    if not booking:
        booking = Booking(
            guest_name=guest_name,
            room_name='',
            channel='Beds24',
            status='confirmed',
            external_source='beds24',
            external_booking_id=beds24_id,
        )
        db.add(booking)
        db.flush()

    room_name = _norm(booking_payload.get('roomName')) or _norm(booking_payload.get('unitName')) or (room.name if room else booking.room_name)
    local_status = _map_status(booking_payload.get('status'), booking_payload.get('subStatus'), booking_payload.get('statusCode'))

    booking.guest_id = guest.id if guest else None
    booking.guest_name = guest.full_name if guest else (guest_name or booking.guest_name or 'Unnamed Guest')
    booking.room_id = room.id if room else None
    booking.room_type_id = room.room_type_id if room and room.room_type_id else booking.room_type_id
    booking.channel_id = channel.id if channel else None
    booking.room_name = room_name or booking.room_name or ''
    booking.room_type = room.room_type.name if room and room.room_type else booking.room_type
    booking.channel = channel.name if channel else (channel_name or booking.channel or 'Beds24')
    booking.status = local_status
    booking.check_in = check_in or booking.check_in
    booking.check_out = check_out or booking.check_out
    booking.gross_amount = _as_float(booking_payload.get('totalCharges'), _as_float(booking_payload.get('price'), booking.gross_amount or 0))
    booking.deposit_amount = _as_float(booking_payload.get('deposit'), booking.deposit_amount or 0)
    booking.notes = _append_unique_line(booking.notes, booking_note)
    booking.external_source = 'beds24'
    booking.external_booking_id = beds24_id
    db.add(booking)
    db.flush()

    if not map_row:
        map_row = Beds24BookingMap(beds24_booking_id=beds24_id)
    map_row.local_booking_id = booking.id
    map_row.local_guest_id = guest.id if guest else None
    map_row.beds24_property_id = _norm(booking_payload.get('propertyId')) or None
    map_row.beds24_room_id = _norm(booking_payload.get('roomId')) or None
    map_row.beds24_room_name = _norm(booking_payload.get('roomName')) or None
    map_row.beds24_unit_id = _norm(booking_payload.get('unitId')) or None
    map_row.beds24_unit_name = _norm(booking_payload.get('unitName')) or None
    map_row.beds24_channel_source = channel_name or None
    map_row.beds24_group_id = _extract_guest_value(booking_payload, 'groupId', 'masterId') or None
    map_row.beds24_status = _norm(booking_payload.get('status')) or None
    map_row.beds24_check_in = check_in or None
    map_row.beds24_check_out = check_out or None
    map_row.beds24_last_night = _norm(booking_payload.get('lastNight')) or None
    map_row.beds24_booking_time = booking_time or None
    map_row.beds24_num_adult = _as_int(booking_payload.get('numAdult'))
    map_row.beds24_num_child = _as_int(booking_payload.get('numChild'))
    map_row.beds24_reference = _norm(booking_payload.get('reference')) or None
    map_row.beds24_original_ota = _norm(booking_payload.get('originalOTA')) or None
    map_row.beds24_referer = _norm(booking_payload.get('referer')) or None
    map_row.beds24_original_referer = _norm(booking_payload.get('originalReferer')) or None
    map_row.beds24_offer_id = _norm(booking_payload.get('offerId')) or None
    map_row.beds24_voucher = _norm(booking_payload.get('voucher')) or None
    map_row.beds24_rate_description = _norm(booking_payload.get('rateDescription')) or None
    map_row.beds24_price = _as_float(booking_payload.get('price')) if _norm(booking_payload.get('price')) else None
    map_row.beds24_tax = _as_float(booking_payload.get('tax')) if _norm(booking_payload.get('tax')) else None
    map_row.beds24_deposit = _as_float(booking_payload.get('deposit')) if _norm(booking_payload.get('deposit')) else None
    map_row.beds24_commission = _as_float(booking_payload.get('commission')) if _norm(booking_payload.get('commission')) else None
    map_row.beds24_total_charges = _as_float(booking_payload.get('totalCharges')) if _norm(booking_payload.get('totalCharges')) else None
    map_row.beds24_total_payments = _as_float(booking_payload.get('totalPayments')) if _norm(booking_payload.get('totalPayments')) else None
    map_row.beds24_total_balance = _as_float(booking_payload.get('totalBalance')) if _norm(booking_payload.get('totalBalance')) else None
    map_row.sync_status = 'synced'
    map_row.last_synced_at = _now_iso()
    map_row.last_error = None
    map_row.raw_snapshot = _safe_json_dump(booking_payload)
    db.add(map_row)

    folio_result = None
    if bool(settings.get('auto_create_folio_mirror')) or bool(force_folio_mirror):
        folio_result = _upsert_folio_mirror(
            db,
            booking,
            booking_payload,
            triggered_by=triggered_by or 'beds24_sync',
            clear_existing_mirror=bool(clear_existing_mirror),
            force_prepaid_settlement=bool(channel_prepaid),
        )
    if bool(settings.get('auto_create_receivable_mirror')):
        _upsert_receivable_mirror(db, booking, booking_payload)

    db.commit()

    message = f'Synced Beds24 booking {beds24_id} to ERP booking #{booking.id}.'
    if warnings:
        message = f'{message} Warnings: {", ".join(sorted(set(warnings)))}.'
    _upsert_sync_log(
        db,
        event_type='booking_upsert',
        source_type=source_type,
        status='success',
        message=message,
        beds24_booking_id=beds24_id,
        local_booking_id=booking.id,
        payload={
            'warnings': warnings,
            'guest_match_strategy': strategy,
            'guest_name_strategy': guest_name_strategy,
            'resolved_property_ref': property_ref,
            'channel_is_prepaid': bool(channel_prepaid),
            'folio_mirror': folio_result,
            'clear_existing_mirror': bool(clear_existing_mirror),
        },
    )
    return {
        'ok': True,
        'beds24_booking_id': beds24_id,
        'local_booking_id': booking.id,
        'local_guest_id': booking.guest_id,
        'status': 'synced',
        'action': 'updated' if booking_existed else 'created',
        'guest_match_strategy': strategy,
        'guest_name_strategy': guest_name_strategy,
        'resolved_guest_name': booking.guest_name,
        'resolved_property_ref': property_ref,
        'channel_is_prepaid': bool(channel_prepaid),
        'warnings': warnings,
        'folio_mirror': folio_result,
        'mirror_rebuilt': bool(clear_existing_mirror),
    }


def _mark_sync_error(db: Session, beds24_booking_id: str | None, message: str):
    booking_id = _norm(beds24_booking_id) or None
    if booking_id:
        map_row = db.query(Beds24BookingMap).filter(Beds24BookingMap.beds24_booking_id == booking_id).first()
        if not map_row:
            map_row = Beds24BookingMap(beds24_booking_id=booking_id)
        map_row.sync_status = 'error'
        map_row.last_synced_at = _now_iso()
        map_row.last_error = _norm(message)[:4000]
        db.add(map_row)
    db.commit()


def sync_booking_by_id(
    db: Session,
    booking_id: str,
    *,
    source_type: str = 'manual',
    include_invoice_items: bool | None = None,
    triggered_by: str | None = None,
    replace_mirror: bool = False,
    force_folio_mirror: bool = False,
) -> dict[str, Any]:
    booking_id = _norm(booking_id)
    if not booking_id:
        raise ValueError('booking_id is required.')
    try:
        bookings, _payload, _settings = fetch_beds24_bookings(
            db,
            booking_id=booking_id,
            include_invoice_items=include_invoice_items,
        )
        if not bookings:
            raise ValueError(f'Beds24 booking {booking_id} not found.')
        row = bookings[0]
        result = sync_booking_payload(
            db,
            row,
            source_type=source_type,
            triggered_by=triggered_by,
            clear_existing_mirror=replace_mirror,
            force_folio_mirror=force_folio_mirror,
        )
        return result
    except Exception as exc:
        db.rollback()
        try:
            _mark_sync_error(db, booking_id, str(exc))
            _upsert_sync_log(
                db,
                event_type='booking_upsert',
                source_type=source_type,
                status='error',
                message=f'Failed syncing Beds24 booking {booking_id}: {exc}',
                beds24_booking_id=booking_id,
            )
        except Exception:
            db.rollback()
        raise


def sync_recent_bookings(
    db: Session,
    *,
    limit: int = 25,
    status: str | None = None,
    filter_value: str | None = None,
    include_invoice_items: bool | None = None,
    source_type: str = 'manual',
    triggered_by: str | None = None,
) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit or 25), 200))
    bookings, _payload, _settings = fetch_beds24_bookings(
        db,
        status=status,
        filter_value=filter_value,
        limit=safe_limit,
        include_invoice_items=include_invoice_items,
    )
    results: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for row in bookings[:safe_limit]:
        bid = _extract_booking_id(row)
        try:
            results.append(sync_booking_payload(db, row, source_type=source_type, triggered_by=triggered_by))
        except Exception as exc:
            db.rollback()
            try:
                _mark_sync_error(db, bid, str(exc))
                _upsert_sync_log(
                    db,
                    event_type='booking_upsert',
                    source_type=source_type,
                    status='error',
                    message=f'Failed syncing Beds24 booking {bid or "unknown"}: {exc}',
                    beds24_booking_id=bid or None,
                )
            except Exception:
                db.rollback()
            failed.append({'beds24_booking_id': bid or None, 'error': str(exc)})

    summary = {
        'ok': True,
        'requested_limit': safe_limit,
        'fetched': len(bookings),
        'synced': len(results),
        'failed': len(failed),
        'results': results,
        'errors': failed,
    }
    _upsert_sync_log(
        db,
        event_type='sync_recent',
        source_type=source_type,
        status='success' if not failed else 'partial',
        message=f'Recent Beds24 sync finished: {len(results)} synced, {len(failed)} failed.',
        payload={'status': status, 'filter': filter_value, 'limit': safe_limit},
    )
    return summary


def _parse_date(value: str, label: str) -> datetime:
    try:
        return datetime.strptime(_norm(value), '%Y-%m-%d')
    except Exception as exc:
        raise ValueError(f'{label} must be in YYYY-MM-DD format.') from exc


def _date_chunks(from_date: str, to_date: str, chunk_days: int) -> list[tuple[str, str]]:
    start = _parse_date(from_date, 'from_date')
    end = _parse_date(to_date, 'to_date')
    if end < start:
        raise ValueError('to_date cannot be earlier than from_date.')
    chunks: list[tuple[str, str]] = []
    cursor = start
    step = max(1, min(int(chunk_days or 31), 92))
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=step - 1), end)
        chunks.append((cursor.strftime('%Y-%m-%d'), chunk_end.strftime('%Y-%m-%d')))
        cursor = chunk_end + timedelta(days=1)
    return chunks


def backfill_bookings_by_date_range(
    db: Session,
    *,
    from_date: str,
    to_date: str,
    property_id: str | None = None,
    statuses: list[str] | None = None,
    include_invoice_items: bool | None = None,
    dry_run: bool = False,
    chunk_days: int = 31,
    source_type: str = 'backfill',
    triggered_by: str | None = None,
) -> dict[str, Any]:
    chunks = _date_chunks(from_date, to_date, chunk_days)
    status_values = [_norm(value) for value in (statuses or []) if _norm(value)]
    if not status_values:
        status_values = [None]  # type: ignore[list-item]

    _upsert_sync_log(
        db,
        event_type='backfill_start',
        source_type=source_type,
        status='info',
        message=f'Beds24 historical import started for {from_date} to {to_date}.',
        payload={
            'from_date': from_date,
            'to_date': to_date,
            'property_id': property_id,
            'statuses': [value for value in status_values if value],
            'include_invoice_items': include_invoice_items,
            'dry_run': bool(dry_run),
            'chunk_days': chunk_days,
            'triggered_by': triggered_by,
        },
    )

    seen_ids: set[str] = set()
    fetched = created = updated = skipped = failed = 0
    errors: list[dict[str, Any]] = []
    chunk_summaries: list[dict[str, Any]] = []
    sample: list[dict[str, Any]] = []
    page_limit = 99 if include_invoice_items else 200

    for chunk_from, chunk_to in chunks:
        for status in status_values:
            offset = 0
            chunk_fetched = chunk_created = chunk_updated = chunk_skipped = chunk_failed = 0
            while True:
                try:
                    bookings, _payload, _settings = fetch_beds24_bookings(
                        db,
                        status=status,
                        limit=page_limit,
                        offset=offset,
                        arrival_from=chunk_from,
                        arrival_to=chunk_to,
                        property_id=property_id,
                        include_invoice_items=include_invoice_items,
                    )
                except Exception as exc:
                    failed += 1
                    chunk_failed += 1
                    errors.append({
                        'range': f'{chunk_from} to {chunk_to}',
                        'status': status,
                        'offset': offset,
                        'error': str(exc),
                    })
                    break

                if not bookings:
                    break

                fetched += len(bookings)
                chunk_fetched += len(bookings)
                for booking_payload in bookings:
                    beds24_id = _extract_booking_id(booking_payload)
                    if not beds24_id:
                        skipped += 1
                        chunk_skipped += 1
                        continue
                    if beds24_id in seen_ids:
                        skipped += 1
                        chunk_skipped += 1
                        continue
                    seen_ids.add(beds24_id)

                    existing = (
                        db.query(Beds24BookingMap)
                        .filter(Beds24BookingMap.beds24_booking_id == beds24_id)
                        .first()
                    )
                    if dry_run:
                        action = 'updated' if existing and existing.local_booking_id else 'created'
                        if action == 'updated':
                            updated += 1
                            chunk_updated += 1
                        else:
                            created += 1
                            chunk_created += 1
                        if len(sample) < 25:
                            sample.append({
                                'beds24_booking_id': beds24_id,
                                'action': action,
                                'guest_name': _compose_guest_name(booking_payload)[0],
                                'check_in': _extract_check_in(booking_payload),
                                'check_out': _extract_check_out(booking_payload),
                            })
                        continue

                    try:
                        result = sync_booking_payload(
                            db,
                            booking_payload,
                            source_type=source_type,
                            triggered_by=triggered_by,
                            force_folio_mirror=include_invoice_items is True,
                        )
                        if result.get('action') == 'created':
                            created += 1
                            chunk_created += 1
                        else:
                            updated += 1
                            chunk_updated += 1
                        if len(sample) < 25:
                            sample.append({
                                'beds24_booking_id': beds24_id,
                                'local_booking_id': result.get('local_booking_id'),
                                'action': result.get('action'),
                                'guest_match_strategy': result.get('guest_match_strategy'),
                            })
                    except Exception as exc:
                        db.rollback()
                        failed += 1
                        chunk_failed += 1
                        errors.append({'beds24_booking_id': beds24_id, 'error': str(exc)})
                        try:
                            _mark_sync_error(db, beds24_id, str(exc))
                            _upsert_sync_log(
                                db,
                                event_type='booking_upsert',
                                source_type=source_type,
                                status='error',
                                message=f'Failed backfill syncing Beds24 booking {beds24_id}: {exc}',
                                beds24_booking_id=beds24_id,
                            )
                        except Exception:
                            db.rollback()

                if len(bookings) < page_limit:
                    break
                offset += page_limit

            chunk_summaries.append({
                'from_date': chunk_from,
                'to_date': chunk_to,
                'status': status,
                'fetched': chunk_fetched,
                'created': chunk_created,
                'updated': chunk_updated,
                'skipped': chunk_skipped,
                'failed': chunk_failed,
            })

    summary = {
        'ok': failed == 0,
        'dry_run': bool(dry_run),
        'from_date': from_date,
        'to_date': to_date,
        'property_id': property_id,
        'statuses': [value for value in status_values if value],
        'chunks': len(chunks),
        'fetched': fetched,
        'unique_seen': len(seen_ids),
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'failed': failed,
        'errors': errors[:100],
        'chunk_summaries': chunk_summaries,
        'sample': sample,
    }
    _upsert_sync_log(
        db,
        event_type='backfill_finish',
        source_type=source_type,
        status='success' if failed == 0 else 'partial',
        message=(
            f'Beds24 historical import finished: {fetched} fetched, '
            f'{created} created, {updated} updated, {skipped} skipped, {failed} failed.'
        ),
        payload=summary,
    )
    return summary


def rebuild_booking_mirror_by_id(
    db: Session,
    booking_id: str,
    *,
    include_invoice_items: bool | None = None,
    triggered_by: str | None = None,
) -> dict[str, Any]:
    # Safe rebuild mode for one Beds24 booking mirror: keep the same local booking row when possible,
    # clear stale Beds24-generated mirror lines, then rebuild from latest Beds24 payload.
    return sync_booking_by_id(
        db,
        booking_id,
        source_type='manual',
        include_invoice_items=include_invoice_items,
        triggered_by=triggered_by,
        replace_mirror=True,
        force_folio_mirror=True,
    )


def list_mapping_helpers(db: Session) -> dict[str, Any]:
    rooms = (
        db.query(Room)
        .order_by(Room.id.asc())
        .all()
    )
    channels = (
        db.query(BookingChannel)
        .order_by(BookingChannel.id.asc())
        .all()
    )
    return {
        'rooms': [
            {
                'id': row.id,
                'room_no': row.room_no,
                'name': row.name,
                'is_active': bool(row.is_active),
            }
            for row in rooms
        ],
        'channels': [
            {
                'id': row.id,
                'code': row.code,
                'name': row.name,
                'is_prepaid': bool(getattr(row, 'is_prepaid', False)),
                'is_active': bool(row.is_active),
            }
            for row in channels
        ],
    }


def list_sync_state(db: Session, *, limit: int = 100) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit or 100), 1000))
    rows = (
        db.query(Beds24BookingMap)
        .order_by(Beds24BookingMap.id.desc())
        .limit(safe_limit)
        .all()
    )
    settings = load_beds24_settings(db)
    auto_link_property = bool(settings.get('auto_link_property'))
    property_map_by_id = settings.get('property_map_by_id') or {}

    out: list[dict[str, Any]] = []
    for row in rows:
        snapshot = _safe_json_load(row.raw_snapshot)
        booking = row.local_booking
        warnings: list[str] = []

        local_booking_id = booking.id if booking else row.local_booking_id
        local_guest_id = booking.guest_id if booking else row.local_guest_id
        local_room_id = booking.room_id if booking else None
        local_channel_id = booking.channel_id if booking else None

        source_candidates = [
            _extract_guest_value(snapshot, 'referer'),
            _extract_guest_value(snapshot, 'channel'),
            _extract_guest_value(snapshot, 'apiSource'),
            _extract_guest_value(snapshot, 'originalOTA'),
            _extract_guest_value(snapshot, 'originalReferer'),
            _norm(row.beds24_channel_source),
            _norm(row.beds24_referer),
            _norm(row.beds24_original_ota),
            _norm(row.beds24_original_referer),
        ]
        source_candidates = [value for value in source_candidates if value]

        if (row.beds24_room_id or row.beds24_unit_id or row.beds24_room_name or row.beds24_unit_name) and not local_room_id:
            warnings.append('room mapping unresolved')
        if source_candidates and not local_channel_id:
            warnings.append('channel mapping unresolved')
        if row.beds24_property_id and (auto_link_property or bool(property_map_by_id)) and not property_map_by_id.get(str(row.beds24_property_id)):
            warnings.append('property mapping unresolved')

        out.append(
            {
                'beds24_booking_id': row.beds24_booking_id,
                'beds24_property_id': row.beds24_property_id,
                'beds24_room_id': row.beds24_room_id,
                'beds24_unit_id': row.beds24_unit_id,
                'beds24_referer': _extract_guest_value(snapshot, 'referer') or row.beds24_referer,
                'beds24_channel': _extract_guest_value(snapshot, 'channel'),
                'beds24_api_source': _extract_guest_value(snapshot, 'apiSource'),
                'local_booking_id': local_booking_id,
                'local_guest_id': local_guest_id,
                'local_room_id': local_room_id,
                'local_channel_id': local_channel_id,
                'sync_status': row.sync_status,
                'warning_text': ', '.join(sorted(set(warnings))),
                'warnings': sorted(set(warnings)),
                'last_synced_at': row.last_synced_at,
                'updated_at': row.updated_at.isoformat() if row.updated_at else None,
            }
        )
    return out


def _validate_reset_mode(mode: str) -> str:
    normalized = _norm(mode)
    if normalized not in RESET_MODES:
        raise ValueError(f'Unsupported reset mode: {mode}')
    return normalized


def _beds24_booking_query(db: Session):
    return db.query(Booking).filter(func.lower(func.coalesce(Booking.external_source, '')) == 'beds24')


def _beds24_booking_ids(db: Session) -> list[int]:
    return [int(row.id) for row in _beds24_booking_query(db).all()]


def _beds24_mapped_guest_ids(db: Session) -> list[int]:
    rows = (
        db.query(Beds24BookingMap.local_guest_id)
        .filter(Beds24BookingMap.local_guest_id.isnot(None))
        .group_by(Beds24BookingMap.local_guest_id)
        .all()
    )
    return [int(row[0]) for row in rows if row and row[0] is not None]


def _guest_is_unlinked(db: Session, guest_id: int) -> bool:
    has_booking = db.query(Booking.id).filter(Booking.guest_id == int(guest_id)).first() is not None
    if has_booking:
        return False
    has_folio = db.query(BookingFolio.id).filter(BookingFolio.guest_id == int(guest_id)).first() is not None
    if has_folio:
        return False
    return True


def _delete_beds24_mirror_folios(db: Session) -> dict[str, int]:
    folios = (
        db.query(BookingFolio)
        .options(
            selectinload(BookingFolio.lines),
            selectinload(BookingFolio.booking),
        )
        .join(Booking, Booking.id == BookingFolio.booking_id)
        .filter(func.lower(func.coalesce(Booking.external_source, '')) == 'beds24')
        .all()
    )
    lines_deleted = 0
    folios_deleted = 0

    for folio in folios:
        booking = folio.booking
        removed_this_folio = 0
        for line in list(folio.lines or []):
            is_mirror_line = _norm_lower(line.external_source) == 'beds24' or _is_legacy_beds24_line(line, booking)
            if not is_mirror_line:
                continue
            db.delete(line)
            removed_this_folio += 1
            lines_deleted += 1

        if removed_this_folio:
            db.flush()
        remaining = (
            db.query(BookingFolioLine.id)
            .filter(BookingFolioLine.folio_id == folio.id)
            .count()
        )
        if remaining == 0:
            db.delete(folio)
            folios_deleted += 1

    return {
        'beds24_folio_lines_deleted': lines_deleted,
        'beds24_folios_deleted': folios_deleted,
    }


def preview_reset_mode(db: Session, mode: str) -> dict[str, Any]:
    mode = _validate_reset_mode(mode)
    beds24_booking_ids = _beds24_booking_ids(db)
    beds24_booking_count = len(beds24_booking_ids)
    mapped_guest_ids = _beds24_mapped_guest_ids(db)

    preview: dict[str, Any] = {
        'mode': mode,
        'required_confirmation': f'RESET {mode}',
        'environment': app_settings.environment,
        'counts': {},
        'notes': [],
    }

    if mode in {RESET_MODE_BEDS24_FOLIOS, RESET_MODE_BEDS24_ALL}:
        mirror_line_count = (
            db.query(BookingFolioLine.id)
            .join(BookingFolio, BookingFolio.id == BookingFolioLine.folio_id)
            .join(Booking, Booking.id == BookingFolio.booking_id)
            .filter(func.lower(func.coalesce(Booking.external_source, '')) == 'beds24')
            .filter(BookingFolioLine.external_source == 'beds24')
            .count()
        )
        beds24_folio_count = (
            db.query(BookingFolio.id)
            .join(Booking, Booking.id == BookingFolio.booking_id)
            .filter(func.lower(func.coalesce(Booking.external_source, '')) == 'beds24')
            .count()
        )
        preview['counts']['beds24_folios'] = int(beds24_folio_count)
        preview['counts']['beds24_folio_mirror_lines'] = int(mirror_line_count)

    if mode in {RESET_MODE_BEDS24_BOOKINGS, RESET_MODE_BEDS24_ALL}:
        preview['counts']['beds24_bookings'] = int(beds24_booking_count)
        if beds24_booking_ids:
            preview['counts']['beds24_booking_maps'] = int(
                db.query(Beds24BookingMap.id)
                .filter(Beds24BookingMap.local_booking_id.in_(beds24_booking_ids))
                .count()
            )
        else:
            preview['counts']['beds24_booking_maps'] = 0

    if mode in {RESET_MODE_BEDS24_GUESTS, RESET_MODE_BEDS24_ALL}:
        removable_guest_ids = [gid for gid in mapped_guest_ids if _guest_is_unlinked(db, gid)]
        preview['counts']['beds24_mapped_guests_total'] = int(len(mapped_guest_ids))
        preview['counts']['beds24_unlinked_guests_removable'] = int(len(removable_guest_ids))

    if mode == RESET_MODE_BEDS24_ALL:
        preview['counts']['beds24_booking_maps_total'] = int(db.query(Beds24BookingMap.id).count())
        preview['counts']['beds24_guest_maps_total'] = int(db.query(Beds24GuestMap.id).count())
        preview['counts']['beds24_sync_logs_total'] = int(db.query(Beds24SyncLog.id).count())
        preview['notes'].append('Preserves unrelated non-Beds24 bookings and non-Beds24 guests.')

    if mode == RESET_MODE_LOCAL_TEST_FULL:
        preview['counts']['all_bookings'] = int(db.query(Booking.id).count())
        preview['counts']['all_guests'] = int(db.query(Guest.id).count())
        preview['counts']['all_folios'] = int(db.query(BookingFolio.id).count())
        preview['counts']['all_folio_lines'] = int(db.query(BookingFolioLine.id).count())
        preview['counts']['beds24_maps_total'] = int(db.query(Beds24BookingMap.id).count())
        preview['counts']['beds24_guest_maps_total'] = int(db.query(Beds24GuestMap.id).count())
        preview['counts']['beds24_sync_logs_total'] = int(db.query(Beds24SyncLog.id).count())
        preview['notes'].append('Local/dev only destructive reset. Not for production use.')
        if app_settings.environment.strip().lower() == 'production':
            preview['notes'].append('Blocked in production environment.')

    return preview


def execute_reset_mode(db: Session, mode: str, *, confirmation: str, triggered_by: str | None = None) -> dict[str, Any]:
    preview = preview_reset_mode(db, mode)
    required = preview.get('required_confirmation')
    if _norm(confirmation) != _norm(required):
        raise ValueError(f'Invalid confirmation phrase. Expected: {required}')

    mode = preview['mode']
    if mode == RESET_MODE_LOCAL_TEST_FULL and app_settings.environment.strip().lower() == 'production':
        raise ValueError('local_test_full reset is blocked in production environment.')

    result: dict[str, Any] = {
        'mode': mode,
        'applied': {},
        'required_confirmation': required,
    }

    if mode in {RESET_MODE_BEDS24_FOLIOS, RESET_MODE_BEDS24_ALL}:
        result['applied'].update(_delete_beds24_mirror_folios(db))

    if mode in {RESET_MODE_BEDS24_BOOKINGS, RESET_MODE_BEDS24_ALL}:
        beds24_bookings = _beds24_booking_query(db).all()
        booking_ids = [int(row.id) for row in beds24_bookings]
        booking_maps_deleted = 0
        if booking_ids:
            booking_maps_deleted = (
                db.query(Beds24BookingMap)
                .filter(Beds24BookingMap.local_booking_id.in_(booking_ids))
                .delete(synchronize_session=False)
            )
        for row in beds24_bookings:
            db.delete(row)
        if beds24_bookings:
            db.flush()
        result['applied']['beds24_bookings_deleted'] = int(len(beds24_bookings))
        result['applied']['beds24_booking_maps_deleted'] = int(booking_maps_deleted)

    if mode in {RESET_MODE_BEDS24_GUESTS, RESET_MODE_BEDS24_ALL}:
        removable_guest_ids = [gid for gid in _beds24_mapped_guest_ids(db) if _guest_is_unlinked(db, gid)]
        removed_guest_merge_history = 0
        if removable_guest_ids:
            removed_guest_merge_history = (
                db.query(GuestMergeHistory)
                .filter(
                    or_(
                        GuestMergeHistory.source_guest_id.in_(removable_guest_ids),
                        GuestMergeHistory.target_guest_id.in_(removable_guest_ids),
                    )
                )
                .delete(synchronize_session=False)
            )
        deleted_guests = 0
        for guest_id in removable_guest_ids:
            row = db.get(Guest, int(guest_id))
            if not row:
                continue
            db.delete(row)
            deleted_guests += 1
        result['applied']['beds24_guest_merge_history_deleted'] = int(removed_guest_merge_history)
        result['applied']['beds24_unlinked_guests_deleted'] = int(deleted_guests)

    if mode == RESET_MODE_BEDS24_ALL:
        result['applied']['beds24_booking_maps_deleted_total'] = int(
            db.query(Beds24BookingMap).delete(synchronize_session=False)
        )
        result['applied']['beds24_guest_maps_deleted'] = int(
            db.query(Beds24GuestMap).delete(synchronize_session=False)
        )
        result['applied']['beds24_sync_logs_deleted'] = int(
            db.query(Beds24SyncLog).delete(synchronize_session=False)
        )

    if mode == RESET_MODE_LOCAL_TEST_FULL:
        all_bookings = db.query(Booking).all()
        for row in all_bookings:
            db.delete(row)
        if all_bookings:
            db.flush()

        removable_guests = []
        for row in db.query(Guest.id).all():
            guest_id = int(row[0])
            if _guest_is_unlinked(db, guest_id):
                removable_guests.append(guest_id)

        removed_guest_merge_history = 0
        if removable_guests:
            removed_guest_merge_history = (
                db.query(GuestMergeHistory)
                .filter(
                    or_(
                        GuestMergeHistory.source_guest_id.in_(removable_guests),
                        GuestMergeHistory.target_guest_id.in_(removable_guests),
                    )
                )
                .delete(synchronize_session=False)
            )
        deleted_guests = 0
        for guest_id in removable_guests:
            row = db.get(Guest, guest_id)
            if not row:
                continue
            db.delete(row)
            deleted_guests += 1

        result['applied']['all_bookings_deleted'] = int(len(all_bookings))
        result['applied']['all_guests_deleted'] = int(deleted_guests)
        result['applied']['all_guest_merge_history_deleted'] = int(removed_guest_merge_history)
        result['applied']['beds24_booking_maps_deleted'] = int(
            db.query(Beds24BookingMap).delete(synchronize_session=False)
        )
        result['applied']['beds24_guest_maps_deleted'] = int(
            db.query(Beds24GuestMap).delete(synchronize_session=False)
        )
        result['applied']['beds24_sync_logs_deleted'] = int(
            db.query(Beds24SyncLog).delete(synchronize_session=False)
        )

    db.commit()

    _upsert_sync_log(
        db,
        event_type='reset',
        source_type='manual',
        status='success',
        message=f'Beds24 reset executed ({mode}) by {triggered_by or "system"}.',
        payload={'mode': mode, 'applied': result['applied']},
    )
    return result


def extract_webhook_booking_ids(payload: Any) -> list[str]:
    found: set[str] = set()

    def walk(node: Any):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in {'id', 'bookingId', 'booking_id', 'bookId', 'book_id'} and value is not None and str(value).strip():
                    found.add(str(value).strip())
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return sorted(found)


def _validate_webhook_secret(settings: dict[str, Any], headers: dict[str, str], query_secret: str | None):
    if not settings.get('webhook_enabled'):
        raise ValueError('Beds24 webhook is disabled.')
    if settings.get('manual_sync_only'):
        raise ValueError('Webhook sync is disabled while manual_sync_only is enabled.')

    require_secret = bool(settings.get('webhook_require_secret'))
    configured_secret = _norm(settings.get('webhook_secret'))
    if not require_secret:
        return
    if not configured_secret:
        raise ValueError('Beds24 webhook secret is required but not configured.')

    provided = _norm(query_secret)
    if not provided:
        for key in WEBHOOK_SECRET_HEADER_KEYS:
            value = _norm(headers.get(key))
            if value:
                provided = value
                break

    if not provided or provided != configured_secret:
        raise ValueError('Invalid webhook secret.')


def sync_from_webhook(
    db: Session,
    payload: Any,
    *,
    headers: dict[str, str] | None = None,
    query_secret: str | None = None,
    triggered_by: str | None = None,
) -> dict[str, Any]:
    settings = load_beds24_settings(db)
    _validate_webhook_secret(settings, {k.lower(): v for k, v in (headers or {}).items()}, query_secret)

    booking_ids = extract_webhook_booking_ids(payload)
    if booking_ids:
        results: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for bid in booking_ids:
            try:
                row = sync_booking_by_id(
                    db,
                    bid,
                    source_type='webhook',
                    include_invoice_items=settings.get('include_invoice_items'),
                    triggered_by=triggered_by,
                )
                results.append(row)
            except Exception as exc:
                errors.append({'beds24_booking_id': bid, 'error': str(exc)})
        return {
            'ok': not errors,
            'source': 'webhook',
            'booking_ids': booking_ids,
            'synced': len(results),
            'failed': len(errors),
            'results': results,
            'errors': errors,
        }

    # Fallback path: fetch recent full bookings when webhook payload does not carry ids.
    return sync_recent_bookings(
        db,
        limit=25,
        include_invoice_items=settings.get('include_invoice_items'),
        source_type='webhook',
        triggered_by=triggered_by,
    )
