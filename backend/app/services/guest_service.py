from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    Beds24GuestMap,
    Booking,
    BookingChannel,
    BookingFolio,
    BookingFolioLine,
    Guest,
    GuestMergeHistory,
    GuestPreference,
    GuestTag,
)
from app.schemas.guests import (
    BookingFolioAction,
    BookingFolioCreate,
    BookingFolioLineCreate,
    BookingFolioLineUpdate,
    BookingFolioUpdate,
    GuestCreate,
    GuestMergePayload,
    GuestUpdate,
)


POSITIVE_FOLIO_TYPES = {
    'room_charge',
    'package_charge',
    'extra_person',
    'extra_bed',
    'breakfast_addon',
    'minibar',
    'cafe_room_charge',
    'manual_charge',
}
NEGATIVE_FOLIO_TYPES = {'deposit', 'payment', 'refund', 'reversal'}


def _today() -> str:
    return datetime.utcnow().strftime('%Y-%m-%d')


def _norm(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _normalize_name(first_name: str | None, last_name: str | None, full_name: str | None) -> str:
    if _norm(full_name):
        return _norm(full_name)  # type: ignore[return-value]
    pieces = [p for p in [
        _norm(first_name),
        _norm(last_name),
    ] if p]
    joined = ' '.join(pieces).strip()
    if joined:
        return joined
    return 'Unnamed Guest'


def _folio_stamp() -> str:
    return f'FOL-{datetime.utcnow().strftime("%Y%m%d-%H%M%S-%f")[:22]}'


def _channel_is_prepaid(channel: BookingChannel | None) -> bool:
    if not channel:
        return False
    if bool(getattr(channel, 'is_prepaid', False)):
        return True
    mode = (channel.settlement_mode or '').strip().lower()
    if mode in {'prepaid', 'ota_prepaid', 'prepaid_ota', 'ota_payout', 'net_payout'}:
        return True
    return False


def _serialize_guest(row: Guest, db: Session | None = None) -> dict:
    booking_count = 0
    stay_count = 0
    last_stay_date = None
    outstanding_balance = 0.0
    if db is not None:
        booking_count = int(db.query(func.count(Booking.id)).filter(Booking.guest_id == row.id).scalar() or 0)
        stay_count = int(
            db.query(func.count(Booking.id)).filter(Booking.guest_id == row.id, Booking.status.in_(['checked_in', 'checked_out'])).scalar() or 0
        )
        last_booking = (
            db.query(Booking)
            .filter(Booking.guest_id == row.id)
            .order_by(Booking.check_out.desc(), Booking.check_in.desc(), Booking.id.desc())
            .first()
        )
        last_stay_date = (last_booking.check_out or last_booking.check_in) if last_booking else None

        folios = db.query(BookingFolio).filter(BookingFolio.guest_id == row.id).all()
        for folio in folios:
            summary = folio_balance_summary(folio)
            outstanding_balance += float(summary.get('balance') or 0)

    return {
        'id': row.id,
        'first_name': row.first_name,
        'last_name': row.last_name,
        'full_name': row.full_name,
        'phone': row.phone,
        'email': row.email,
        'address': row.address,
        'city': row.city,
        'nationality': row.nationality,
        'birthday': row.birthday,
        'company': row.company,
        'vip_flag': bool(row.vip_flag),
        'status_tags': row.status_tags,
        'notes': row.notes,
        'is_active': bool(row.is_active),
        'tags': sorted([t.tag for t in row.tags or []]),
        'preferences': [
            {
                'id': pref.id,
                'preference_key': pref.preference_key,
                'preference_value': pref.preference_value,
            }
            for pref in (row.preferences or [])
        ],
        'booking_count': booking_count,
        'stay_count': stay_count,
        'last_stay_date': last_stay_date,
        'outstanding_balance': round(outstanding_balance, 4),
        'is_returning_guest': booking_count > 0,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_folio_line(row: BookingFolioLine) -> dict:
    return {
        'id': row.id,
        'folio_id': row.folio_id,
        'line_type': row.line_type,
        'description': row.description,
        'quantity': float(row.quantity or 0),
        'unit_price': float(row.unit_price or 0),
        'amount': float(row.amount or 0),
        'transaction_date': row.transaction_date,
        'reference_no': row.reference_no,
        'linked_money_transaction_id': row.linked_money_transaction_id,
        'linked_receivable_id': row.linked_receivable_id,
        'linked_payable_id': row.linked_payable_id,
        'linked_record_id': row.linked_record_id,
        'external_source': row.external_source,
        'external_line_key': row.external_line_key,
        'notes': row.notes,
        'created_by': row.created_by,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def folio_balance_summary(folio: BookingFolio) -> dict:
    charges = 0.0
    payments = 0.0
    deposits = 0.0
    refunds = 0.0
    reversals = 0.0

    for line in folio.lines or []:
        amount = float(line.amount or 0)
        line_type = (line.line_type or '').strip().lower()
        if line_type in POSITIVE_FOLIO_TYPES:
            charges += amount
        elif line_type == 'deposit':
            deposits += amount
            payments += amount
        elif line_type == 'payment':
            payments += amount
        elif line_type == 'refund':
            refunds += amount
            payments -= amount
        elif line_type == 'reversal':
            reversals += amount
            payments -= amount
        else:
            charges += amount

    balance = charges - payments
    return {
        'charges': round(charges, 4),
        'payments': round(payments, 4),
        'deposits': round(deposits, 4),
        'refunds': round(refunds, 4),
        'reversals': round(reversals, 4),
        'balance': round(balance, 4),
    }


def _serialize_folio(row: BookingFolio) -> dict:
    booking = row.booking
    guest = row.guest
    lines = sorted(row.lines or [], key=lambda x: (x.transaction_date or '', x.id))
    summary = folio_balance_summary(row)
    return {
        'id': row.id,
        'booking_id': row.booking_id,
        'booking_ref': f'BOOK-{row.booking_id}',
        'guest_id': row.guest_id,
        'guest_name': guest.full_name if guest else (booking.guest_name if booking else None),
        'guest_vip_flag': bool(guest.vip_flag) if guest else False,
        'folio_no': row.folio_no,
        'status': row.status,
        'opened_at': row.opened_at,
        'closed_at': row.closed_at,
        'notes': row.notes,
        **summary,
        'lines': [_serialize_folio_line(line) for line in lines],
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def _apply_guest_tags_and_preferences(db: Session, guest: Guest, tags: list[str] | None, preferences):
    if tags is not None:
        for old in list(guest.tags or []):
            db.delete(old)
        unique_tags = sorted({(_norm(tag) or '') for tag in tags if _norm(tag)})
        for tag in unique_tags:
            db.add(GuestTag(guest_id=guest.id, tag=tag))

    if preferences is not None:
        for old in list(guest.preferences or []):
            db.delete(old)
        for pref in preferences or []:
            key = _norm(pref.preference_key)
            if not key:
                continue
            db.add(GuestPreference(
                guest_id=guest.id,
                preference_key=key,
                preference_value=_norm(pref.preference_value),
            ))


def list_guests(db: Session, *, q: str | None = None, vip_only: bool = False, active_only: bool = True, limit: int = 300):
    query = db.query(Guest).options(selectinload(Guest.tags), selectinload(Guest.preferences))
    if active_only:
        query = query.filter(Guest.is_active == True)
    if vip_only:
        query = query.filter(Guest.vip_flag == True)
    if q:
        like_q = f'%{q.strip().lower()}%'
        query = query.filter(or_(
            func.lower(func.coalesce(Guest.full_name, '')).like(like_q),
            func.lower(func.coalesce(Guest.phone, '')).like(like_q),
            func.lower(func.coalesce(Guest.email, '')).like(like_q),
            func.lower(func.coalesce(Guest.company, '')).like(like_q),
        ))
    rows = query.order_by(Guest.vip_flag.desc(), func.lower(Guest.full_name).asc()).limit(max(1, min(int(limit or 300), 2000))).all()
    return [_serialize_guest(row, db) for row in rows]


def search_guests(db: Session, q: str, limit: int = 30):
    text = _norm(q)
    if not text:
        return []
    like_q = f'%{text.lower()}%'
    rows = (
        db.query(Guest)
        .options(selectinload(Guest.tags))
        .filter(Guest.is_active == True)
        .filter(or_(
            func.lower(func.coalesce(Guest.full_name, '')).like(like_q),
            func.lower(func.coalesce(Guest.phone, '')).like(like_q),
            func.lower(func.coalesce(Guest.email, '')).like(like_q),
        ))
        .order_by(Guest.vip_flag.desc(), func.lower(Guest.full_name).asc())
        .limit(max(1, min(int(limit or 30), 200)))
        .all()
    )
    return [_serialize_guest(row, db) for row in rows]


def get_guest(db: Session, guest_id: int):
    row = db.query(Guest).options(selectinload(Guest.tags), selectinload(Guest.preferences)).filter(Guest.id == int(guest_id)).first()
    if not row:
        raise ValueError('Guest not found.')
    return _serialize_guest(row, db)


def create_guest(db: Session, payload: GuestCreate):
    full_name = _normalize_name(payload.first_name, payload.last_name, payload.full_name)
    row = Guest(
        first_name=_norm(payload.first_name),
        last_name=_norm(payload.last_name),
        full_name=full_name,
        phone=_norm(payload.phone),
        email=_norm(payload.email),
        address=_norm(payload.address),
        city=_norm(payload.city),
        nationality=_norm(payload.nationality),
        birthday=_norm(payload.birthday),
        company=_norm(payload.company),
        vip_flag=bool(payload.vip_flag),
        status_tags=_norm(payload.status_tags),
        notes=payload.notes,
        is_active=bool(payload.is_active),
    )
    db.add(row)
    db.flush()
    _apply_guest_tags_and_preferences(db, row, payload.tags, payload.preferences)
    db.commit()
    row = db.query(Guest).options(selectinload(Guest.tags), selectinload(Guest.preferences)).filter(Guest.id == row.id).first()
    return _serialize_guest(row, db)


def update_guest(db: Session, guest_id: int, payload: GuestUpdate):
    row = db.query(Guest).options(selectinload(Guest.tags), selectinload(Guest.preferences)).filter(Guest.id == int(guest_id)).first()
    if not row:
        raise ValueError('Guest not found.')

    folio = db.get(BookingFolio, int(row.folio_id))
    if folio and (folio.status or 'open') in {'settled', 'closed', 'cancelled'}:
        raise ValueError('Closed or settled folio lines cannot be edited. Reopen or reverse instead.')
    if row.external_source or row.linked_money_transaction_id or row.linked_receivable_id or row.linked_payable_id:
        raise ValueError('Linked or external folio lines cannot be edited. Reverse the line instead.')
    data = payload.model_dump(exclude_unset=True)
    for key in ('first_name', 'last_name', 'phone', 'email', 'address', 'city', 'nationality', 'birthday', 'company', 'status_tags'):
        if key in data:
            setattr(row, key, _norm(data.get(key)))
    for key in ('vip_flag', 'notes', 'is_active'):
        if key in data:
            setattr(row, key, data.get(key))

    if 'full_name' in data or 'first_name' in data or 'last_name' in data:
        row.full_name = _normalize_name(row.first_name, row.last_name, data.get('full_name'))

    db.add(row)
    db.flush()
    if 'tags' in data:
        _apply_guest_tags_and_preferences(db, row, data.get('tags'), None)
    if 'preferences' in data:
        _apply_guest_tags_and_preferences(db, row, None, data.get('preferences'))

    db.commit()
    row = db.query(Guest).options(selectinload(Guest.tags), selectinload(Guest.preferences)).filter(Guest.id == row.id).first()
    return _serialize_guest(row, db)


def _merge_one_guest(db: Session, *, source_guest_id: int, target_guest_id: int, reason: str | None, username: str | None = None):
    if int(source_guest_id) == int(target_guest_id):
        raise ValueError('Cannot merge the same guest.')
    source = db.get(Guest, int(source_guest_id))
    target = db.get(Guest, int(target_guest_id))
    if not source or not target:
        raise ValueError('source_guest_id or target_guest_id not found.')

    db.query(Booking).filter(Booking.guest_id == source.id).update({'guest_id': target.id, 'guest_name': target.full_name})
    db.query(BookingFolio).filter(BookingFolio.guest_id == source.id).update({'guest_id': target.id})
    db.query(Beds24GuestMap).filter(Beds24GuestMap.local_guest_id == source.id).update({'local_guest_id': target.id})

    source.is_active = False
    source.notes = f'{source.notes or ""}\nMerged into guest #{target.id} ({target.full_name})'.strip()
    db.add(source)

    db.add(GuestMergeHistory(
        source_guest_id=source.id,
        target_guest_id=target.id,
        reason=reason,
        merged_by=username,
    ))
    return {
        'source_guest_id': source.id,
        'target_guest_id': target.id,
    }


def merge_guests(db: Session, payload: GuestMergePayload, username: str | None = None):
    target_guest_id = int(payload.target_guest_id)
    source_ids = [int(value) for value in (payload.source_guest_ids or [])]
    if payload.source_guest_id:
        source_ids.append(int(payload.source_guest_id))
    source_ids = sorted(set(source_ids))
    if not source_ids:
        raise ValueError('Select at least one source guest to merge.')
    if target_guest_id in source_ids:
        raise ValueError('Target guest cannot also be a source guest.')

    target = db.get(Guest, target_guest_id)
    if not target:
        raise ValueError('target_guest_id not found.')

    merged = [
        _merge_one_guest(
            db,
            source_guest_id=source_id,
            target_guest_id=target_guest_id,
            reason=payload.reason,
            username=username,
        )
        for source_id in source_ids
    ]
    db.commit()
    return {
        'ok': True,
        'source_guest_ids': [row['source_guest_id'] for row in merged],
        'target_guest_id': target_guest_id,
        'merged_count': len(merged),
    }

def guest_history(db: Session, guest_id: int):
    guest = db.get(Guest, int(guest_id))
    if not guest:
        raise ValueError('Guest not found.')

    bookings = (
        db.query(Booking)
        .filter(Booking.guest_id == guest.id)
        .order_by(Booking.check_in.desc(), Booking.id.desc())
        .all()
    )

    folios = (
        db.query(BookingFolio)
        .options(selectinload(BookingFolio.lines), selectinload(BookingFolio.booking), selectinload(BookingFolio.guest))
        .filter(BookingFolio.guest_id == guest.id)
        .order_by(BookingFolio.id.desc())
        .all()
    )

    payment_history = []
    folio_summaries = []
    for folio in folios:
        serialized = _serialize_folio(folio)
        folio_summaries.append({
            'id': serialized['id'],
            'folio_no': serialized['folio_no'],
            'booking_id': serialized['booking_id'],
            'status': serialized['status'],
            'charges': serialized['charges'],
            'payments': serialized['payments'],
            'balance': serialized['balance'],
        })
        for line in serialized['lines']:
            if line['line_type'] in {'deposit', 'payment', 'refund', 'reversal'}:
                payment_history.append({
                    'folio_id': serialized['id'],
                    'folio_no': serialized['folio_no'],
                    **line,
                })

    payment_history = sorted(payment_history, key=lambda x: (x.get('transaction_date') or '', x.get('id') or 0), reverse=True)
    outstanding_balance = round(sum(float(x.get('balance') or 0) for x in folio_summaries), 4)

    return {
        'guest': _serialize_guest(guest, db),
        'bookings': [
            {
                'id': row.id,
                'status': row.status,
                'room_name': row.room_name,
                'room_type': row.room_type,
                'channel': row.channel,
                'check_in': row.check_in,
                'check_out': row.check_out,
                'gross_amount': float(row.gross_amount or 0),
                'deposit_amount': float(row.deposit_amount or 0),
            }
            for row in bookings
        ],
        'stay_history': [
            {
                'booking_id': row.id,
                'check_in': row.check_in,
                'check_out': row.check_out,
                'status': row.status,
                'room_name': row.room_name,
                'room_type': row.room_type,
            }
            for row in bookings
            if row.status in {'checked_in', 'checked_out'}
        ],
        'payment_history': payment_history,
        'folio_history': folio_summaries,
        'outstanding_balance': outstanding_balance,
    }


def ensure_booking_folio(
    db: Session,
    booking: Booking,
    username: str | None = None,
    *,
    create_default_lines: bool = True,
):
    folio = db.query(BookingFolio).filter(BookingFolio.booking_id == booking.id).order_by(BookingFolio.id.desc()).first()
    if folio:
        return folio
    channel_obj = db.get(BookingChannel, int(booking.channel_id)) if booking.channel_id else None
    channel_prepaid = _channel_is_prepaid(channel_obj)

    folio = BookingFolio(
        booking_id=booking.id,
        guest_id=booking.guest_id,
        folio_no=_folio_stamp(),
        status='open',
        opened_at=booking.check_in or _today(),
        notes=f'Auto-created for booking #{booking.id}',
    )
    db.add(folio)
    db.flush()
    if create_default_lines and float(booking.gross_amount or 0) > 0:
        db.add(
            BookingFolioLine(
                folio_id=folio.id,
                line_type='room_charge',
                description=f'Room charge for booking #{booking.id}',
                quantity=1,
                unit_price=float(booking.gross_amount or 0),
                amount=float(booking.gross_amount or 0),
                transaction_date=booking.check_in or _today(),
                reference_no=f'BOOK-{booking.id}',
                notes='Auto-created from booking amount',
                created_by=username,
            )
        )
    if create_default_lines and float(booking.deposit_amount or 0) > 0:
        db.add(
            BookingFolioLine(
                folio_id=folio.id,
                line_type='deposit',
                description='Booking deposit',
                quantity=1,
                unit_price=float(booking.deposit_amount or 0),
                amount=float(booking.deposit_amount or 0),
                transaction_date=booking.check_in or _today(),
                reference_no=f'BOOK-{booking.id}',
                notes='Auto-created from booking deposit',
                created_by=username,
            )
        )
    elif create_default_lines and channel_prepaid and float(booking.gross_amount or 0) > 0:
        db.add(
            BookingFolioLine(
                folio_id=folio.id,
                line_type='deposit',
                description='Prepaid OTA settlement',
                quantity=1,
                unit_price=float(booking.gross_amount or 0),
                amount=float(booking.gross_amount or 0),
                transaction_date=booking.check_in or _today(),
                reference_no=f'BOOK-{booking.id}:PREPAID',
                notes='Auto-created from prepaid booking channel',
                created_by=username,
            )
        )
    db.flush()
    return folio


def list_folios(db: Session, *, booking_id: int | None = None, guest_id: int | None = None, status: str | None = None):
    query = db.query(BookingFolio).options(
        selectinload(BookingFolio.booking),
        selectinload(BookingFolio.guest),
        selectinload(BookingFolio.lines),
    )
    if booking_id:
        query = query.filter(BookingFolio.booking_id == int(booking_id))
    if guest_id:
        query = query.filter(BookingFolio.guest_id == int(guest_id))
    if status:
        query = query.filter(BookingFolio.status == status)
    rows = query.order_by(BookingFolio.id.desc()).all()
    return [_serialize_folio(row) for row in rows]


def get_folio(db: Session, folio_id: int):
    row = (
        db.query(BookingFolio)
        .options(
            selectinload(BookingFolio.booking),
            selectinload(BookingFolio.guest),
            selectinload(BookingFolio.lines),
        )
        .filter(BookingFolio.id == int(folio_id))
        .first()
    )
    if not row:
        raise ValueError('Folio not found.')
    return _serialize_folio(row)


def create_folio(db: Session, payload: BookingFolioCreate):
    booking = db.get(Booking, int(payload.booking_id))
    if not booking:
        raise ValueError('booking_id not found.')
    if payload.guest_id and not db.get(Guest, int(payload.guest_id)):
        raise ValueError('guest_id not found.')

    row = BookingFolio(
        booking_id=booking.id,
        guest_id=payload.guest_id or booking.guest_id,
        folio_no=_norm(payload.folio_no) or _folio_stamp(),
        status='open',
        opened_at=booking.check_in or _today(),
        notes=payload.notes,
    )
    db.add(row)
    db.commit()
    return get_folio(db, row.id)


def update_folio(db: Session, folio_id: int, payload: BookingFolioUpdate):
    row = db.get(BookingFolio, int(folio_id))
    if not row:
        raise ValueError('Folio not found.')
    data = payload.model_dump(exclude_unset=True)
    if 'guest_id' in data:
        guest_id = data.get('guest_id')
        if guest_id and not db.get(Guest, int(guest_id)):
            raise ValueError('guest_id not found.')
        row.guest_id = guest_id
    if 'status' in data:
        row.status = _norm(data.get('status')) or row.status
        if row.status == 'closed' and not row.closed_at:
            row.closed_at = _today()
    if 'notes' in data:
        row.notes = data.get('notes')
    db.add(row)
    db.commit()
    return get_folio(db, row.id)


def set_folio_status(db: Session, folio_id: int, payload: BookingFolioAction):
    row = db.get(BookingFolio, int(folio_id))
    if not row:
        raise ValueError('Folio not found.')
    status = _norm(payload.status)
    if status not in {'open', 'reviewed', 'pending_settlement', 'settled', 'closed', 'cancelled', 'reopened'}:
        raise ValueError('Invalid folio status.')
    row.status = status
    if status in {'settled', 'closed'}:
        row.closed_at = _today()
    elif status in {'open', 'reopened'}:
        row.closed_at = None
    if payload.notes:
        row.notes = f'{row.notes or ""}\n{payload.notes}'.strip()
    db.add(row)
    db.commit()
    return get_folio(db, row.id)


def add_folio_line(db: Session, folio_id: int, payload: BookingFolioLineCreate, username: str | None = None):
    folio = db.get(BookingFolio, int(folio_id))
    if not folio:
        raise ValueError('Folio not found.')
    if (folio.status or 'open') in {'settled', 'closed', 'cancelled'}:
        raise ValueError('Closed or settled folios cannot accept new lines. Reopen the folio first.')

    qty = float(payload.quantity or 0)
    if qty <= 0:
        raise ValueError('quantity must be greater than zero.')
    unit_price = float(payload.unit_price or 0)
    amount = float(payload.amount) if payload.amount is not None else round(qty * unit_price, 4)

    row = BookingFolioLine(
        folio_id=folio.id,
        line_type=_norm(payload.line_type) or 'manual_charge',
        description=_norm(payload.description) or 'Folio line',
        quantity=qty,
        unit_price=unit_price,
        amount=amount,
        transaction_date=_norm(payload.transaction_date) or _today(),
        reference_no=_norm(payload.reference_no),
        linked_money_transaction_id=payload.linked_money_transaction_id,
        linked_receivable_id=payload.linked_receivable_id,
        linked_payable_id=payload.linked_payable_id,
        linked_record_id=payload.linked_record_id,
        notes=payload.notes,
        created_by=username,
    )
    db.add(row)
    db.commit()
    return get_folio(db, folio.id)


def update_folio_line(db: Session, folio_line_id: int, payload: BookingFolioLineUpdate):
    row = db.get(BookingFolioLine, int(folio_line_id))
    if not row:
        raise ValueError('Folio line not found.')
    data = payload.model_dump(exclude_unset=True)

    for key in (
        'line_type',
        'description',
        'quantity',
        'unit_price',
        'amount',
        'transaction_date',
        'reference_no',
        'linked_money_transaction_id',
        'linked_receivable_id',
        'linked_payable_id',
        'linked_record_id',
        'notes',
    ):
        if key in data:
            value = data.get(key)
            if key in {'line_type', 'description', 'transaction_date', 'reference_no'}:
                value = _norm(value)
            setattr(row, key, value)

    if ('quantity' in data or 'unit_price' in data) and 'amount' not in data:
        row.amount = round(float(row.quantity or 0) * float(row.unit_price or 0), 4)

    db.add(row)
    db.commit()
    return get_folio(db, row.folio_id)


def delete_folio_line(db: Session, folio_line_id: int):
    row = db.get(BookingFolioLine, int(folio_line_id))
    if not row:
        raise ValueError('Folio line not found.')
    folio_id = row.folio_id
    folio = db.get(BookingFolio, int(folio_id))
    if folio and (folio.status or 'open') in {'settled', 'closed', 'cancelled'}:
        raise ValueError('Closed or settled folio lines cannot be deleted.')
    if row.external_source or row.linked_money_transaction_id or row.linked_receivable_id or row.linked_payable_id:
        raise ValueError('Linked or external folio lines cannot be deleted. Reverse the line instead.')
    db.delete(row)
    db.commit()
    return get_folio(db, folio_id)


def reverse_folio_line(db: Session, folio_line_id: int, payload, username: str | None = None):
    original = db.get(BookingFolioLine, int(folio_line_id))
    if not original:
        raise ValueError('Folio line not found.')
    folio = db.get(BookingFolio, int(original.folio_id))
    if not folio:
        raise ValueError('Folio not found.')
    reversal_key = f'reversal:{original.id}'
    duplicate = db.query(BookingFolioLine).filter(
        BookingFolioLine.folio_id == folio.id,
        BookingFolioLine.external_line_key == reversal_key,
    ).first()
    if duplicate:
        raise ValueError('This folio line has already been reversed.')
    amount = abs(float(original.amount or 0))
    line_type = (original.line_type or '').strip().lower()
    # Charges reverse as a negative charge; payments/deposits reverse as a positive reversal effect.
    reversal_amount = -amount if line_type in POSITIVE_FOLIO_TYPES or line_type not in {'deposit','payment','refund','reversal'} else amount
    row = BookingFolioLine(
        folio_id=folio.id,
        line_type='reversal',
        description=f'Reversal of line #{original.id}: {original.description}',
        quantity=1,
        unit_price=reversal_amount,
        amount=reversal_amount,
        transaction_date=_norm(payload.transaction_date) or _today(),
        reference_no=original.reference_no,
        linked_money_transaction_id=original.linked_money_transaction_id,
        linked_receivable_id=original.linked_receivable_id,
        linked_payable_id=original.linked_payable_id,
        linked_record_id=original.linked_record_id,
        external_source='accounting',
        external_line_key=reversal_key,
        notes=_norm(payload.reason) or 'Folio line reversal',
        created_by=username,
    )
    db.add(row)
    db.commit()
    return get_folio(db, folio.id)


def transfer_folio_line(db: Session, folio_line_id: int, payload, username: str | None = None):
    original = db.get(BookingFolioLine, int(folio_line_id))
    target = db.get(BookingFolio, int(payload.target_folio_id))
    if not original or not target:
        raise ValueError('Folio line or target folio not found.')
    if original.folio_id == target.id:
        raise ValueError('Target folio must be different.')
    if (target.status or 'open') in {'settled','closed','cancelled'}:
        raise ValueError('Target folio is not open.')
    transfer_key = f'transfer:{original.id}:{target.id}'
    if db.query(BookingFolioLine).filter(BookingFolioLine.external_line_key == transfer_key).first():
        raise ValueError('This line has already been transferred to the selected folio.')
    amount = float(original.amount or 0)
    moved = BookingFolioLine(
        folio_id=target.id, line_type=original.line_type, description=original.description,
        quantity=float(original.quantity or 1), unit_price=float(original.unit_price or 0), amount=amount,
        transaction_date=_norm(payload.transaction_date) or _today(), reference_no=original.reference_no,
        linked_money_transaction_id=original.linked_money_transaction_id, linked_receivable_id=original.linked_receivable_id,
        linked_payable_id=original.linked_payable_id, linked_record_id=original.linked_record_id,
        external_source=original.external_source or 'accounting', external_line_key=transfer_key,
        notes=f'Transferred from folio #{original.folio_id}. {_norm(payload.reason) or ""}'.strip(), created_by=username,
    )
    db.add(moved)
    reverse_payload = type('ReversePayload', (), {'transaction_date': payload.transaction_date, 'reason': f'Transferred to folio #{target.id}. {_norm(payload.reason) or ""}'})()
    db.flush()
    reverse_folio_line(db, original.id, reverse_payload, username=username)
    return {'source_folio': get_folio(db, original.folio_id), 'target_folio': get_folio(db, target.id)}


def settle_folio(db: Session, folio_id: int, payload):
    folio = db.get(BookingFolio, int(folio_id))
    if not folio:
        raise ValueError('Folio not found.')
    summary = folio_balance_summary(folio)
    tolerance = abs(float(payload.tolerance or 0))
    if abs(float(summary['balance'])) > tolerance:
        raise ValueError(f'Folio balance must be within {tolerance:.2f} before settlement.')
    folio.status = 'settled'
    folio.closed_at = _today()
    if payload.notes:
        folio.notes = f'{folio.notes or ""}\n{payload.notes}'.strip()
    db.add(folio)
    db.commit()
    return get_folio(db, folio.id)
