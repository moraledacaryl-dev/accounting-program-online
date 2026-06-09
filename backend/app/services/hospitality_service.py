from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    BookingChannel,
    Booking,
    BookingAccountingLink,
    BookingFolio,
    Guest,
    InventoryItem,
    MenuItem,
    MenuSKU,
    RatePlan,
    Room,
    RoomType,
    RoomBreakfastLog,
    StaffMealIngredient,
    StaffMealLog,
)
from app.services.guest_service import ensure_booking_folio
from app.services.restaurant_service import (
    consume_inventory_requirements,
    create_approved_record,
    expand_menu_or_sku_to_inventory_requirements,
    merge_inventory_requirements,
)


def _today() -> str:
    return datetime.utcnow().strftime('%Y-%m-%d')


def _normalize(value: str | None) -> str:
    return (value or '').strip().lower()


def _parse_iso_date(value: str | None, label: str) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, '%Y-%m-%d')
    except ValueError as exc:
        raise ValueError(f'{label} must be in YYYY-MM-DD format.') from exc


def _validate_booking_dates(check_in: str | None, check_out: str | None):
    in_date = _parse_iso_date(check_in, 'check_in')
    out_date = _parse_iso_date(check_out, 'check_out')
    if in_date and out_date and out_date < in_date:
        raise ValueError('check_out cannot be earlier than check_in.')


def _serial_record_link(link: BookingAccountingLink) -> dict:
    rec = link.record
    return {
        'id': link.id,
        'link_type': link.link_type,
        'record_id': link.record_id,
        'record_name': rec.name if rec else None,
        'record_module': rec.module_slug if rec else None,
        'record_direction': rec.direction if rec else None,
        'record_amount': rec.amount if rec else None,
        'record_date': rec.transaction_date if rec else None,
    }


def _serialize_booking(booking: Booking) -> dict:
    guest = booking.guest
    room = booking.room
    room_type_obj = booking.room_type_obj
    rate_plan = booking.rate_plan
    channel_obj = booking.channel_obj
    return {
        'id': booking.id,
        'guest_id': booking.guest_id,
        'guest_name': booking.guest_name,
        'guest_full_name': guest.full_name if guest else booking.guest_name,
        'guest_phone': guest.phone if guest else None,
        'guest_email': guest.email if guest else None,
        'guest_vip_flag': bool(guest.vip_flag) if guest else False,
        'room_id': booking.room_id,
        'room_type_id': booking.room_type_id,
        'rate_plan_id': booking.rate_plan_id,
        'channel_id': booking.channel_id,
        'room_display_name': room.name if room else None,
        'room_no': room.room_no if room else None,
        'room_type_display_name': room_type_obj.name if room_type_obj else None,
        'rate_plan_name': rate_plan.name if rate_plan else None,
        'channel_display_name': channel_obj.name if channel_obj else None,
        'channel_is_prepaid': bool(channel_obj.is_prepaid) if channel_obj else False,
        'room_name': booking.room_name,
        'room_type': booking.room_type,
        'channel': booking.channel,
        'external_source': booking.external_source,
        'external_booking_id': booking.external_booking_id,
        'status': booking.status,
        'check_in': booking.check_in,
        'check_out': booking.check_out,
        'gross_amount': booking.gross_amount,
        'deposit_amount': booking.deposit_amount,
        'breakfast_included': booking.breakfast_included,
        'notes': booking.notes,
        'created_at': booking.created_at,
        'updated_at': booking.updated_at,
        'accounting_links': [_serial_record_link(x) for x in (booking.accounting_links or [])],
        'primary_folio_id': (sorted(booking.folios or [], key=lambda x: x.id, reverse=True)[0].id if booking.folios else None),
    }


def _resolve_guest(db: Session, guest_id: int | None) -> Guest | None:
    if not guest_id:
        return None
    guest = db.get(Guest, int(guest_id))
    if not guest:
        raise ValueError(f'guest_id {guest_id} not found.')
    return guest


def _resolve_room(db: Session, room_id: int | None) -> Room | None:
    if not room_id:
        return None
    room = db.get(Room, int(room_id))
    if not room:
        raise ValueError(f'room_id {room_id} not found.')
    return room


def _resolve_room_type(db: Session, room_type_id: int | None) -> RoomType | None:
    if not room_type_id:
        return None
    room_type = db.get(RoomType, int(room_type_id))
    if not room_type:
        raise ValueError(f'room_type_id {room_type_id} not found.')
    return room_type


def _resolve_rate_plan(db: Session, rate_plan_id: int | None) -> RatePlan | None:
    if not rate_plan_id:
        return None
    rate_plan = db.get(RatePlan, int(rate_plan_id))
    if not rate_plan:
        raise ValueError(f'rate_plan_id {rate_plan_id} not found.')
    return rate_plan


def _resolve_channel(db: Session, channel_id: int | None) -> BookingChannel | None:
    if not channel_id:
        return None
    channel = db.get(BookingChannel, int(channel_id))
    if not channel:
        raise ValueError(f'channel_id {channel_id} not found.')
    return channel


def _serialize_breakfast(log: RoomBreakfastLog) -> dict:
    return {
        'id': log.id,
        'breakfast_no': log.breakfast_no,
        'booking_id': log.booking_id,
        'meal_date': log.meal_date,
        'guest_name': log.guest_name,
        'menu_item_id': log.menu_item_id,
        'menu_item_name': log.menu_item.name if log.menu_item else None,
        'sku_id': log.sku_id,
        'sku_name': (log.sku.variant_name if log.sku else None),
        'quantity': log.quantity,
        'charged_amount': log.charged_amount,
        'charge_to_room': log.charge_to_room,
        'cogs_amount': log.cogs_amount,
        'income_record_id': log.income_record_id,
        'cogs_record_id': log.cogs_record_id,
        'notes': log.notes,
        'created_by': log.created_by,
        'created_at': log.created_at,
    }


def _serialize_staff_meal(log: StaffMealLog) -> dict:
    return {
        'id': log.id,
        'meal_no': log.meal_no,
        'meal_date': log.meal_date,
        'dish_name': log.dish_name,
        'menu_item_id': log.menu_item_id,
        'menu_item_name': log.menu_item.name if log.menu_item else None,
        'sku_id': log.sku_id,
        'sku_name': (log.sku.variant_name if log.sku else None),
        'quantity': log.quantity,
        'served_to': log.served_to,
        'cogs_amount': log.cogs_amount,
        'expense_record_id': log.expense_record_id,
        'notes': log.notes,
        'created_by': log.created_by,
        'created_at': log.created_at,
        'lines': [
            {
                'id': line.id,
                'inventory_item_id': line.inventory_item_id,
                'inventory_item_name': line.inventory_item.name if line.inventory_item else None,
                'quantity': line.quantity,
                'unit': line.unit,
                'source': line.source,
                'notes': line.notes,
            }
            for line in (log.lines or [])
        ],
    }


def _room_income_paths(channel: str | None) -> list[tuple[str, str, str]]:
    normalized_channel = _normalize(channel)
    if normalized_channel in {'agoda', 'booking.com', 'airbnb', 'expedia'}:
        return [
            ('Revenue', 'OTA Bookings', channel or 'Agoda'),
            ('Revenue', 'OTA Bookings', 'Agoda'),
        ]
    if normalized_channel in {'corporate', 'group', 'group reservations'}:
        return [
            ('Revenue', 'Corporate / Group', 'Corporate Accounts'),
            ('Revenue', 'Corporate / Group', 'Group Reservations'),
        ]
    return [
        ('Revenue', 'Direct Bookings', channel or 'Walk-in'),
        ('Revenue', 'Direct Bookings', 'Walk-in'),
    ]


def _is_ota_channel(channel: str | None) -> bool:
    return _normalize(channel) in {'agoda', 'booking.com', 'airbnb', 'expedia'}


def _booking_payment_method(channel: str | None, payment_method: str | None) -> str:
    value = (payment_method or '').strip()
    if value:
        return value
    return 'ota_payout' if _is_ota_channel(channel) else 'cash'


def generate_room_breakfast_no(db: Session) -> str:
    base = datetime.utcnow().strftime('RB-%Y%m%d-%H%M%S')
    suffix = int(db.query(func.count(RoomBreakfastLog.id)).scalar() or 0) + 1
    return f'{base}-{suffix}'


def generate_staff_meal_no(db: Session) -> str:
    base = datetime.utcnow().strftime('SM-%Y%m%d-%H%M%S')
    suffix = int(db.query(func.count(StaffMealLog.id)).scalar() or 0) + 1
    return f'{base}-{suffix}'


def list_bookings(db: Session, limit: int = 400):
    rows = (
        db.query(Booking)
        .options(
            selectinload(Booking.accounting_links).selectinload(BookingAccountingLink.record),
            selectinload(Booking.guest),
            selectinload(Booking.room),
            selectinload(Booking.room_type_obj),
            selectinload(Booking.rate_plan),
            selectinload(Booking.channel_obj),
            selectinload(Booking.folios),
        )
        .order_by(Booking.id.desc())
        .limit(limit)
        .all()
    )
    return [_serialize_booking(x) for x in rows]


def get_booking(db: Session, booking_id: int) -> dict:
    row = (
        db.query(Booking)
        .options(
            selectinload(Booking.accounting_links).selectinload(BookingAccountingLink.record),
            selectinload(Booking.guest),
            selectinload(Booking.room),
            selectinload(Booking.room_type_obj),
            selectinload(Booking.rate_plan),
            selectinload(Booking.channel_obj),
            selectinload(Booking.folios),
        )
        .filter(Booking.id == int(booking_id))
        .first()
    )
    if not row:
        raise ValueError('Booking not found.')
    return _serialize_booking(row)


def list_booking_calendar(
    db: Session,
    *,
    start_date: str,
    end_date: str,
    room_id: int | None = None,
    status: str | None = None,
    channel_id: int | None = None,
):
    _parse_iso_date(start_date, 'start_date')
    _parse_iso_date(end_date, 'end_date')
    query = (
        db.query(Booking)
        .options(
            selectinload(Booking.guest),
            selectinload(Booking.room),
            selectinload(Booking.room_type_obj),
            selectinload(Booking.channel_obj),
            selectinload(Booking.folios),
        )
        .filter(Booking.check_in <= end_date)
        .filter(or_(
            Booking.check_out.is_(None),
            Booking.check_out == '',
            Booking.check_out > start_date,
            and_(
                Booking.check_in == Booking.check_out,
                Booking.check_in >= start_date,
                Booking.check_in <= end_date,
            ),
        ))
    )
    if room_id:
        query = query.filter(Booking.room_id == int(room_id))
    if status:
        query = query.filter(Booking.status == status)
    if channel_id:
        query = query.filter(Booking.channel_id == int(channel_id))
    rows = query.order_by(Booking.check_in.asc(), Booking.room_name.asc(), Booking.id.asc()).limit(2500).all()
    return [_serialize_booking(row) for row in rows]


def create_booking_with_accounting(db: Session, payload, username: str | None = None) -> dict:
    _validate_booking_dates(payload.check_in, payload.check_out)
    guest = _resolve_guest(db, payload.guest_id) if payload.guest_id else None
    room = _resolve_room(db, payload.room_id)
    room_type = _resolve_room_type(db, payload.room_type_id) if payload.room_type_id else None
    rate_plan = _resolve_rate_plan(db, payload.rate_plan_id) if payload.rate_plan_id else None
    channel_obj = _resolve_channel(db, payload.channel_id) if payload.channel_id else None

    if room and not room_type and room.room_type_id:
        room_type = room.room_type
    if rate_plan and not room_type and rate_plan.room_type_id:
        room_type = rate_plan.room_type

    room_name = (payload.room_name or '').strip() or ((room.name or room.room_no) if room else '')
    room_type_name = (payload.room_type or '').strip() or (room_type.name if room_type else None)
    channel_name = (payload.channel or '').strip() or (channel_obj.name if channel_obj else 'Walk-in')
    breakfast_included = int(payload.breakfast_included if payload.breakfast_included is not None else (rate_plan.breakfast_included if rate_plan else 0))

    guest_name = (payload.guest_name or '').strip() or (guest.full_name if guest else '')
    if not guest_name:
        raise ValueError('guest_name is required.')

    booking = Booking(
        guest_id=guest.id if guest else None,
        guest_name=guest_name,
        room_id=room.id if room else None,
        room_type_id=room_type.id if room_type else None,
        rate_plan_id=rate_plan.id if rate_plan else None,
        channel_id=channel_obj.id if channel_obj else None,
        room_name=room_name,
        room_type=room_type_name,
        channel=channel_name,
        status=payload.status,
        check_in=payload.check_in,
        check_out=payload.check_out,
        gross_amount=float(payload.gross_amount or 0),
        deposit_amount=float(payload.deposit_amount or 0),
        breakfast_included=max(0, breakfast_included),
        notes=payload.notes,
    )
    db.add(booking)
    db.flush()
    ensure_booking_folio(db, booking, username=username)

    booking_ref = f'BOOK-{booking.id}'
    transaction_date = payload.check_in or payload.check_out or _today()
    payment_method = _booking_payment_method(payload.channel, payload.payment_method)

    if payload.auto_post_accounting:
        gross_amount = float(payload.gross_amount or 0)
        if gross_amount != 0:
            room_income = create_approved_record(
                db,
                module_slug='rooms',
                direction='income',
                amount=gross_amount,
                name=f'Room booking {booking.guest_name}',
                transaction_date=transaction_date,
                payment_method=payment_method,
                counterparty=booking.guest_name,
                notes='Auto-generated from booking entry',
                document_ref=booking_ref,
                created_by=username,
                preferred_paths=_room_income_paths(payload.channel),
            )
            db.add(BookingAccountingLink(booking_id=booking.id, record_id=room_income.id, link_type='room_income'))

        deposit_amount = float(payload.deposit_amount or 0)
        if deposit_amount > 0:
            deposit_record = create_approved_record(
                db,
                module_slug='rooms',
                direction='liability',
                amount=deposit_amount,
                name=f'Booking deposit {booking.guest_name}',
                transaction_date=transaction_date,
                payment_method=payment_method,
                counterparty=booking.guest_name,
                notes='Auto-generated booking deposit liability',
                document_ref=booking_ref,
                created_by=username,
                preferred_paths=[
                    ('Deposits', 'Advance Payments', 'Reservation Deposit'),
                    ('Deposits', 'Advance Payments', 'Event Deposit'),
                ],
            )
            db.add(BookingAccountingLink(booking_id=booking.id, record_id=deposit_record.id, link_type='deposit_liability'))

    db.commit()

    booking = (
        db.query(Booking)
        .options(
            selectinload(Booking.accounting_links).selectinload(BookingAccountingLink.record),
            selectinload(Booking.guest),
            selectinload(Booking.room),
            selectinload(Booking.room_type_obj),
            selectinload(Booking.rate_plan),
            selectinload(Booking.channel_obj),
            selectinload(Booking.folios),
        )
        .filter(Booking.id == booking.id)
        .first()
    )
    return _serialize_booking(booking)


def update_booking_with_accounting(db: Session, booking_id: int, payload, username: str | None = None) -> dict:
    booking = (
        db.query(Booking)
        .options(
            selectinload(Booking.accounting_links).selectinload(BookingAccountingLink.record),
            selectinload(Booking.guest),
            selectinload(Booking.room),
            selectinload(Booking.room_type_obj),
            selectinload(Booking.rate_plan),
            selectinload(Booking.channel_obj),
            selectinload(Booking.folios),
        )
        .filter(Booking.id == booking_id)
        .first()
    )
    if not booking:
        raise ValueError(f'Booking {booking_id} not found.')

    old_gross = float(booking.gross_amount or 0)
    old_deposit = float(booking.deposit_amount or 0)
    old_status = _normalize(booking.status)

    data = payload.model_dump(exclude_unset=True)
    id_fields_changed = False
    if 'guest_id' in data:
        guest = _resolve_guest(db, data.get('guest_id')) if data.get('guest_id') else None
        booking.guest_id = guest.id if guest else None
        if guest:
            booking.guest_name = guest.full_name
    if 'room_id' in data:
        room = _resolve_room(db, data.get('room_id')) if data.get('room_id') else None
        booking.room_id = room.id if room else None
        id_fields_changed = True
    if 'room_type_id' in data:
        room_type = _resolve_room_type(db, data.get('room_type_id')) if data.get('room_type_id') else None
        booking.room_type_id = room_type.id if room_type else None
        id_fields_changed = True
    if 'rate_plan_id' in data:
        rate_plan = _resolve_rate_plan(db, data.get('rate_plan_id')) if data.get('rate_plan_id') else None
        booking.rate_plan_id = rate_plan.id if rate_plan else None
        id_fields_changed = True
    if 'channel_id' in data:
        channel_obj = _resolve_channel(db, data.get('channel_id')) if data.get('channel_id') else None
        booking.channel_id = channel_obj.id if channel_obj else None
        id_fields_changed = True

    for key in (
        'guest_name',
        'status',
        'check_in',
        'check_out',
        'gross_amount',
        'deposit_amount',
        'breakfast_included',
        'notes',
    ):
        if key in data:
            setattr(booking, key, data[key])

    room = db.get(Room, int(booking.room_id)) if booking.room_id else None
    room_type = db.get(RoomType, int(booking.room_type_id)) if booking.room_type_id else None
    rate_plan = db.get(RatePlan, int(booking.rate_plan_id)) if booking.rate_plan_id else None
    channel_obj = db.get(BookingChannel, int(booking.channel_id)) if booking.channel_id else None
    if room and not room_type and room.room_type_id:
        room_type = room.room_type
        booking.room_type_id = room_type.id if room_type else booking.room_type_id
    if rate_plan and not room_type and rate_plan.room_type_id:
        room_type = rate_plan.room_type
        booking.room_type_id = room_type.id if room_type else booking.room_type_id

    if 'room_name' in data:
        booking.room_name = (data.get('room_name') or '').strip()
    elif id_fields_changed and room and not booking.room_name:
        booking.room_name = room.name or room.room_no

    if 'room_type' in data:
        booking.room_type = (data.get('room_type') or '').strip() or None
    elif id_fields_changed and room_type and not booking.room_type:
        booking.room_type = room_type.name

    if 'channel' in data:
        booking.channel = (data.get('channel') or '').strip() or 'Walk-in'
    elif id_fields_changed and channel_obj and not booking.channel:
        booking.channel = channel_obj.name

    if 'breakfast_included' not in data and 'rate_plan_id' in data and rate_plan:
        booking.breakfast_included = max(0, int(rate_plan.breakfast_included or 0))

    if 'check_in' in data or 'check_out' in data:
        _validate_booking_dates(booking.check_in, booking.check_out)

    folio = db.query(BookingFolio).filter(BookingFolio.booking_id == booking.id).order_by(BookingFolio.id.desc()).first()
    if folio and booking.guest_id and folio.guest_id != booking.guest_id:
        folio.guest_id = booking.guest_id
        db.add(folio)
    if not folio:
        ensure_booking_folio(db, booking, username=username)

    new_gross = float(booking.gross_amount or 0)
    new_deposit = float(booking.deposit_amount or 0)
    new_status = _normalize(booking.status)
    booking_ref = f'BOOK-{booking.id}'
    transaction_date = payload.effective_date or booking.check_out or booking.check_in or _today()
    payment_method = _booking_payment_method(booking.channel, payload.payment_method)

    cancelling = old_status != 'cancelled' and new_status == 'cancelled' and payload.auto_reverse_on_cancel
    checking_out = old_status != 'checked_out' and new_status == 'checked_out'

    if payload.auto_post_accounting:
        gross_delta = round(new_gross - old_gross, 4)
        if gross_delta != 0:
            gross_note = 'Auto-generated booking adjustment (increase)' if gross_delta > 0 else 'Auto-generated booking adjustment (decrease/reversal)'
            gross_record = create_approved_record(
                db,
                module_slug='rooms',
                direction='income',
                amount=gross_delta,
                name=f'Booking adjustment {booking.guest_name}',
                transaction_date=transaction_date,
                payment_method=payment_method,
                counterparty=booking.guest_name,
                notes=gross_note,
                document_ref=booking_ref,
                created_by=username,
                preferred_paths=_room_income_paths(booking.channel),
            )
            db.add(BookingAccountingLink(booking_id=booking.id, record_id=gross_record.id, link_type='room_income_adjustment'))

        if cancelling:
            if old_deposit != 0:
                cancel_dep = create_approved_record(
                    db,
                    module_slug='rooms',
                    direction='liability',
                    amount=-old_deposit,
                    name=f'Cancelled booking deposit {booking.guest_name}',
                    transaction_date=transaction_date,
                    payment_method=payment_method,
                    counterparty=booking.guest_name,
                    notes='Auto-generated cancellation deposit reversal',
                    document_ref=booking_ref,
                    created_by=username,
                    preferred_paths=[
                        ('Deposits', 'Advance Payments', 'Reservation Deposit'),
                        ('Deposits', 'Advance Payments', 'Event Deposit'),
                    ],
                )
                db.add(BookingAccountingLink(booking_id=booking.id, record_id=cancel_dep.id, link_type='deposit_liability_reversal'))
        elif checking_out:
            if old_deposit != 0:
                checkout_dep = create_approved_record(
                    db,
                    module_slug='rooms',
                    direction='liability',
                    amount=-old_deposit,
                    name=f'Checkout deposit clearing {booking.guest_name}',
                    transaction_date=transaction_date,
                    payment_method=payment_method,
                    counterparty=booking.guest_name,
                    notes='Auto-generated checkout deposit clearing entry',
                    document_ref=booking_ref,
                    created_by=username,
                    preferred_paths=[
                        ('Deposits', 'Advance Payments', 'Reservation Deposit'),
                        ('Deposits', 'Advance Payments', 'Event Deposit'),
                    ],
                )
                db.add(BookingAccountingLink(booking_id=booking.id, record_id=checkout_dep.id, link_type='deposit_liability_clear'))
        else:
            dep_delta = round(new_deposit - old_deposit, 4)
            if dep_delta != 0:
                dep_note = 'Auto-generated booking deposit adjustment (increase)' if dep_delta > 0 else 'Auto-generated booking deposit adjustment (decrease/reversal)'
                dep_record = create_approved_record(
                    db,
                    module_slug='rooms',
                    direction='liability',
                    amount=dep_delta,
                    name=f'Booking deposit adjustment {booking.guest_name}',
                    transaction_date=transaction_date,
                    payment_method=payment_method,
                    counterparty=booking.guest_name,
                    notes=dep_note,
                    document_ref=booking_ref,
                    created_by=username,
                    preferred_paths=[
                        ('Deposits', 'Advance Payments', 'Reservation Deposit'),
                        ('Deposits', 'Advance Payments', 'Event Deposit'),
                    ],
                )
                db.add(BookingAccountingLink(booking_id=booking.id, record_id=dep_record.id, link_type='deposit_liability_adjustment'))

    db.add(booking)
    db.commit()

    booking = (
        db.query(Booking)
        .options(
            selectinload(Booking.accounting_links).selectinload(BookingAccountingLink.record),
            selectinload(Booking.guest),
            selectinload(Booking.room),
            selectinload(Booking.room_type_obj),
            selectinload(Booking.rate_plan),
            selectinload(Booking.channel_obj),
        )
        .filter(Booking.id == booking.id)
        .first()
    )
    return _serialize_booking(booking)


def list_room_breakfast_logs(db: Session, limit: int = 300):
    rows = (
        db.query(RoomBreakfastLog)
        .options(selectinload(RoomBreakfastLog.menu_item), selectinload(RoomBreakfastLog.sku))
        .order_by(RoomBreakfastLog.id.desc())
        .limit(limit)
        .all()
    )
    return [_serialize_breakfast(x) for x in rows]


def create_room_breakfast_log(db: Session, payload, username: str | None = None) -> dict:
    quantity = float(payload.quantity or 0)
    if quantity <= 0:
        raise ValueError('Breakfast quantity must be greater than zero.')

    booking = None
    if payload.booking_id:
        booking = db.get(Booking, int(payload.booking_id))
        if not booking:
            raise ValueError(f'Booking {payload.booking_id} not found.')

    menu_item = db.get(MenuItem, int(payload.menu_item_id))
    if not menu_item:
        raise ValueError(f'Menu item {payload.menu_item_id} not found.')

    sku = None
    if payload.sku_id:
        sku = db.get(MenuSKU, int(payload.sku_id))
        if not sku:
            raise ValueError(f'SKU {payload.sku_id} not found.')
        if sku.menu_item_id != menu_item.id:
            raise ValueError('SKU does not belong to selected menu item.')

    meal_date = payload.meal_date or (booking.check_in if booking else None) or _today()
    breakfast_no = (payload.breakfast_no or '').strip() or generate_room_breakfast_no(db)

    existing = db.query(RoomBreakfastLog).filter(RoomBreakfastLog.breakfast_no == breakfast_no).first()
    if existing:
        raise ValueError(f'Breakfast reference {breakfast_no} already exists.')

    requirements = expand_menu_or_sku_to_inventory_requirements(
        db,
        menu_item=menu_item,
        sku=sku,
        quantity=quantity,
        strict_inventory=payload.strict_inventory,
    )
    cogs_amount = consume_inventory_requirements(
        db,
        requirements,
        reason='Room Breakfast',
        module_slug='inventory',
        reference_no=breakfast_no,
        movement_date=meal_date,
        notes_prefix=f'Room breakfast {breakfast_no}',
    )

    if payload.charged_amount is not None and float(payload.charged_amount or 0) < 0:
        raise ValueError('charged_amount cannot be negative.')

    charged_amount = float(payload.charged_amount) if payload.charged_amount is not None else 0.0
    if payload.charged_amount is None and payload.charge_to_room:
        base_price = float((sku.price if sku else menu_item.price) or 0)
        charged_amount = max(base_price * quantity, 0.0)

    counterparty = payload.guest_name or (booking.guest_name if booking else None)
    auto_post = bool(getattr(payload, 'auto_post_accounting', False))

    income_record = None
    if auto_post and charged_amount > 0:
        income_record = create_approved_record(
            db,
            module_slug='breakfast',
            direction='income',
            amount=charged_amount,
            name=f'Room breakfast charge {breakfast_no}',
            transaction_date=meal_date,
            payment_method=payload.payment_method,
            counterparty=counterparty,
            notes='Auto-generated room breakfast income entry',
            document_ref=breakfast_no,
            created_by=username,
            preferred_paths=[
                ('Paid Breakfast', 'Guest Paid', 'Additional Breakfast'),
                ('Paid Breakfast', 'Guest Paid', 'Walk-in'),
            ],
        )

    cogs_record = None
    if auto_post:
        cogs_record = create_approved_record(
            db,
            module_slug='breakfast',
            direction='expense',
            amount=cogs_amount,
            name=f'Breakfast consumption {breakfast_no}',
            transaction_date=meal_date,
            payment_method='inventory',
            counterparty=counterparty,
            notes='Auto-generated room breakfast COGS entry',
            document_ref=breakfast_no,
            created_by=username,
            preferred_paths=[
                ('Cost', 'Food Cost', 'Ingredient Cost'),
                ('Inventory Usage', 'Staples', 'Eggs'),
                ('Included Breakfast', 'Guest Breakfast', 'Claimed'),
            ],
        )

    log = RoomBreakfastLog(
        breakfast_no=breakfast_no,
        booking_id=booking.id if booking else None,
        meal_date=meal_date,
        guest_name=counterparty,
        menu_item_id=menu_item.id,
        sku_id=sku.id if sku else None,
        quantity=quantity,
        charged_amount=charged_amount,
        charge_to_room=bool(payload.charge_to_room),
        cogs_amount=round(cogs_amount, 4),
        income_record_id=income_record.id if income_record else None,
        cogs_record_id=cogs_record.id if cogs_record else None,
        notes=payload.notes,
        created_by=username,
    )
    db.add(log)
    db.flush()

    if booking:
        if income_record:
            db.add(BookingAccountingLink(booking_id=booking.id, record_id=income_record.id, link_type='breakfast_income'))
        if cogs_record:
            db.add(BookingAccountingLink(booking_id=booking.id, record_id=cogs_record.id, link_type='breakfast_cogs'))

    db.commit()

    log = (
        db.query(RoomBreakfastLog)
        .options(selectinload(RoomBreakfastLog.menu_item), selectinload(RoomBreakfastLog.sku))
        .filter(RoomBreakfastLog.id == log.id)
        .first()
    )
    return _serialize_breakfast(log)


def list_staff_meal_logs(db: Session, limit: int = 300):
    rows = (
        db.query(StaffMealLog)
        .options(
            selectinload(StaffMealLog.lines).selectinload(StaffMealIngredient.inventory_item),
            selectinload(StaffMealLog.menu_item),
            selectinload(StaffMealLog.sku),
        )
        .order_by(StaffMealLog.id.desc())
        .limit(limit)
        .all()
    )
    return [_serialize_staff_meal(x) for x in rows]


def create_staff_meal_log(db: Session, payload, username: str | None = None) -> dict:
    quantity = float(payload.quantity or 0)
    if quantity <= 0:
        raise ValueError('Staff meal quantity must be greater than zero.')

    meal_date = payload.meal_date or _today()
    meal_no = (payload.meal_no or '').strip() or generate_staff_meal_no(db)

    existing = db.query(StaffMealLog).filter(StaffMealLog.meal_no == meal_no).first()
    if existing:
        raise ValueError(f'Staff meal reference {meal_no} already exists.')

    menu_item = None
    sku = None
    recipe_requirements: dict[int, float] = {}

    if payload.menu_item_id:
        menu_item = db.get(MenuItem, int(payload.menu_item_id))
        if not menu_item:
            raise ValueError(f'Menu item {payload.menu_item_id} not found.')

    if payload.sku_id:
        sku = db.get(MenuSKU, int(payload.sku_id))
        if not sku:
            raise ValueError(f'SKU {payload.sku_id} not found.')
        if menu_item and sku.menu_item_id != menu_item.id:
            raise ValueError('SKU does not belong to selected menu item.')
        if not menu_item:
            menu_item = db.get(MenuItem, int(sku.menu_item_id))

    if menu_item:
        recipe_requirements = expand_menu_or_sku_to_inventory_requirements(
            db,
            menu_item=menu_item,
            sku=sku,
            quantity=quantity,
            strict_inventory=payload.strict_inventory,
        )

    manual_requirements: dict[int, float] = {}
    for row in payload.ingredients or []:
        inv = db.get(InventoryItem, int(row.inventory_item_id))
        if not inv:
            raise ValueError(f'Inventory item {row.inventory_item_id} not found.')
        line_qty = float(row.quantity or 0)
        if line_qty <= 0:
            raise ValueError('Staff meal ingredient quantity must be greater than zero.')
        manual_requirements[inv.id] = manual_requirements.get(inv.id, 0.0) + line_qty

    requirements = merge_inventory_requirements(recipe_requirements, manual_requirements)
    if not requirements:
        raise ValueError('No inventory requirements found. Add a recipe-based dish and/or manual ingredients.')

    cogs_amount = consume_inventory_requirements(
        db,
        requirements,
        reason='Staff Meals',
        module_slug='inventory',
        reference_no=meal_no,
        movement_date=meal_date,
        notes_prefix=f'Staff meal {payload.dish_name}',
    )

    served_to = (payload.served_to or 'Kitchen Staff').strip() or 'Kitchen Staff'
    preferred_staff_item = 'Service Staff' if 'service' in _normalize(served_to) else 'Kitchen Staff'

    expense_record = None
    if bool(getattr(payload, 'auto_post_accounting', False)):
        expense_record = create_approved_record(
            db,
            module_slug='restaurant',
            direction='expense',
            amount=cogs_amount,
            name=f'Staff meal {payload.dish_name}',
            transaction_date=meal_date,
            payment_method=payload.payment_method or 'inventory',
            counterparty=served_to,
            notes='Auto-generated staff meal consumption entry',
            document_ref=meal_no,
            created_by=username,
            preferred_paths=[
                ('Internal Use', 'Staff Meals', preferred_staff_item),
                ('Manual / Custom Expense', 'Adjustments', 'Manual Ingredient Use'),
            ],
        )

    log = StaffMealLog(
        meal_no=meal_no,
        meal_date=meal_date,
        dish_name=payload.dish_name,
        menu_item_id=menu_item.id if menu_item else None,
        sku_id=sku.id if sku else None,
        quantity=quantity,
        served_to=served_to,
        cogs_amount=round(cogs_amount, 4),
        expense_record_id=expense_record.id if expense_record else None,
        notes=payload.notes,
        created_by=username,
    )
    db.add(log)
    db.flush()

    for inventory_item_id, req_qty in recipe_requirements.items():
        inv = db.get(InventoryItem, int(inventory_item_id))
        db.add(StaffMealIngredient(
            staff_meal_log_id=log.id,
            inventory_item_id=inventory_item_id,
            quantity=req_qty,
            unit=(inv.unit if inv else ''),
            source='recipe',
            notes='From menu/SKU recipe',
        ))

    for row in payload.ingredients or []:
        inv = db.get(InventoryItem, int(row.inventory_item_id))
        db.add(StaffMealIngredient(
            staff_meal_log_id=log.id,
            inventory_item_id=row.inventory_item_id,
            quantity=float(row.quantity or 0),
            unit=row.unit or (inv.unit if inv else ''),
            source='manual',
            notes=row.notes,
        ))

    db.commit()

    log = (
        db.query(StaffMealLog)
        .options(
            selectinload(StaffMealLog.lines).selectinload(StaffMealIngredient.inventory_item),
            selectinload(StaffMealLog.menu_item),
            selectinload(StaffMealLog.sku),
        )
        .filter(StaffMealLog.id == log.id)
        .first()
    )
    return _serialize_staff_meal(log)
