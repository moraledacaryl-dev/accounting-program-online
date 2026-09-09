from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models.entities import IntegrationReviewItem, Payable
from app.models.payable_adjustments import PayableAdjustment, SupplierCredit


def _loads(value):
    if not value:
        return {}
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return {}


def _round(value) -> float:
    return round(float(value or 0), 4)


def _existing_result(db: Session, source_app: str, source_event_id: str):
    adjustments = (
        db.query(PayableAdjustment)
        .filter(
            PayableAdjustment.source_app == source_app,
            PayableAdjustment.source_event_id == source_event_id,
        )
        .order_by(PayableAdjustment.id.asc())
        .all()
    )
    credit = (
        db.query(SupplierCredit)
        .filter(
            SupplierCredit.source_app == source_app,
            SupplierCredit.source_event_id == source_event_id,
        )
        .first()
    )
    if not adjustments and not credit:
        return None
    return {
        'allocated_amount': _round(sum(item.amount for item in adjustments)),
        'supplier_credit_amount': _round(credit.amount if credit else 0),
        'supplier_credit_id': credit.id if credit else None,
        'adjustment_ids': [item.id for item in adjustments],
        'payable_ids': [item.payable_id for item in adjustments],
        'replayed': True,
    }


def _receipt_payable_ids(db: Session, purchase_order_id: str) -> list[int]:
    rows = (
        db.query(IntegrationReviewItem)
        .filter(
            IntegrationReviewItem.source_app == 'inventory',
            IntegrationReviewItem.financial_effect == 'payable',
            IntegrationReviewItem.status == 'accepted',
            IntegrationReviewItem.accepted_payable_id.isnot(None),
        )
        .order_by(IntegrationReviewItem.id.asc())
        .all()
    )
    result: list[int] = []
    seen: set[int] = set()
    for row in rows:
        links = _loads(row.proposed_links_json)
        if str(links.get('purchase_order_id') or '') != purchase_order_id:
            continue
        payload = _loads(row.payload_json)
        if str(payload.get('event_type') or '') != 'procurement.goods_received':
            continue
        payable_id = int(row.accepted_payable_id)
        if payable_id not in seen:
            result.append(payable_id)
            seen.add(payable_id)
    return result


def apply_purchase_return_adjustment(
    db: Session,
    review_item: IntegrationReviewItem,
    links: dict,
    adjustment_date: str,
    notes: str | None = None,
) -> dict:
    source_app = str(review_item.source_app or '').strip().lower()
    source_event_id = str(review_item.source_event_id or '').strip()
    purchase_order_id = str(links.get('purchase_order_id') or '').strip()
    supplier_name = str(links.get('supplier_name') or '').strip()
    amount = _round(review_item.amount)

    if source_app != 'inventory':
        raise ValueError('Payable adjustments are currently supported only for Inventory events.')
    if not source_event_id:
        raise ValueError('source_event_id is required for payable adjustment.')
    if not purchase_order_id:
        raise ValueError('purchase_order_id is required for payable adjustment.')
    if not supplier_name:
        raise ValueError('supplier_name is required for payable adjustment.')
    if amount <= 0:
        raise ValueError('Payable adjustment amount must be greater than zero.')

    replay = _existing_result(db, source_app, source_event_id)
    if replay:
        return replay

    payable_ids = _receipt_payable_ids(db, purchase_order_id)
    if not payable_ids:
        raise ValueError(
            f'No accepted goods-receipt payable exists for purchase order {purchase_order_id}.'
        )

    payables = (
        db.query(Payable)
        .filter(Payable.id.in_(payable_ids))
        .populate_existing()
        .order_by(Payable.id.asc())
        .with_for_update()
        .all()
    )
    by_id = {row.id: row for row in payables}
    ordered = [by_id[item_id] for item_id in payable_ids if item_id in by_id]

    remaining = amount
    adjustment_ids: list[int] = []
    adjusted_payable_ids: list[int] = []

    for payable in ordered:
        if remaining <= 0.0001:
            break
        outstanding = max(_round(payable.balance_due), 0.0)
        allocation = min(remaining, outstanding)
        if allocation <= 0.0001:
            continue

        adjustment = PayableAdjustment(
            payable_id=payable.id,
            adjustment_date=adjustment_date,
            amount=allocation,
            source_app=source_app,
            source_event_id=source_event_id,
            purchase_order_id=purchase_order_id,
            supplier_name=supplier_name,
            notes=notes or f'Inventory purchase return {source_event_id}',
        )
        db.add(adjustment)
        db.flush()
        adjustment_ids.append(adjustment.id)
        adjusted_payable_ids.append(payable.id)

        payable.gross_amount = _round(max(float(payable.amount_paid or 0), float(payable.gross_amount or 0) - allocation))
        payable.balance_due = _round(max(0.0, float(payable.gross_amount or 0) - float(payable.amount_paid or 0)))
        if payable.balance_due <= 0.0001:
            payable.balance_due = 0.0
            payable.status = 'settled'
            payable.closed_at = payable.closed_at or adjustment_date
        elif float(payable.amount_paid or 0) > 0:
            payable.status = 'partial'
            payable.closed_at = None
        else:
            payable.status = 'open'
            payable.closed_at = None
        db.add(payable)
        remaining = _round(remaining - allocation)

    credit = None
    if remaining > 0.0001:
        credit = SupplierCredit(
            supplier_name=supplier_name,
            purchase_order_id=purchase_order_id,
            credit_date=adjustment_date,
            amount=remaining,
            applied_amount=0,
            balance_available=remaining,
            status='open',
            source_app=source_app,
            source_event_id=source_event_id,
            notes=notes or f'Unapplied credit from Inventory purchase return {source_event_id}',
        )
        db.add(credit)
        db.flush()

    return {
        'allocated_amount': _round(amount - remaining),
        'supplier_credit_amount': _round(remaining),
        'supplier_credit_id': credit.id if credit else None,
        'adjustment_ids': adjustment_ids,
        'payable_ids': adjusted_payable_ids,
        'replayed': False,
    }
