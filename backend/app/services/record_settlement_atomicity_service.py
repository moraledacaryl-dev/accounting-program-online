"""Atomic, idempotent settlement evidence for generic approved credit records.

These RecordSettlement rows are evidence/aging adjustments, NOT automatic cash
transactions or journal postings. Posting funds happens via the owning workflow.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.business_clock import business_today
from app.models.entities import Record, RecordSettlement
from app.schemas.common import RecordSettlementCreate
from app.services.bir_service import ensure_date_unlocked
from app.services.journal_integrity_service import money
from app.services.payable_atomicity_service import (
    IdempotencyConflict, _fingerprint, _reserve,
)


class SettlementConflict(ValueError):
    """A financial state or payment-reference conflict (HTTP 409)."""


def _settlement_date(value: str | None) -> str:
    raw = (value or '').strip() or business_today()
    try:
        if date.fromisoformat(raw).isoformat() != raw:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError('Settlement date must be valid YYYY-MM-DD.') from None
    return raw


def _record_balance(db: Session, record: Record, *, through_id: int | None = None):
    query = db.query(func.coalesce(func.sum(RecordSettlement.amount), 0)).filter(
        RecordSettlement.record_id == record.id,
    )
    if through_id is not None:
        query = query.filter(RecordSettlement.id <= through_id)
    settled = money(query.scalar() or 0)
    return money(abs(money(record.amount)) - settled)


def create_record_settlement_idempotent(
    db: Session,
    payload: RecordSettlementCreate,
    *,
    idempotency_key: str | None,
    username: str | None = None,
) -> tuple[RecordSettlement, Decimal, Decimal, bool]:
    """Commit the evidence and its idempotency reservation in one transaction.

    Locking the parent Record serializes concurrent payments even when they use
    different keys. A PostgreSQL unique constraint serializes same-key retries.
    """
    fingerprint = _fingerprint(payload.model_dump(mode='json'))
    try:
        reservation, replayed = _reserve(
            db,
            scope=f'record_settlement:create:{int(payload.record_id)}',
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
        )
        if replayed:
            if reservation.resource_type != 'record_settlement' or not reservation.resource_id:
                raise IdempotencyConflict('Settlement request has no completed result to replay.')
            row = db.get(RecordSettlement, int(reservation.resource_id))
            if row is None or row.record_id != int(payload.record_id):
                raise IdempotencyConflict('Idempotent settlement result no longer exists.')
            record = db.get(Record, row.record_id)
            if record is None:
                raise IdempotencyConflict('Source record for settlement no longer exists.')
            after = _record_balance(db, record, through_id=row.id)
            before = money(after + money(row.amount))
            return row, before, after, True

        record = (
            db.query(Record)
            .filter(Record.id == int(payload.record_id))
            .populate_existing()
            .with_for_update()
            .one_or_none()
        )
        if record is None:
            raise ValueError('Record not found.')
        if record.workflow_status != 'approved':
            raise ValueError('Only approved records can be settled.')
        if (record.payment_method or '').strip().lower() not in {'on_account', 'credit'}:
            raise ValueError('Record is not marked as on-account/credit.')
        if (record.direction or '').strip().lower() not in {'income', 'expense', 'asset', 'liability'}:
            raise ValueError('This record direction cannot be settled.')

        amount = money(payload.amount)
        if amount <= 0:
            raise ValueError('Settlement amount must be greater than zero.')
        if Decimal(str(payload.amount)) != amount:
            raise ValueError('Settlement amount supports at most four decimal places.')
        settlement_date = _settlement_date(payload.settlement_date)
        ensure_date_unlocked(db, settlement_date, scope='bir', action='create settlement')

        ref = (payload.reference_no or '').strip()
        if ref:
            already_used = db.query(RecordSettlement.id).filter(
                RecordSettlement.record_id == record.id,
                func.lower(func.trim(RecordSettlement.reference_no)) == ref.lower(),
            ).first()
            if already_used:
                raise SettlementConflict('Payment reference already exists for this record.')

        before = _record_balance(db, record)
        if before <= 0:
            raise SettlementConflict('Record is already fully settled or over-settled.')
        if amount > before:
            raise SettlementConflict(f'Settlement exceeds outstanding amount ({before}).')

        row = RecordSettlement(
            record_id=record.id,
            settlement_date=settlement_date,
            amount=amount,
            payment_method=payload.payment_method or record.payment_method,
            reference_no=ref or None,
            notes=payload.notes,
            created_by=username,
        )
        db.add(row)
        db.flush()
        reservation.resource_type = 'record_settlement'
        reservation.resource_id = row.id
        after = money(before - amount)
        db.commit()
        db.refresh(row)
        return row, before, after, False
    except Exception:
        db.rollback()
        raise
