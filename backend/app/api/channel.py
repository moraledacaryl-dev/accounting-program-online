from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload
from app.db.database import get_db
from app.models.entities import BookingChannel, ChannelPayout, ChannelPayoutAccountingLink, Record
from app.schemas.common import ChannelPayoutCreate, ChannelPayoutSettle, ChannelPayoutUpdate
from app.api.deps import require_any_permissions
from app.services.restaurant_service import create_approved_record

router = APIRouter()


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


def _serialize_payout(obj: ChannelPayout) -> dict:
    channel_obj = getattr(obj, 'channel_obj', None)
    links = getattr(obj, 'accounting_links', None) or []
    return {
        'id': obj.id,
        'channel_id': obj.channel_id,
        'channel': obj.channel,
        'channel_code': channel_obj.code if channel_obj else None,
        'channel_display_name': channel_obj.name if channel_obj else obj.channel,
        'booking_ref': obj.booking_ref,
        'gross_amount': obj.gross_amount,
        'commission_amount': obj.commission_amount,
        'net_amount': obj.net_amount,
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
    return [_serialize_payout(x) for x in rows]


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
    legacy_channels = [
        label
        for (label,) in legacy_labels
        if str(label or '').strip().lower() not in setup_keys
    ]
    return {
        'channels': setup_channel_rows,
        'legacy_channels': legacy_channels,
    }


@router.post('/payouts')
def add_payout(
    payload: ChannelPayoutCreate,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('cashflow.money_in', 'cashflow.money_out', 'reports.view')),
):
    try:
        payload_data = payload.model_dump(exclude={'payment_method', 'auto_post_accounting'})
        resolved_channel_id, resolved_channel_name = _resolve_payout_channel(
            db,
            payload.channel_id,
            payload.channel,
        )
        payload_data['channel_id'] = resolved_channel_id
        payload_data['channel'] = resolved_channel_name
        obj = ChannelPayout(**payload_data)
        db.add(obj)
        db.flush()

        if payload.auto_post_accounting:
            tx_date = payload.actual_payout_date or payload.expected_payout_date
            _post_commission_delta(
                db,
                obj,
                target_amount=float(obj.commission_amount or 0),
                tx_date=tx_date,
                payment_method=payload.payment_method,
                username=getattr(user, 'username', None),
            )
            if (obj.status or '').strip().lower() == 'paid':
                _post_settlement_delta(
                    db,
                    obj,
                    target_amount=float(obj.net_amount or 0),
                    tx_date=obj.actual_payout_date or tx_date,
                    username=getattr(user, 'username', None),
                )

        db.commit()
        obj = _get_payout_with_links(db, obj.id)
        return _serialize_payout(obj)
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
            resolved_channel_id, resolved_channel_name = _resolve_payout_channel(
                db,
                data.get('channel_id', obj.channel_id),
                data.get('channel', obj.channel),
            )
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
            _post_commission_delta(
                db,
                obj,
                target_amount=float(obj.commission_amount or 0),
                tx_date=tx_date,
                payment_method=payload.payment_method,
                username=getattr(user, 'username', None),
            )
            if (obj.status or '').strip().lower() == 'paid':
                _post_settlement_delta(
                    db,
                    obj,
                    target_amount=float(obj.net_amount or 0),
                    tx_date=obj.actual_payout_date or tx_date,
                    username=getattr(user, 'username', None),
                )

        db.commit()
        obj = _get_payout_with_links(db, obj.id)
        return _serialize_payout(obj)
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
            _post_settlement_delta(
                db,
                obj,
                target_amount=float(obj.net_amount or 0),
                tx_date=obj.actual_payout_date or obj.expected_payout_date,
                username=getattr(user, 'username', None),
            )

        db.commit()
        obj = _get_payout_with_links(db, obj.id)
        return _serialize_payout(obj)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
