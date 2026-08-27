from __future__ import annotations

import hashlib
import json

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.entities import FinancialAccount, MoneyTransaction, Payable
from app.models.mutation_idempotency import MutationIdempotency
from app.schemas.cashflow import PayableCreate, PayablePayPayload
from app.services.bir_service import ensure_date_unlocked
from app.services.cashflow_service import (
    _apply_money_effect,
    _as_float,
    _create_linked_record,
    _normalize,
    _safe_date,
    _serialize_money_transaction,
    _serialize_payable,
    _update_payable_balance,
)


class IdempotencyConflict(ValueError):
    pass


def _normalize_idempotency_key(value: str | None) -> str:
    key = (value or '').strip()
    if not key:
        raise ValueError('Idempotency-Key header is required for this mutation.')
    if len(key) < 8:
        raise ValueError('Idempotency-Key must contain at least 8 characters.')
    if len(key) > 255:
        raise ValueError('Idempotency-Key must not exceed 255 characters.')
    return key


def _fingerprint(payload: dict) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _reserve(
    db: Session,
    *,
    scope: str,
    idempotency_key: str | None,
    fingerprint: str,
) -> tuple[MutationIdempotency, bool]:
    key = _normalize_idempotency_key(idempotency_key)
    existing = (
        db.query(MutationIdempotency)
        .filter(
            MutationIdempotency.scope == scope,
            MutationIdempotency.idempotency_key == key,
        )
        .first()
    )
    if existing:
        if existing.request_fingerprint != fingerprint:
            raise IdempotencyConflict(
                'Idempotency-Key was already used with a different request.'
            )
        return existing, True

    row = MutationIdempotency(
        scope=scope,
        idempotency_key=key,
        request_fingerprint=fingerprint,
    )
    db.add(row)
    try:
        db.flush()
        return row, False
    except IntegrityError:
        # A concurrent request may have won the unique-key race. No business
        # mutation has occurred yet, so rolling back here cannot discard money
        # or liability state from this request.
        db.rollback()
        existing = (
            db.query(MutationIdempotency)
            .filter(
                MutationIdempotency.scope == scope,
                MutationIdempotency.idempotency_key == key,
            )
            .first()
        )
        if not existing:
            raise
        if existing.request_fingerprint != fingerprint:
            raise IdempotencyConflict(
                'Idempotency-Key was already used with a different request.'
            )
        return existing, True


def create_payable_idempotent(
    db: Session,
    payload: PayableCreate,
    idempotency_key: str | None,
) -> tuple[dict, bool]:
    payload_data = payload.model_dump(mode='json')
    fingerprint = _fingerprint(payload_data)
    reservation, replayed = _reserve(
        db,
        scope='payable:create',
        idempotency_key=idempotency_key,
        fingerprint=fingerprint,
    )

    if replayed:
        if reservation.resource_type != 'payable' or not reservation.resource_id:
            raise IdempotencyConflict(
                'Idempotent payable request is incomplete and cannot be replayed.'
            )
        existing = db.get(Payable, int(reservation.resource_id))
        if not existing:
            raise IdempotencyConflict(
                'Idempotent payable result no longer exists.'
            )
        return _serialize_payable(existing), True

    gross_amount = _as_float(payload.gross_amount)
    amount_paid = max(_as_float(payload.amount_paid), 0)
    if gross_amount <= 0:
        raise ValueError('gross_amount must be greater than zero.')
    if amount_paid > gross_amount:
        raise ValueError('amount_paid cannot exceed gross_amount.')

    row = Payable(
        source_type=(payload.source_type or '').strip() or None,
        source_id=payload.source_id,
        supplier_name=(payload.supplier_name or '').strip(),
        payable_type=(payload.payable_type or 'supplier_bill').strip() or 'supplier_bill',
        bill_date=_safe_date(payload.bill_date),
        due_date=(payload.due_date or '').strip() or None,
        gross_amount=gross_amount,
        amount_paid=amount_paid,
        status=(payload.status or 'open').strip() or 'open',
        posted_at=_safe_date(payload.bill_date),
        closed_at=None,
        notes=payload.notes,
        bir_include=bool(payload.bir_include),
    )
    db.add(row)
    db.flush()
    _update_payable_balance(db, row.id)
    db.flush()

    reservation.resource_type = 'payable'
    reservation.resource_id = row.id
    db.add(reservation)
    db.flush()
    return _serialize_payable(row), False


def pay_payable_idempotent(
    db: Session,
    payable_id: int,
    payload: PayablePayPayload,
    idempotency_key: str | None,
    *,
    username: str | None = None,
) -> tuple[dict, bool]:
    payload_data = {
        'payable_id': int(payable_id),
        'payload': payload.model_dump(mode='json'),
    }
    fingerprint = _fingerprint(payload_data)
    reservation, replayed = _reserve(
        db,
        scope='payable:payment',
        idempotency_key=idempotency_key,
        fingerprint=fingerprint,
    )

    payable = db.get(Payable, int(payable_id))
    if not payable:
        raise ValueError('Payable not found.')

    if replayed:
        if reservation.resource_type != 'money_transaction' or not reservation.resource_id:
            raise IdempotencyConflict(
                'Idempotent payable payment is incomplete and cannot be replayed.'
            )
        tx = db.get(MoneyTransaction, int(reservation.resource_id))
        if not tx:
            raise IdempotencyConflict(
                'Idempotent payable payment result no longer exists.'
            )
        return {
            'payable': _serialize_payable(payable),
            'transaction': _serialize_money_transaction(tx),
        }, True

    if float(payable.balance_due or 0) <= 0:
        raise ValueError('Payable is already settled.')

    amount = _as_float(payload.amount)
    if amount <= 0:
        raise ValueError('Payment amount must be greater than zero.')
    if amount > float(payable.balance_due or 0):
        raise ValueError('Payment amount cannot exceed payable balance.')

    account = db.get(FinancialAccount, int(payload.financial_account_id))
    if not account:
        raise ValueError('financial_account_id not found.')

    tx_date = _safe_date(payload.payment_date)
    ensure_date_unlocked(
        db,
        tx_date,
        scope='bir',
        action='create cashflow transaction in locked period',
    )

    tx = MoneyTransaction(
        transaction_date=tx_date,
        direction='out',
        financial_account_id=account.id,
        module=(payload.module or 'finance').strip() or 'finance',
        category=(payload.category or '').strip() or None,
        subcategory=(payload.subcategory or '').strip() or None,
        level3_item=(payload.level3_item or '').strip() or None,
        amount=amount,
        payment_method=(payload.payment_method or '').strip() or 'cash',
        reference_no=(payload.reference_no or '').strip() or None,
        counterparty_name=payable.supplier_name,
        notes=payload.notes,
        linked_record_type=(payable.source_type or '').strip() or None,
        linked_record_id=payable.source_id,
        receivable_id=None,
        payable_id=payable.id,
        bir_include=bool(payable.bir_include),
        journal_entry_id=None,
        status='posted',
        reversed_from_id=None,
        is_reversed=False,
        posted_at=tx_date,
        created_by=username,
        approved_by=username,
        external_source='payable_payment',
        external_id=_normalize_idempotency_key(idempotency_key),
    )
    db.add(tx)
    db.flush()
    _apply_money_effect(db, tx, allow_overdraw=False)

    if bool(payload.auto_post_accounting):
        _, journal_id = _create_linked_record(
            db,
            direction='out',
            account=account,
            module=payload.module or 'finance',
            category=payload.category,
            subcategory=payload.subcategory,
            level3_item=payload.level3_item,
            amount=amount,
            payment_method=payload.payment_method,
            counterparty_name=payable.supplier_name,
            transaction_date=tx_date,
            reference_no=payload.reference_no,
            notes=payload.notes,
            bir_include=bool(payable.bir_include),
            created_by=username,
        )
        tx.journal_entry_id = journal_id
        db.add(tx)

    reservation.resource_type = 'money_transaction'
    reservation.resource_id = tx.id
    db.add(reservation)
    db.flush()

    payable = db.get(Payable, int(payable_id))
    return {
        'payable': _serialize_payable(payable),
        'transaction': _serialize_money_transaction(tx),
    }, False
