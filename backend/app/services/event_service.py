from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    EventBooking,
    EventBookingLine,
    EventPayment,
    FinancialAccount,
    JournalEntry,
    JournalLine,
    MoneyTransaction,
    Receivable,
    Record,
)
from app.schemas.cashflow import ReceivableCollectPayload, ReceivableCreate
from app.schemas.events import EventActionPayload, EventBookingPayload, EventBookingUpdate, EventLinePayload, EventPaymentPayload
from app.services.cashflow_service import _update_receivable_balance, collect_receivable, create_receivable
from app.services.restaurant_service import create_approved_record


EVENT_STATUSES = {'draft', 'quoted', 'confirmed', 'completed', 'cancelled'}
EDITABLE_DIRECT_STATUSES = {'draft', 'quoted'}


def _today() -> str:
    return datetime.utcnow().strftime('%Y-%m-%d')


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def _norm(value: str | None) -> str:
    return (value or '').strip().lower()


def _clean(value: str | None) -> str | None:
    text = (value or '').strip()
    return text or None


def _as_float(value, default: float = 0.0) -> float:
    try:
        return float(value if value is not None else default)
    except Exception:
        return float(default)


def _round(value) -> float:
    return round(float(value or 0), 4)


def _event_query(db: Session):
    return db.query(EventBooking).options(
        selectinload(EventBooking.lines),
        selectinload(EventBooking.payments).selectinload(EventPayment.financial_account),
        selectinload(EventBooking.payments).selectinload(EventPayment.money_transaction),
        selectinload(EventBooking.receivable).selectinload(Receivable.adjustments),
        selectinload(EventBooking.record),
    )


def _line_total(payload: EventLinePayload) -> float:
    qty = _as_float(payload.quantity, 1)
    unit_price = _as_float(payload.unit_price)
    total = _as_float(payload.total_amount, qty * unit_price)
    if _norm(payload.line_type) == 'discount':
        total = -abs(total)
    return _round(total)


def _apply_lines(event: EventBooking, lines: list[EventLinePayload]):
    event.lines = [
        EventBookingLine(
            line_type=_norm(line.line_type) or 'package',
            description=(line.description or '').strip(),
            quantity=_as_float(line.quantity, 1),
            unit_price=_as_float(line.unit_price),
            total_amount=_line_total(line),
            notes=line.notes,
            sort_order=int(line.sort_order or index),
        )
        for index, line in enumerate(lines or [])
        if (line.description or '').strip()
    ]


def _recompute_totals(db: Session, event: EventBooking):
    subtotal = 0.0
    discount_lines = 0.0
    for line in event.lines or []:
        qty = _as_float(line.quantity, 1)
        total = _as_float(line.total_amount, qty * _as_float(line.unit_price))
        if _norm(line.line_type) == 'discount':
            total = -abs(total)
        line.total_amount = _round(total)
        if total < 0:
            discount_lines += abs(total)
        else:
            subtotal += total

    explicit_discount = max(_as_float(event.discount_amount), 0)
    event.subtotal_amount = _round(subtotal)
    event.discount_amount = _round(explicit_discount)
    event.tax_amount = _round(max(_as_float(event.tax_amount), 0))
    event.total_amount = _round(max(subtotal - discount_lines - explicit_discount + event.tax_amount, 0))

    receivable = db.get(Receivable, int(event.receivable_id)) if event.receivable_id else None
    if receivable:
        event.deposit_paid = _round(receivable.amount_collected)
        event.balance_due = _round(receivable.balance_due)
    else:
        payment_total = db.query(func.coalesce(func.sum(EventPayment.amount), 0)).filter(
            EventPayment.event_booking_id == event.id
        ).scalar() if event.id else 0
        event.deposit_paid = _round(payment_total)
        event.balance_due = _round(max(event.total_amount - event.deposit_paid, 0))

    db.add(event)


def _serialize_line(row: EventBookingLine) -> dict:
    return {
        'id': row.id,
        'line_type': row.line_type,
        'description': row.description,
        'quantity': float(row.quantity or 0),
        'unit_price': float(row.unit_price or 0),
        'total_amount': float(row.total_amount or 0),
        'notes': row.notes,
        'sort_order': int(row.sort_order or 0),
    }


def _serialize_payment(row: EventPayment) -> dict:
    account = row.financial_account
    tx = row.money_transaction
    return {
        'id': row.id,
        'payment_date': row.payment_date,
        'amount': float(row.amount or 0),
        'payment_method': row.payment_method,
        'financial_account_id': row.financial_account_id,
        'financial_account_name': account.name if account else None,
        'reference_no': row.reference_no,
        'notes': row.notes,
        'money_transaction_id': row.money_transaction_id,
        'journal_entry_id': tx.journal_entry_id if tx else None,
        'created_by': row.created_by,
        'created_at': row.created_at.isoformat() if row.created_at else None,
    }


def _serialize_event(row: EventBooking) -> dict:
    receivable = row.receivable
    record = row.record
    paid = float(row.deposit_paid or 0)
    total = float(row.total_amount or 0)
    return {
        'id': row.id,
        'event_no': row.event_no,
        'event_name': row.event_name,
        'client_name': row.client_name,
        'contact_name': row.contact_name,
        'contact_phone': row.contact_phone,
        'contact_email': row.contact_email,
        'event_type': row.event_type,
        'event_date': row.event_date,
        'start_time': row.start_time,
        'end_time': row.end_time,
        'venue': row.venue,
        'guest_count': int(row.guest_count or 0),
        'package_name': row.package_name,
        'status': row.status,
        'quote_sent_at': row.quote_sent_at,
        'confirmed_at': row.confirmed_at,
        'completed_at': row.completed_at,
        'cancelled_at': row.cancelled_at,
        'deposit_required': float(row.deposit_required or 0),
        'deposit_due_date': row.deposit_due_date,
        'subtotal_amount': float(row.subtotal_amount or 0),
        'discount_amount': float(row.discount_amount or 0),
        'tax_amount': float(row.tax_amount or 0),
        'total_amount': total,
        'deposit_paid': paid,
        'balance_due': float(row.balance_due or 0),
        'payment_percent': round((paid / total * 100), 2) if total > 0 else 0,
        'receivable_id': row.receivable_id,
        'receivable_status': receivable.status if receivable else None,
        'record_id': row.record_id,
        'record_reference': record.document_ref if record else None,
        'notes': row.notes,
        'created_by': row.created_by,
        'approved_by': row.approved_by,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
        'lines': [_serialize_line(line) for line in sorted(row.lines or [], key=lambda x: (x.sort_order, x.id or 0))],
        'payments': [_serialize_payment(payment) for payment in sorted(row.payments or [], key=lambda x: (x.payment_date or '', x.id or 0))],
    }


def generate_event_no(db: Session) -> str:
    prefix = f'EVT-{datetime.utcnow().strftime("%Y%m%d")}'
    existing = (
        db.query(EventBooking.event_no)
        .filter(EventBooking.event_no.like(f'{prefix}-%'))
        .order_by(EventBooking.event_no.desc())
        .first()
    )
    next_seq = 1
    if existing and existing[0]:
        try:
            next_seq = int(str(existing[0]).rsplit('-', 1)[-1]) + 1
        except Exception:
            next_seq = int(db.query(func.count(EventBooking.id)).filter(EventBooking.event_no.like(f'{prefix}-%')).scalar() or 0) + 1
    return f'{prefix}-{next_seq:03d}'


def list_events(
    db: Session,
    *,
    status: str | None = None,
    q: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 300,
):
    query = _event_query(db)
    if status:
        query = query.filter(EventBooking.status == _norm(status))
    if start_date:
        query = query.filter(EventBooking.event_date >= start_date)
    if end_date:
        query = query.filter(EventBooking.event_date <= end_date)
    if q:
        like_q = f'%{q.strip()}%'
        query = query.filter(
            or_(
                EventBooking.event_no.like(like_q),
                EventBooking.event_name.like(like_q),
                EventBooking.client_name.like(like_q),
                EventBooking.contact_name.like(like_q),
                EventBooking.venue.like(like_q),
            )
        )
    rows = query.order_by(EventBooking.event_date.desc(), EventBooking.id.desc()).limit(max(1, min(int(limit or 300), 1000))).all()
    for row in rows:
        _recompute_totals(db, row)
    db.flush()
    return [_serialize_event(row) for row in rows]


def get_event(db: Session, event_id: int) -> dict:
    row = _event_query(db).filter(EventBooking.id == int(event_id)).first()
    if not row:
        raise ValueError('Event not found.')
    _recompute_totals(db, row)
    db.flush()
    return _serialize_event(row)


def create_event(db: Session, payload: EventBookingPayload, username: str | None = None):
    event_name = (payload.event_name or '').strip()
    client_name = (payload.client_name or '').strip()
    if not event_name:
        raise ValueError('Event name is required.')
    if not client_name:
        raise ValueError('Client name is required.')

    requested_no = (payload.event_no or '').strip()
    if requested_no and db.query(EventBooking).filter(EventBooking.event_no == requested_no).first():
        raise ValueError('Event number already exists.')

    status = _norm(payload.status)
    if status not in EDITABLE_DIRECT_STATUSES:
        status = 'draft'

    event = EventBooking(
        event_no=requested_no or generate_event_no(db),
        event_name=event_name,
        client_name=client_name,
        contact_name=_clean(payload.contact_name),
        contact_phone=_clean(payload.contact_phone),
        contact_email=_clean(payload.contact_email),
        event_type=_clean(payload.event_type),
        event_date=_clean(payload.event_date),
        start_time=_clean(payload.start_time),
        end_time=_clean(payload.end_time),
        venue=_clean(payload.venue),
        guest_count=max(int(payload.guest_count or 0), 0),
        package_name=_clean(payload.package_name),
        status=status,
        quote_sent_at=_clean(payload.quote_sent_at) or (_today() if status == 'quoted' else None),
        deposit_required=max(_as_float(payload.deposit_required), 0),
        deposit_due_date=_clean(payload.deposit_due_date),
        discount_amount=max(_as_float(payload.discount_amount), 0),
        tax_amount=max(_as_float(payload.tax_amount), 0),
        notes=payload.notes,
        created_by=username,
    )
    _apply_lines(event, payload.lines or [])
    db.add(event)
    db.flush()
    _recompute_totals(db, event)
    db.commit()
    return get_event(db, event.id)


def _sync_event_revenue_journal(db: Session, record: Record):
    reference_no = f'REC-{record.id}'
    journal = db.query(JournalEntry).filter(JournalEntry.reference_no == reference_no).first()
    if not journal:
        journal = JournalEntry(
            entry_date=record.transaction_date,
            reference_no=reference_no,
            description=record.name or 'Event booking',
            source_module='events',
            status='posted',
        )
        db.add(journal)
        db.flush()
    else:
        journal.entry_date = record.transaction_date
        journal.description = record.name or 'Event booking'
        journal.source_module = 'events'
        journal.status = 'posted'
        db.add(journal)
        db.flush()

    db.query(JournalLine).filter(JournalLine.journal_entry_id == journal.id).delete()
    amount = _round(abs(record.amount or 0))
    if amount > 0:
        db.add(JournalLine(journal_entry_id=journal.id, account_code='1100', account_name='Accounts Receivable', debit=amount, credit=0, memo=record.name))
        db.add(JournalLine(journal_entry_id=journal.id, account_code='4014', account_name='Events Revenue', debit=0, credit=amount, memo=record.name))
    db.flush()
    return journal


def _sync_event_record(db: Session, event: EventBooking, username: str | None):
    if not event.record_id:
        record = create_approved_record(
            db,
            module_slug='events',
            direction='income',
            amount=event.total_amount,
            name=event.event_name,
            transaction_date=event.event_date or _today(),
            payment_method='on_account',
            counterparty=event.client_name,
            notes=event.notes,
            document_ref=event.event_no,
            created_by=username,
            preferred_paths=(
                ('Revenue', 'Catering', 'Food Package'),
                ('Revenue', 'Venue Rental', 'Hall Rental'),
                ('Receivables', 'Event Balance', 'Remaining Balance'),
            ),
        )
        event.record_id = record.id
        db.add(event)
        db.flush()
        _sync_event_revenue_journal(db, record)
        return record

    record = db.get(Record, int(event.record_id))
    if not record:
        event.record_id = None
        db.add(event)
        db.flush()
        return _sync_event_record(db, event, username)

    record.module_slug = 'events'
    record.module_name = 'Events'
    record.direction = 'income'
    record.name = event.event_name
    record.amount = _round(event.total_amount)
    record.transaction_date = event.event_date or record.transaction_date or _today()
    record.payment_method = 'on_account'
    record.counterparty = event.client_name
    record.document_ref = event.event_no
    record.workflow_status = 'approved'
    record.notes = event.notes
    record.approved_by = record.approved_by or username
    db.add(record)
    db.flush()
    _sync_event_revenue_journal(db, record)
    return record


def _sync_event_receivable(db: Session, event: EventBooking):
    if event.total_amount <= 0:
        raise ValueError('Event total must be greater than zero before confirming.')

    if not event.receivable_id:
        receivable_data = create_receivable(
            db,
            ReceivableCreate(
                source_type='event',
                source_id=event.id,
                counterparty_name=event.client_name,
                receivable_type='event_balance',
                transaction_date=event.event_date or _today(),
                due_date=event.deposit_due_date or event.event_date,
                gross_amount=event.total_amount,
                amount_collected=0,
                status='open',
                notes=f'{event.event_no} · {event.event_name}',
                bir_include=True,
                external_source='event_workflow',
                external_id=event.event_no,
            ),
        )
        event = db.get(EventBooking, int(event.id))
        event.receivable_id = int(receivable_data['id'])
        db.add(event)
        db.flush()

    receivable = db.get(Receivable, int(event.receivable_id))
    if not receivable:
        event.receivable_id = None
        db.add(event)
        db.flush()
        return _sync_event_receivable(db, event)

    if float(receivable.amount_collected or 0) > float(event.total_amount or 0) + 0.0001:
        raise ValueError('Event total cannot be lower than the amount already collected.')

    receivable.source_type = 'event'
    receivable.source_id = event.id
    receivable.counterparty_name = event.client_name
    receivable.receivable_type = 'event_balance'
    receivable.transaction_date = event.event_date or receivable.transaction_date or _today()
    receivable.due_date = event.deposit_due_date or event.event_date or receivable.due_date
    receivable.gross_amount = _round(event.total_amount)
    receivable.notes = f'{event.event_no} · {event.event_name}'
    receivable.bir_include = True
    receivable.external_source = receivable.external_source or 'event_workflow'
    receivable.external_id = receivable.external_id or event.event_no
    db.add(receivable)
    _update_receivable_balance(db, receivable.id)
    db.flush()
    event.deposit_paid = _round(receivable.amount_collected)
    event.balance_due = _round(receivable.balance_due)
    db.add(event)
    return receivable


def _sync_financial_links(db: Session, event: EventBooking, username: str | None):
    _recompute_totals(db, event)
    _sync_event_record(db, event, username)
    receivable = _sync_event_receivable(db, event)
    _recompute_totals(db, event)
    return receivable


def update_event(db: Session, event_id: int, payload: EventBookingUpdate, username: str | None = None):
    event = _event_query(db).filter(EventBooking.id == int(event_id)).first()
    if not event:
        raise ValueError('Event not found.')
    if _norm(event.status) == 'cancelled':
        raise ValueError('Cancelled events cannot be edited.')

    data = payload.model_dump(exclude_unset=True)
    if 'event_no' in data and data.get('event_no'):
        next_no = str(data['event_no']).strip()
        duplicate = db.query(EventBooking).filter(EventBooking.event_no == next_no, EventBooking.id != event.id).first()
        if duplicate:
            raise ValueError('Event number already exists.')
        event.event_no = next_no

    for field in (
        'event_name', 'client_name', 'contact_name', 'contact_phone', 'contact_email', 'event_type',
        'event_date', 'start_time', 'end_time', 'venue', 'package_name', 'quote_sent_at',
        'deposit_due_date', 'notes',
    ):
        if field in data:
            value = data.get(field)
            setattr(event, field, (value.strip() if isinstance(value, str) else value) or None)

    if 'event_name' in data and not (event.event_name or '').strip():
        raise ValueError('Event name is required.')
    if 'client_name' in data and not (event.client_name or '').strip():
        raise ValueError('Client name is required.')
    if 'guest_count' in data and data.get('guest_count') is not None:
        event.guest_count = max(int(data.get('guest_count') or 0), 0)
    if 'deposit_required' in data and data.get('deposit_required') is not None:
        event.deposit_required = max(_as_float(data.get('deposit_required')), 0)
    if 'discount_amount' in data and data.get('discount_amount') is not None:
        event.discount_amount = max(_as_float(data.get('discount_amount')), 0)
    if 'tax_amount' in data and data.get('tax_amount') is not None:
        event.tax_amount = max(_as_float(data.get('tax_amount')), 0)
    if 'status' in data and data.get('status'):
        next_status = _norm(data.get('status'))
        if next_status in EDITABLE_DIRECT_STATUSES and _norm(event.status) in EDITABLE_DIRECT_STATUSES:
            event.status = next_status
            if next_status == 'quoted' and not event.quote_sent_at:
                event.quote_sent_at = _today()

    if data.get('lines') is not None:
        _apply_lines(event, data.get('lines') or [])

    _recompute_totals(db, event)
    if _norm(event.status) in {'confirmed', 'completed'}:
        _sync_financial_links(db, event, username)
    db.commit()
    return get_event(db, event.id)


def confirm_event(db: Session, event_id: int, payload: EventActionPayload, username: str | None = None):
    event = _event_query(db).filter(EventBooking.id == int(event_id)).first()
    if not event:
        raise ValueError('Event not found.')
    if _norm(event.status) == 'cancelled':
        raise ValueError('Cancelled events cannot be confirmed.')
    if _norm(event.status) == 'completed':
        raise ValueError('Completed events are already past confirmation.')
    _recompute_totals(db, event)
    event.status = 'confirmed'
    event.confirmed_at = event.confirmed_at or payload.action_date or _today()
    event.approved_by = username
    if payload.note:
        event.notes = f"{event.notes or ''}\nConfirmed: {payload.note}".strip()
    _sync_financial_links(db, event, username)
    db.commit()
    return get_event(db, event.id)


def complete_event(db: Session, event_id: int, payload: EventActionPayload, username: str | None = None):
    event = _event_query(db).filter(EventBooking.id == int(event_id)).first()
    if not event:
        raise ValueError('Event not found.')
    if _norm(event.status) == 'cancelled':
        raise ValueError('Cancelled events cannot be completed.')
    if _norm(event.status) == 'draft':
        raise ValueError('Confirm the event before completing it.')
    _sync_financial_links(db, event, username)
    event.status = 'completed'
    event.completed_at = event.completed_at or payload.action_date or _today()
    if payload.note:
        event.notes = f"{event.notes or ''}\nCompleted: {payload.note}".strip()
    db.add(event)
    db.commit()
    return get_event(db, event.id)


def cancel_event(db: Session, event_id: int, payload: EventActionPayload, username: str | None = None):
    event = _event_query(db).filter(EventBooking.id == int(event_id)).first()
    if not event:
        raise ValueError('Event not found.')
    if _norm(event.status) == 'completed':
        raise ValueError('Completed events cannot be cancelled.')
    receivable = db.get(Receivable, int(event.receivable_id)) if event.receivable_id else None
    if (receivable and float(receivable.amount_collected or 0) > 0) or (event.payments or []):
        raise ValueError('Paid events cannot be cancelled here. Record the refund/reversal first, then close the event.')

    event.status = 'cancelled'
    event.cancelled_at = event.cancelled_at or payload.action_date or _today()
    event.balance_due = 0
    event.deposit_paid = 0
    if payload.note:
        event.notes = f"{event.notes or ''}\nCancelled: {payload.note}".strip()

    if receivable:
        receivable.gross_amount = 0
        receivable.amount_collected = 0
        receivable.balance_due = 0
        receivable.status = 'cancelled'
        receivable.closed_at = event.cancelled_at
        db.add(receivable)

    record = db.get(Record, int(event.record_id)) if event.record_id else None
    if record:
        record.amount = 0
        record.notes = f"{record.notes or ''}\nCancelled event {event.event_no}".strip()
        db.add(record)
        _sync_event_revenue_journal(db, record)

    db.add(event)
    db.commit()
    return get_event(db, event.id)


def _payment_account_line(account: FinancialAccount) -> tuple[str, str]:
    account_type = _norm(account.account_type)
    if account_type == 'bank':
        return '1020', 'Bank'
    if account_type == 'ewallet':
        return '1010', 'GCash'
    return '1000', 'Cash on Hand'


def _post_event_payment_journal(db: Session, event: EventBooking, payment: EventPayment, account: FinancialAccount):
    tx = db.get(MoneyTransaction, int(payment.money_transaction_id)) if payment.money_transaction_id else None
    reference_no = f'EVTPAY-{payment.id}'
    journal = db.query(JournalEntry).filter(JournalEntry.reference_no == reference_no).first()
    if not journal:
        journal = JournalEntry(
            entry_date=payment.payment_date or _today(),
            reference_no=reference_no,
            description=f'Event payment {event.event_no}',
            source_module='events',
            status='posted',
        )
        db.add(journal)
        db.flush()
    db.query(JournalLine).filter(JournalLine.journal_entry_id == journal.id).delete()
    cash_code, cash_name = _payment_account_line(account)
    amount = _round(payment.amount)
    db.add(JournalLine(journal_entry_id=journal.id, account_code=cash_code, account_name=cash_name, debit=amount, credit=0, memo=event.event_name))
    db.add(JournalLine(journal_entry_id=journal.id, account_code='1100', account_name='Accounts Receivable', debit=0, credit=amount, memo=event.event_name))
    if tx:
        tx.journal_entry_id = journal.id
        db.add(tx)
    db.flush()
    return journal


def record_event_payment(db: Session, event_id: int, payload: EventPaymentPayload, username: str | None = None):
    event = _event_query(db).filter(EventBooking.id == int(event_id)).first()
    if not event:
        raise ValueError('Event not found.')
    if _norm(event.status) == 'cancelled':
        raise ValueError('Cancelled events cannot receive payments.')

    amount = _as_float(payload.amount)
    if amount <= 0:
        raise ValueError('Payment amount must be greater than zero.')

    account = db.get(FinancialAccount, int(payload.financial_account_id))
    if not account:
        raise ValueError('Financial account not found.')

    if _norm(event.status) in {'draft', 'quoted'}:
        confirm_event(db, event.id, EventActionPayload(action_date=payload.payment_date or _today(), note='Auto-confirmed by event payment.'), username=username)
        event = _event_query(db).filter(EventBooking.id == int(event_id)).first()
    else:
        _sync_financial_links(db, event, username)
        db.commit()
        event = _event_query(db).filter(EventBooking.id == int(event_id)).first()

    receivable = db.get(Receivable, int(event.receivable_id)) if event.receivable_id else None
    if not receivable:
        raise ValueError('Event receivable was not created.')
    if amount > float(receivable.balance_due or 0) + 0.0001:
        raise ValueError('Payment cannot exceed the event balance due.')

    result = collect_receivable(
        db,
        receivable.id,
        ReceivableCollectPayload(
            amount=amount,
            collection_date=payload.payment_date or _today(),
            financial_account_id=account.id,
            payment_method=payload.payment_method or 'cash',
            reference_no=payload.reference_no,
            notes=payload.notes,
            module='events',
            category='Event Payments',
            subcategory='Deposits & Balances',
            level3_item=event.event_name or 'Event Payment',
            auto_post_accounting=False,
        ),
        username=username,
    )
    tx_data = result.get('transaction') or {}
    event = _event_query(db).filter(EventBooking.id == int(event_id)).first()
    payment = EventPayment(
        event_booking_id=event.id,
        payment_date=payload.payment_date or _today(),
        amount=amount,
        payment_method=payload.payment_method or 'cash',
        financial_account_id=account.id,
        reference_no=payload.reference_no,
        notes=payload.notes,
        money_transaction_id=tx_data.get('id'),
        created_by=username,
    )
    db.add(payment)
    db.flush()
    _post_event_payment_journal(db, event, payment, account)
    receivable = db.get(Receivable, int(event.receivable_id))
    event.deposit_paid = _round(receivable.amount_collected if receivable else event.deposit_paid)
    event.balance_due = _round(receivable.balance_due if receivable else max(event.total_amount - event.deposit_paid, 0))
    db.add(event)
    db.commit()
    return get_event(db, event.id)
