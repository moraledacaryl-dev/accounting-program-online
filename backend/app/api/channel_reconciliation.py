from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.channel import _post_commission_delta, _post_settlement_delta
from app.api.deps import require_any_permissions
from app.db.database import get_db
from app.models.channel_payout_reconciliation import ChannelBookingStaySnapshot, ChannelPayoutBookingLink
from app.models.entities import Beds24BookingMap, Booking, BookingChannel, ChannelPayout, RatePlan

router = APIRouter()
CENT = Decimal('0.01')
_STANDARD_RATE_NAMES = ('standard', 'normal', 'rack')
_PUBLISHED_ROOM_RATES = {
    'cafe suite': Decimal('2500.00'), 'grandeur': Decimal('3500.00'),
    'solace': Decimal('4000.00'), 'twinspire': Decimal('3000.00'),
    'skyroom': Decimal('3200.00'), 'sky room': Decimal('3200.00'),
    'perch 1': Decimal('4200.00'), 'perch 2': Decimal('4300.00'),
    'crown': Decimal('3300.00'),
}


class PayoutReconcileItem(BaseModel):
    booking_id: int
    expected_amount: Decimal = Field(ge=0, max_digits=20, decimal_places=4)
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


def _standard_plan_rank(plan: RatePlan) -> tuple[int, int]:
    code = str(getattr(plan, 'code', '') or '').strip().lower()
    name = str(getattr(plan, 'name', '') or '').strip().lower()
    if code in _STANDARD_RATE_NAMES: return (0, int(getattr(plan, 'id', 0) or 0))
    if name in _STANDARD_RATE_NAMES: return (1, int(getattr(plan, 'id', 0) or 0))
    if any(code.startswith(f'{token}-') or code.startswith(f'{token}_') for token in _STANDARD_RATE_NAMES): return (2, int(getattr(plan, 'id', 0) or 0))
    if any(name.startswith(token) for token in _STANDARD_RATE_NAMES): return (3, int(getattr(plan, 'id', 0) or 0))
    return (99, int(getattr(plan, 'id', 0) or 0))


def _published_room_rate(booking: Booking) -> Decimal | None:
    room_name = str(getattr(booking, 'room_name', '') or '').strip().lower()
    if not room_name:
        room = getattr(booking, 'room', None)
        room_name = str(getattr(room, 'name', '') or '').strip().lower() if room else ''
    return _PUBLISHED_ROOM_RATES.get(room_name)


def _stay_date(value) -> date | None:
    if isinstance(value, datetime): return value.date()
    if isinstance(value, date): return value
    text = str(value or '').strip()
    if not text: return None
    try: return date.fromisoformat(text[:10])
    except ValueError: return None


def _date_range_nights(check_in_value, check_out_value) -> int | None:
    check_in, check_out = _stay_date(check_in_value), _stay_date(check_out_value)
    if check_in is None or check_out is None: return None
    return max(1, (check_out - check_in).days)


def _stay_nights(booking: Booking) -> int:
    return _date_range_nights(getattr(booking, 'check_in', None), getattr(booking, 'check_out', None)) or 1


def _channel_stay_nights(db: Session, booking: Booking) -> int:
    """Use immutable first-seen OTA dates; mutable Beds24/current booking dates are fallbacks only."""
    booking_id = getattr(booking, 'id', None)
    if booking_id:
        snapshot = db.query(ChannelBookingStaySnapshot).filter(ChannelBookingStaySnapshot.booking_id == booking_id).first()
        if snapshot:
            nights = _date_range_nights(snapshot.ota_check_in, snapshot.ota_check_out)
            if nights is not None: return nights
        mapping = db.query(Beds24BookingMap).filter(Beds24BookingMap.local_booking_id == booking_id).first()
        if mapping:
            nights = _date_range_nights(mapping.beds24_check_in, mapping.beds24_check_out)
            if nights is not None: return nights
    return _stay_nights(booking)


def _normal_room_rate(db: Session, booking: Booking) -> Decimal:
    booking_value = _money(booking.gross_amount)
    nights = Decimal(_channel_stay_nights(db, booking))
    room_type_id = getattr(booking, 'room_type_id', None)
    if not room_type_id:
        room = getattr(booking, 'room', None)
        room_type_id = getattr(room, 'room_type_id', None) if room else None
    if room_type_id:
        plans = db.query(RatePlan).filter(RatePlan.room_type_id == room_type_id).filter(RatePlan.is_active == True).all()
        standard_plans = [p for p in plans if _standard_plan_rank(p)[0] < 99 and _money(p.base_rate) > 0]
        if standard_plans:
            return _money(_money(min(standard_plans, key=_standard_plan_rank).base_rate) * nights)
    published_rate = _published_room_rate(booking)
    return _money(published_rate * nights) if published_rate is not None else booking_value


def _booking_ref(booking: Booking) -> str:
    external = str(getattr(booking, 'external_booking_id', '') or '').strip()
    return external or f'BOOK-{booking.id}'


@router.get('/channels')
def reconciliation_channels(db: Session = Depends(get_db), user=Depends(require_any_permissions('bookings.view', 'cashflow.view', 'reports.view'))):
    rows = db.query(BookingChannel).filter(BookingChannel.is_active == True).order_by(BookingChannel.name.asc()).all()
    return [{'id': r.id, 'code': r.code, 'name': r.name, 'channel_class': r.channel_class, 'settlement_mode': r.settlement_mode, 'default_commission_rate': float(r.default_commission_rate or 0), 'is_prepaid': bool(r.is_prepaid)} for r in rows]


@router.get('/bookings')
def payout_bookings(channel_id: int = Query(ge=1), search: str = Query(default='', max_length=120), db: Session = Depends(get_db), user=Depends(require_any_permissions('bookings.view', 'cashflow.view', 'reports.view'))):
    query = (db.query(Booking, BookingChannel, ChannelPayoutBookingLink, ChannelPayout).join(BookingChannel, Booking.channel_id == BookingChannel.id).outerjoin(ChannelPayoutBookingLink, ChannelPayoutBookingLink.booking_id == Booking.id).outerjoin(ChannelPayout, ChannelPayout.id == ChannelPayoutBookingLink.payout_id).filter(Booking.channel_id == channel_id).filter(BookingChannel.is_active == True).filter(func.lower(func.coalesce(Booking.status, '')).notin_(['cancelled', 'canceled', 'no_show', 'noshow'])))
    term = search.strip()
    if term:
        like = f'%{term}%'; clauses = [Booking.guest_name.ilike(like), Booking.external_booking_id.ilike(like)]
        if term.isdigit(): clauses.append(Booking.id == int(term))
        query = query.filter(or_(*clauses))
    out = []
    for booking, channel, link, payout in query.order_by(Booking.check_out.desc(), Booking.id.desc()).limit(2000).all():
        if payout and str(payout.status or '').strip().lower() == 'paid': continue
        expected = _money(payout.gross_amount) if payout else _money(booking.gross_amount)
        original = _normal_room_rate(db, booking)
        difference = (original - expected).quantize(CENT, rounding=ROUND_HALF_UP)
        rate = ((difference / original * Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if original > 0 else Decimal('0.00'))
        out.append({'booking_id': booking.id, 'booking_ref': _booking_ref(booking), 'guest_name': booking.guest_name, 'room_name': booking.room_name, 'check_in': booking.check_in, 'check_out': booking.check_out, 'booking_status': booking.status, 'channel_id': channel.id, 'channel_name': channel.name, 'original_amount': float(original), 'expected_net_amount': float(expected), 'expected_commission_rate': float(rate), 'expected_difference_amount': float(difference), 'pending_payout_id': payout.id if payout else None, 'pending_actual_amount': float(_money(payout.net_amount)) if payout else None})
    return out


@router.get('/history')
def reconciliation_history(channel_id: int | None = Query(default=None, ge=1), db: Session = Depends(get_db), user=Depends(require_any_permissions('bookings.view', 'cashflow.view', 'reports.view'))):
    query = (db.query(ChannelPayoutBookingLink, ChannelPayout, Booking, BookingChannel).join(ChannelPayout, ChannelPayout.id == ChannelPayoutBookingLink.payout_id).join(Booking, Booking.id == ChannelPayoutBookingLink.booking_id).join(BookingChannel, BookingChannel.id == Booking.channel_id).filter(func.lower(ChannelPayout.status) == 'paid'))
    if channel_id: query = query.filter(Booking.channel_id == channel_id)
    out = []
    for link, payout, booking, channel in query.order_by(ChannelPayout.actual_payout_date.desc(), ChannelPayout.id.desc()).all():
        expected, original, actual = _money(payout.gross_amount), _normal_room_rate(db, booking), _money(payout.net_amount)
        difference = _deduction_amount(original, expected)
        out.append({'id': payout.id, 'booking_id': booking.id, 'booking_ref': payout.booking_ref or _booking_ref(booking), 'guest_name': booking.guest_name, 'room_name': booking.room_name, 'check_in': booking.check_in, 'check_out': booking.check_out, 'channel_id': channel.id, 'channel_name': channel.name, 'payout_reference': link.payout_reference, 'gross_amount': float(original), 'expected_amount': float(expected), 'actual_amount': float(actual), 'deduction_amount': float(difference), 'deduction_percent': _deduction_percent(original, expected), 'payout_variance_amount': float(_deduction_amount(expected, actual)), 'actual_payout_date': payout.actual_payout_date, 'status': payout.status, 'notes': payout.notes})
    return out


@router.post('/reconcile')
def reconcile_payout_batch(payload: PayoutReconcileBatch, db: Session = Depends(get_db), user=Depends(require_any_permissions('cashflow.money_in', 'cashflow.money_out', 'reports.view'))):
    channel = db.get(BookingChannel, payload.channel_id)
    if not channel or not channel.is_active: raise HTTPException(status_code=400, detail='Select an active booking channel.')
    allocated = sum((_money(item.actual_amount) for item in payload.items), Decimal('0'))
    if payload.amount_received is not None and abs(_money(payload.amount_received) - allocated) > CENT: raise HTTPException(status_code=400, detail='Allocated booking payouts must equal the bank payout amount before reconciliation.')
    try:
        results = []
        for item in payload.items:
            booking = db.get(Booking, item.booking_id)
            if not booking: raise ValueError(f'Booking {item.booking_id} was not found.')
            if booking.channel_id != channel.id: raise ValueError(f'Booking {item.booking_id} does not belong to {channel.name}.')
            if str(booking.status or '').strip().lower() in {'cancelled', 'canceled', 'no_show', 'noshow'}: raise ValueError(f'Booking {item.booking_id} is cancelled/no-show and cannot be reconciled.')
            existing_link = db.query(ChannelPayoutBookingLink).filter(ChannelPayoutBookingLink.booking_id == booking.id).first()
            existing = db.get(ChannelPayout, existing_link.payout_id) if existing_link else None
            if existing and str(existing.status or '').strip().lower() == 'paid': raise ValueError(f'Booking {item.booking_id} is already marked paid by its channel.')
            expected, actual = _money(item.expected_amount), _money(item.actual_amount)
            accounting_deduction = max(_deduction_amount(expected, actual), Decimal('0.00'))
            payout = existing or ChannelPayout()
            payout.channel_id, payout.channel, payout.booking_ref = channel.id, channel.name, _booking_ref(booking)
            payout.gross_amount, payout.commission_amount, payout.net_amount = expected, accounting_deduction, actual
            payout.actual_payout_date, payout.status = payload.actual_payout_date, 'paid'
            if payload.notes: payout.notes = payload.notes if not payout.notes else f'{payout.notes}\n{payload.notes}'.strip()
            db.add(payout); db.flush()
            if existing_link: existing_link.payout_reference = (payload.payout_reference or '').strip() or None
            else: existing_link = ChannelPayoutBookingLink(payout_id=payout.id, booking_id=booking.id, payout_reference=(payload.payout_reference or '').strip() or None)
            db.add(existing_link)
            if payload.auto_post_accounting:
                _post_commission_delta(db, payout, target_amount=float(accounting_deduction), tx_date=payload.actual_payout_date, payment_method=payload.payment_method, username=getattr(user, 'username', None))
                _post_settlement_delta(db, payout, target_amount=float(actual), tx_date=payload.actual_payout_date, username=getattr(user, 'username', None))
            results.append(payout.id)
        db.commit()
        return {'ok': True, 'channel_id': channel.id, 'channel': channel.name, 'booking_count': len(results), 'allocated_amount': float(allocated), 'payout_reference': (payload.payout_reference or '').strip() or None, 'payout_ids': results}
    except ValueError as exc:
        db.rollback(); raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        db.rollback(); raise
