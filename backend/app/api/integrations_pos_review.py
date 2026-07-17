from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.settings import settings
from app.db.database import get_db
from app.models.entities import User
from app.schemas.integration_review import IntegrationReviewCreate
from app.services.integration_review_service import create_review_item

router = APIRouter()


def require_pos_integration_user(user: User = Depends(get_current_user)) -> User:
    if user.username != settings.integration_username:
        raise HTTPException(status_code=403, detail='POS compatibility intake requires the integration account')
    return user


def _amount(payload: dict[str, Any], *keys: str) -> float:
    for key in keys:
        value = payload.get(key)
        try:
            amount = round(float(value or 0), 2)
        except (TypeError, ValueError):
            continue
        if amount != 0:
            return abs(amount)
    return 0.0


def _event_id(kind: str, payload: dict[str, Any]) -> str:
    candidates = (
        payload.get('external_id'),
        payload.get('reference_no'),
        payload.get('order_no'),
        payload.get('posting_uuid'),
        payload.get('source_id'),
        payload.get('shift_name'),
    )
    identity = next((str(value) for value in candidates if value not in (None, '')), None)
    if not identity:
        identity = json.dumps(payload, sort_keys=True, default=str, separators=(',', ':'))
    return f'pos:{kind}:{identity}'


def _create_review(
    db: Session,
    *,
    kind: str,
    payload: dict[str, Any],
    effect: str,
    amount: float = 0,
    account_id: int | None = None,
    links: dict[str, Any] | None = None,
):
    source_event_id = _event_id(kind, payload)
    source_id = payload.get('linked_record_id') or payload.get('source_id') or payload.get('external_id') or payload.get('order_no')
    review = IntegrationReviewCreate(
        source_app='pos',
        source_event_id=source_event_id,
        source_entity_type=kind,
        source_entity_id=str(source_id) if source_id not in (None, '') else None,
        source_revision=1,
        financial_effect=effect,
        amount=amount,
        currency=str(payload.get('currency') or 'PHP').upper(),
        proposed_account_id=account_id,
        proposed_links=links or {},
        payload=payload,
        correlation_id=str(payload.get('order_no') or payload.get('reference_no') or source_event_id),
        idempotency_key=source_event_id,
    )
    try:
        return create_review_item(db, review)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/cashflow')
def cashflow(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    _user: User = Depends(require_pos_integration_user),
):
    direction = str(payload.get('direction') or '').lower()
    if direction not in {'in', 'out'}:
        raise HTTPException(status_code=422, detail='POS cashflow direction must be in or out')
    return _create_review(
        db,
        kind='cashflow_transaction',
        payload=payload,
        effect='cash_in' if direction == 'in' else 'cash_out',
        amount=_amount(payload, 'amount'),
        account_id=payload.get('financial_account_id'),
        links={
            'category': payload.get('category') or 'POS',
            'subcategory': payload.get('subcategory'),
            'payment_method': payload.get('payment_method'),
            'counterparty_name': payload.get('counterparty_name'),
            'transaction_date': payload.get('transaction_date'),
            'reference_no': payload.get('reference_no'),
        },
    )


@router.post('/transfer')
def transfer(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    _user: User = Depends(require_pos_integration_user),
):
    return _create_review(
        db,
        kind='cash_transfer',
        payload=payload,
        effect='reference_only',
        amount=_amount(payload, 'amount'),
        links={
            'from_account_id': payload.get('from_account_id'),
            'to_account_id': payload.get('to_account_id'),
            'transaction_date': payload.get('transfer_date'),
            'reference_no': payload.get('reference_no'),
        },
    )


@router.post('/room-charge')
def room_charge(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    _user: User = Depends(require_pos_integration_user),
):
    gross = float(payload.get('gross_amount') or 0)
    effect = 'receivable' if gross >= 0 else 'reference_only'
    return _create_review(
        db,
        kind='room_charge',
        payload=payload,
        effect=effect,
        amount=abs(round(gross, 2)),
        links={
            'counterparty_name': payload.get('counterparty_name'),
            'receivable_type': payload.get('receivable_type') or 'guest_balance',
            'transaction_date': payload.get('transaction_date'),
            'source_type': payload.get('source_type'),
            'source_id': payload.get('source_id'),
            'reverses_source_type': payload.get('reverses_source_type'),
            'reverses_source_id': payload.get('reverses_source_id'),
        },
    )


@router.post('/order')
def order(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    _user: User = Depends(require_pos_integration_user),
):
    total = sum(
        float(line.get('quantity') or 0) * float(line.get('unit_price') or 0) - float(line.get('discount_amount') or 0)
        for line in payload.get('lines') or []
    )
    return _create_review(
        db,
        kind='order_finalized',
        payload=payload,
        effect='reference_only',
        amount=round(max(total, 0), 2),
        links={
            'order_no': payload.get('order_no'),
            'transaction_date': payload.get('order_date'),
            'payment_method': payload.get('payment_method'),
            'counterparty_name': payload.get('counterparty'),
            'inventory_owner': 'inventory',
            'note': 'Revenue context only; Inventory owns stock consumption and COGS.',
        },
    )


@router.post('/order-void')
def order_void(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    _user: User = Depends(require_pos_integration_user),
):
    return _create_review(
        db,
        kind='order_voided',
        payload=payload,
        effect='reference_only',
        links={'order_no': payload.get('order_no'), 'reason': payload.get('reason')},
    )


@router.post('/reconciliation')
def reconciliation(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    _user: User = Depends(require_pos_integration_user),
):
    return _create_review(
        db,
        kind='register_reconciliation',
        payload=payload,
        effect='reference_only',
        amount=_amount(payload, 'actual_counted'),
        account_id=payload.get('financial_account_id'),
        links={
            'transaction_date': payload.get('reconciliation_date'),
            'shift_name': payload.get('shift_name'),
            'actual_counted': payload.get('actual_counted'),
            'status': payload.get('status'),
        },
    )
