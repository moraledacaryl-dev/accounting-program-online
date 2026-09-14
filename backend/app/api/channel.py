from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_any_permissions
from app.db.database import get_db
from app.models.channel_payout_reconciliation import ChannelPayoutBookingLink
from app.models.entities import Booking, BookingChannel, ChannelPayout, ChannelPayoutAccountingLink, Record
from app.schemas.common import ChannelPayoutCreate, ChannelPayoutSettle, ChannelPayoutUpdate
from app.services.restaurant_service import create_approved_record

router = APIRouter()
CENT = Decimal('0.01')


class PayoutReconcileItem(BaseModel):
    booking_id: int
    actual_amount: Decimal = Field(ge=0, max_digits=20, decimal_places=4)


class PayoutReconcileBatch(BaseModel):
    channel_id: int
    actual_payout_date: str
    payout_reference: str | None = Field(default=None, max_length=255)
    amount_received: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=4)
    payment_method: str = 'bank_transfer'
    auto_post_accounting: bool = True
    notes: str | None = None
    items: list[PayoutReconcileItem] = Field(min_length=1, max_length=500)

    @model_validator(mode='after')
    def unique_bookings(self):
        ids = [item.booking_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError('Each booking can appear only once in a payout batch.')
        return self


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


def _deduction_amount(gross, actual) -> Decimal:
    return (_money(gross) - _money(actual)).quantize(CENT, rounding=ROUND_HALF_UP)


def _deduction_percent(gross, actual) -> float | None:
    original = _money(gross)
    if original <= 0:
        return None
    return float((_deduction_amount(original, actual) / original * Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def _serialize_link(link: ChannelPayoutAccountingLink) -> dict:
    rec = link.record
    return {
        'id': link.id,
        'link_type': link.link_type,
        'record_id': link.record_id,
        'record_name': rec.name if rec else None,
        'record_direction': rec.direction if rec else None,
        'record_amount': rec.amount if rec else None,
        'record_date': rec.transaction_date if rec else None,
    }


def _booking_link(db: Session, payout_id: int) -> ChannelPayoutBookingLink | None:
    return db.query(ChannelPayoutBookingLink).filter(ChannelPayoutBookingLink.payout_id == payout_id).first()


def _serialize_payout(obj: ChannelPayout, db: Session | None = None) -> dict:
    channel_obj = getattr(obj, 'channel_obj', None)
    links = getattr(obj, 'accounting_links', None) or []
    booking_link = _booking_link(db, obj.id) if db else None
    booking = db.get(Booking, booking_link.booking_id) if db and booking_link else None
    gross = _money(obj.gross_amount)
    actual = _money(obj.net_amount)
    return {
        'id': obj.id,
        'channel_id': obj.channel_id,
        'channel': obj.channel,
        'channel_code': channel_obj.code if channel_obj else None,
        'channel_display_name': channel_obj.name if channel_obj else obj.channel,
        'booking_ref': obj.booking_ref,
        'booking_id': booking_link.booking_id if booking_link else None,
        'payout_reference': booking_link.payout_reference if booking_link else None,
        'guest_name': booking.guest_name if booking else None,
        'room_name': booking.room_name if booking else None,
        'check_in': booking.check_in if booking else None,
        'check_out': booking.check_out if booking else None,
        'gross_amount': obj.gross_amount,
        'commission_amount': obj.commission_amount,
        'net_amount': obj.net_amount,
        'deduction_amount': float(_deduction_amount(gross, actual)),
        'deduction_percent': _deduction_percent(gross, actual),
        'expected_payout_date': obj.expected_payout_date,
        'actual_payout_date': obj.actual_payout_date,
        'status': obj.status,
        'notes': obj.notes,
        'created_at': obj.created_at,
        'updated_at': obj.updated_at,
        'accounting_links': [_serialize_link(link) for link in links],
    }


def _get_payout_with_links(db: Session, payout_id: int) -> ChannelPayout | None:
    return (
        db.query(ChannelPayout)
        .options(
            selectinload(ChannelPayout.accounting_links).selectinload(ChannelPayoutAccountingLink.record),
            selectinload(ChannelPayout.channel_obj),
        )
        .filter(ChannelPayout.id == payout_id)
        .first()
    )


def _resolve_payout_channel(db: Session, channel_id: int | None, channel_text: str | None) -> tuple[int | None, str]:
    if channel_id:
        channel_obj = db.get(BookingChannel, int(channel_id))
        if not channel_obj:
            raise ValueError(f'channel_id {channel_id} not found.')
        return channel_obj.id, channel_obj.name

    channel_label = (channel_text or '').strip()
    if channel_label:
        channel_obj = (
            db.query(BookingChannel)
            .filter(
                or_(
                    func.lower(BookingChannel.name) == channel_label.lower(),
                    func.lower(BookingChannel.code) == channel_label.lower(),
                )
            )
            .first()
        )
        if channel_obj:
            return channel_obj.id, channel_obj.name
        return None, channel_label
    raise ValueError('Select a booking channel.')


def _linked_total(db: Session, payout_id: int, link_type: str) -> float:
    value = (
        db.query(func.coalesce(func.sum(Record.amount), 0))
        .join(ChannelPayoutAccountingLink, ChannelPayoutAccountingLink.record_id == Record.id)
        .filter(
            ChannelPayoutAccountingLink.payout_id == payout_id,
            ChannelPayoutAccountingLink.link_type == link_type,
        )
        .scalar()
    )
    return float(value or 0)


def _post_commission_delta(db: Session, payout: ChannelPayout, *, target_amount: float, tx_date: str | None, payment_method: str | None, username: str | None):
    existing_total = _linked_total(db, payout.id, 'commission_expense')
    delta = round(float(target_amount or 0) - existing_total, 4)
    if delta == 0:
        return None
    channel_label = payout.channel or 'OTA'
    rec = create_approved_record(
        db,
        module_slug='channel_ota',
        direction='expense',
        amount=delta,
        name=f'{channel_label} commission {payout.booking_ref or payout.id}',
        transaction_date=tx_date,
        payment_method=payment_method or 'ota_payout',
        counterparty=channel_label,
        notes='Auto-generated OTA commission entry',
        document_ref=payout.booking_ref or f'PAYOUT-{payout.id}',
        created_by=username,
        preferred_paths=[
            ('Channel Costs', 'Commission', f'{channel_label} Commission'),
            ('Channel Costs', 'Commission', 'Agoda Commission'),
            ('Channel Costs', 'Promotions', 'Discounts'),
        ],
    )
    db.add(ChannelPayoutAccountingLink(payout_id=payout.id, record_id=rec.id, link_type='commission_expense'))
    return rec


def _post_settlement_delta(db: Session, payout: ChannelPayout, *, target_amount: float, tx_date: str | None, username: str | None):
    existing_total = _linked_total(db, payout.id, 'payout_settlement')
    delta = round(float(target_amount or 0) - existing_total, 4)
    if delta == 0:
        return None
    rec = create_approved_record(
        db,
        module_slug='finance',
        direction='asset',
        amount=delta,
        name=f'OTA payout settlement {payout.booking_ref or payout.id}',
        transaction_date=tx_date,
        payment_method='ota_payout',
        counterparty=payout.channel,
        notes='Auto-generated OTA receivable settlement entry',
        document_ref=payout.booking_ref or f'PAYOUT-{payout.id}',
        created_by=username,
        preferred_paths=[
            ('Cash', 'Collections', 'Collection Received'),
            ('Receivables', 'Channel Receivable', 'Payout Expected'),
            ('Bank', 'Deposits', 'Bank Transfer'),
        ],
    )
    db.add(ChannelPayoutAccountingLink(payout_id=payout.id, record_id=rec.id, link_type='payout_settlement'))
    return rec


def _booking_ref(booking: Booking) -> str:
    external = str(getattr(booking, 'external_booking_id', '') or '').strip()
    return external or f'BOOK-{booking.id}'


@router.get('/payouts')
def payouts(db: Session = Depends(get_db), user=Depends(require_any_permissions('bookings.view', 'cashflow.view', 'reports.view'))):
    rows = (
        db.query(ChannelPayout)
        .options(
            selectinload(ChannelPayout.accounting_links).selectinload(ChannelPayoutAccountingLink.record),
            selectinload(ChannelPayout.channel_obj),
        )
        .order_by(ChannelPayout.id.desc())
        .all()
    )
    return [_serialize_payout(x, db) for x in rows]


@router.get('/payout-channel-options')
def payout_channel_options(db: Session = Depends(get_db), user=Depends(require_any_permissions('bookings.view', 'cashflow.view', 'reports.view'))):
    channels = (
        db.query(BookingChannel)
        .filter(BookingChannel.is_active == True)
        .order_by(BookingChannel.name.asc())
        .all()
    )
    setup_channel_rows = [
        {
            'id': row.id,
            'code': row.code,
            'name': row.name,
            'channel_class': row.channel_class,
            'settlement_mode': row.settlement_mode,
            'default_commission_rate': float(row.default_commission_rate or 0),
            'is_prepaid': bool(row.is_prepaid),
        }
        for row in channels
    ]
    setup_keys = {str((row.name or '')).strip().lower() for row in channels}
    setup_keys.update({str((row.code or '')).strip().lower() for row in channels})
    legacy_labels = (
        db.query(ChannelPayout.channel)
        .filter(ChannelPayout.channel_id == None)  # noqa: E711
        .filter(ChannelPayout.channel.isnot(None))
        .filter(ChannelPayout.channel != '')
        .group_by(ChannelPayout.channel)
        .order_by(ChannelPayout.channel.asc())
        .all()
    )
    return {
        'channels': setup_channel_rows,
        'legacy_channels': [label for (label,) in legacy_labels if str(label or '').strip().lower() not in setup_keys],
    }


@router.get('/payout-bookings')
def payout_bookings(
    channel_id: int | None = Query(default=None, ge=1),
    status: str = Query(default='awaiting', pattern='^(awaiting|paid|all)$'),
    search: str = Query(default='', max_length=120),
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('bookings.view', 'cashflow.view', 'reports.view')),
):
    query = (
        db.query(Booking, BookingChannel, ChannelPayoutBookingLink, ChannelPayout)
        .join(BookingChannel, Booking.channel_id == BookingChannel.id)
        .outerjoin(ChannelPayoutBookingLink, ChannelPayoutBookingLink.booking_id == Booking.id)
        .outerjoin(ChannelPayout, ChannelPayout.id == ChannelPayoutBookingLink.payout_id)
        .filter(BookingChannel.is_active == True)
        .filter(func.lower(func.coalesce(Booking.status, '')) .notin_(['cancelled', 'canceled', 'no_show', 'noshow']))
    )
    if channel_id:
        query = query.filter(Booking.channel_id == channel_id)
    term = search.strip()
    if term:
        like = f'%{term}%'
        query = query.filter(or_(Booking.guest_name.ilike(like), Booking.external_booking_id.ilike(like), func.cast(Booking.id, String).ilike(like)))
    rows = query.order_by(Booking.check_out.desc(), Booking.id.desc()).limit(2000).all()

    out = []
    for booking, channel, link, payout in rows:
        paid = bool(payout and str(payout.status or '').strip().lower() == 'paid')
        if status == 'awaiting' and paid:
            continue
        if status == 'paid' and not paid:
            continue
        gross = _money(booking.gross_amount)
        actual = _money(payout.net_amount) if payout else Decimal('0')
        expected_rate = Decimal(str(channel.default_commission_rate or 0))
        expected_net = (gross * (Decimal('1') - expected_rate / Decimal('100'))).quantize(CENT, rounding=ROUND_HALF_UP)
        out.append({
            'booking_id': booking.id,
            'booking_ref': _booking_ref(booking),
            'guest_name': booking.guest_name,
            'room_name': booking.room_name,
            'check_in': booking.check_in,
            'check_out': booking.check_out,
            'booking_status': booking.status,
            'channel_id': channel.id,
            'channel_name': channel.name,
            'original_amount': float(gross),
            'expected_commission_rate': float(expected_rate),
            'expected_net_amount': float(expected_net),
            'payout_id': payout.id if payout else None,
            'payout_status': payout.status if payout else 'unpaid',
            'actual_amount': float(actual) if payout else None,
            'deduction_amount': float(_deduction_amount(gross, actual)) if payout else None,
            'deduction_percent': _deduction_percent(gross, actual) if payout else None,
            'payout_reference': link.payout_reference if link else None,
            'actual_payout_date': payout.actual_payout_date if payout else None,
        })
    return out


@router.post('/payouts/reconcile')
def reconcile_payout_batch(
    payload: PayoutReconcileBatch,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('cashflow.money_in', 'cashflow.money_out', 'reports.view')),
):
    channel = db.get(BookingChannel, payload.channel_id)
    if not channel or not channel.is_active:
        raise HTTPException(status_code=400, detail='Select an active booking channel.')

    allocated = sum((_money(item.actual_amount) for item in payload.items), Decimal('0'))
    if payload.amount_received is not None and abs(_money(payload.amount_received) - allocated) > CENT:
        raise HTTPException(status_code=400, detail='Allocated booking payouts must equal the bank payout amount before reconciliation.')

    try:
        results = []
        for item in payload.items:
            booking = db.get(Booking, item.booking_id)
            if not booking:
                raise ValueError(f'Booking {item.booking_id} was not found.')
            if booking.channel_id != channel.id:
                raise ValueError(f'Booking {item.booking_id} does not belong to {channel.name}.')
            if str(booking.status or '').strip().lower() in {'cancelled', 'canceled', 'no_show', 'noshow'}:
                raise ValueError(f'Booking {item.booking_id} is cancelled/no-show and cannot be reconciled.')

            existing_link = db.query(ChannelPayoutBookingLink).filter(ChannelPayoutBookingLink.booking_id == booking.id).first()
            existing = db.get(ChannelPayout, existing_link.payout_id) if existing_link else None
            if existing and str(existing.status or '').strip().lower() == 'paid':
                raise ValueError(f'Booking {item.booking_id} is already marked paid by its channel.')

            gross = _money(booking.gross_amount)
            actual = _money(item.actual_amount)
            if actual > gross and gross >= 0:
                raise ValueError(f'Booking {item.booking_id} payout cannot exceed its original amount.')
            deduction = _deduction_amount(gross, actual)

            payout = existing or ChannelPayout()
            payout.channel_id = channel.id
            payout.channel = channel.name
            payout.booking_ref = _booking_ref(booking)
            payout.gross_amount = gross
            payout.commission_amount = deduction
            payout.net_amount = actual
            payout.actual_payout_date = payload.actual_payout_date
            payout.status = 'paid'
            if payload.notes:
                payout.notes = payload.notes if not payout.notes else f'{payout.notes}\n{payload.notes}'.strip()
            db.add(payout)
            db.flush()

            if existing_link:
                existing_link.payout_reference = (payload.payout_reference or '').strip() or None
            else:
                existing_link = ChannelPayoutBookingLink(
                    payout_id=payout.id,
                    booking_id=booking.id,
                    payout_reference=(payload.payout_reference or '').strip() or None,
                )
            db.add(existing_link)

            if payload.auto_post_accounting:
                _post_commission_delta(
                    db, payout,
                    target_amount=float(deduction),
                    tx_date=payload.actual_payout_date,
                    payment_method=payload.payment_method,
                    username=getattr(user, 'username', None),
                )
                _post_settlement_delta(
                    db, payout,
                    target_amount=float(actual),
                    tx_date=payload.actual_payout_date,
                    username=getattr(user, 'username', None),
                )
            results.append(payout.id)

        db.commit()
        return {
            'ok': True,
            'channel_id': channel.id,
            'channel': channel.name,
            'booking_count': len(results),
            'allocated_amount': float(allocated),
            'payout_reference': (payload.payout_reference or '').strip() or None,
            'payout_ids': results,
        }
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        db.rollback()
        raise


@router.post('/payouts')
def add_payout(
    payload: ChannelPayoutCreate,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('cashflow.money_in', 'cashflow.money_out', 'reports.view')),
):
    try:
        payload_data = payload.model_dump(exclude={'payment_method', 'auto_post_accounting'})
        resolved_channel_id, resolved_channel_name = _resolve_payout_channel(db, payload.channel_id, payload.channel)
        payload_data['channel_id'] = resolved_channel_id
        payload_data['channel'] = resolved_channel_name
        obj = ChannelPayout(**payload_data)
        db.add(obj)
        db.flush()
        if payload.auto_post_accounting:
            tx_date = payload.actual_payout_date or payload.expected_payout_date
            _post_commission_delta(db, obj, target_amount=float(obj.commission_amount or 0), tx_date=tx_date, payment_method=payload.payment_method, username=getattr(user, 'username', None))
            if (obj.status or '').strip().lower() == 'paid':
                _post_settlement_delta(db, obj, target_amount=float(obj.net_amount or 0), tx_date=obj.actual_payout_date or tx_date, username=getattr(user, 'username', None))
        db.commit()
        return _serialize_payout(_get_payout_with_links(db, obj.id), db)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put('/payouts/{payout_id}')
def update_payout(
    payout_id: int,
    payload: ChannelPayoutUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('cashflow.money_in', 'cashflow.money_out', 'reports.view')),
):
    obj = db.get(ChannelPayout, payout_id)
    if not obj:
        raise HTTPException(status_code=404, detail='Payout not found')
    try:
        data = payload.model_dump(exclude_unset=True, exclude={'payment_method', 'auto_post_accounting'})
        if 'channel_id' in data or 'channel' in data:
            resolved_channel_id, resolved_channel_name = _resolve_payout_channel(db, data.get('channel_id', obj.channel_id), data.get('channel', obj.channel))
            obj.channel_id = resolved_channel_id
            obj.channel = resolved_channel_name
            data.pop('channel_id', None)
            data.pop('channel', None)
        for key, value in data.items():
            setattr(obj, key, value)
        db.add(obj)
        db.flush()
        if payload.auto_post_accounting:
            tx_date = obj.actual_payout_date or obj.expected_payout_date
            _post_commission_delta(db, obj, target_amount=float(obj.commission_amount or 0), tx_date=tx_date, payment_method=payload.payment_method, username=getattr(user, 'username', None))
            if (obj.status or '').strip().lower() == 'paid':
                _post_settlement_delta(db, obj, target_amount=float(obj.net_amount or 0), tx_date=obj.actual_payout_date or tx_date, username=getattr(user, 'username', None))
        db.commit()
        return _serialize_payout(_get_payout_with_links(db, obj.id), db)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/payouts/{payout_id}/settle')
def settle_payout(
    payout_id: int,
    payload: ChannelPayoutSettle,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('cashflow.money_in', 'cashflow.money_out', 'reports.view')),
):
    obj = db.get(ChannelPayout, payout_id)
    if not obj:
        raise HTTPException(status_code=404, detail='Payout not found')
    try:
        if payload.actual_payout_date:
            obj.actual_payout_date = payload.actual_payout_date
        obj.status = 'paid'
        if payload.notes:
            obj.notes = f"{obj.notes or ''}\n{payload.notes}".strip()
        db.add(obj)
        db.flush()
        if payload.auto_post_accounting:
            _post_settlement_delta(db, obj, target_amount=float(obj.net_amount or 0), tx_date=obj.actual_payout_date or obj.expected_payout_date, username=getattr(user, 'username', None))
        db.commit()
        return _serialize_payout(_get_payout_with_links(db, obj.id), db)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
