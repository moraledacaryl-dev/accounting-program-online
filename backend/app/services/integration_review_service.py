from __future__ import annotations

import json
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models.entities import IntegrationReviewItem, JournalEntry, JournalLine, Payable, Receivable
from app.schemas.cashflow import MoneyTransactionCreate
from app.schemas.integration_review import IntegrationReviewCreate, IntegrationReviewDecision
from app.services.cashflow_service import create_money_transaction

ALLOWED_EFFECTS = {'cash_in', 'cash_out', 'journal_only', 'receivable', 'payable', 'folio_charge', 'reference_only', 'settlement'}


def _loads(value):
    if not value:
        return {}
    try:
        return json.loads(value)
    except Exception:
        return {}


def _serialize(row: IntegrationReviewItem) -> dict:
    return {
        'id': row.id,
        'source_app': row.source_app,
        'source_event_id': row.source_event_id,
        'source_entity_type': row.source_entity_type,
        'source_entity_id': row.source_entity_id,
        'source_revision': row.source_revision,
        'financial_effect': row.financial_effect,
        'amount': float(row.amount or 0),
        'currency': row.currency,
        'proposed_account_id': row.proposed_account_id,
        'proposed_account_name': row.proposed_account.name if row.proposed_account else None,
        'proposed_journal': _loads(row.proposed_journal_json),
        'proposed_links': _loads(row.proposed_links_json),
        'payload': _loads(row.payload_json),
        'validation': _loads(row.validation_json),
        'status': row.status,
        'reviewed_at': row.reviewed_at,
        'reviewed_by': row.reviewed_by,
        'accepted_transaction_id': row.accepted_transaction_id,
        'accepted_journal_entry_id': row.accepted_journal_entry_id,
        'accepted_receivable_id': row.accepted_receivable_id,
        'accepted_payable_id': row.accepted_payable_id,
        'rejection_reason': row.rejection_reason,
        'idempotency_key': row.idempotency_key,
        'correlation_id': row.correlation_id,
        'created_at': row.created_at.isoformat() if row.created_at else None,
    }


def create_review_item(db: Session, payload: IntegrationReviewCreate):
    if payload.financial_effect not in ALLOWED_EFFECTS:
        raise ValueError('Unsupported financial effect.')
    key = payload.idempotency_key or f'{payload.source_app}:{payload.source_event_id}:{payload.source_revision}'
    existing = db.query(IntegrationReviewItem).filter(IntegrationReviewItem.idempotency_key == key).first()
    if existing:
        return _serialize(existing)
    row = IntegrationReviewItem(
        source_app=payload.source_app.strip().lower(),
        source_event_id=payload.source_event_id,
        source_entity_type=payload.source_entity_type,
        source_entity_id=payload.source_entity_id,
        source_revision=payload.source_revision,
        financial_effect=payload.financial_effect,
        amount=payload.amount,
        currency=payload.currency,
        proposed_account_id=payload.proposed_account_id,
        proposed_journal_json=json.dumps(payload.proposed_journal or {}),
        proposed_links_json=json.dumps(payload.proposed_links or {}),
        payload_json=json.dumps(payload.payload or {}),
        validation_json=json.dumps({'valid': True, 'errors': []}),
        status='ready_for_review',
        idempotency_key=key,
        correlation_id=payload.correlation_id,
    )
    db.add(row); db.commit(); db.refresh(row)
    return _serialize(row)


def list_review_items(db: Session, *, status=None, source_app=None, financial_effect=None, q=None, limit=200):
    query = db.query(IntegrationReviewItem).options(selectinload(IntegrationReviewItem.proposed_account))
    if status: query = query.filter(IntegrationReviewItem.status == status)
    if source_app: query = query.filter(IntegrationReviewItem.source_app == source_app)
    if financial_effect: query = query.filter(IntegrationReviewItem.financial_effect == financial_effect)
    if q:
        like = f'%{q}%'
        query = query.filter(
            IntegrationReviewItem.source_event_id.ilike(like) |
            IntegrationReviewItem.source_entity_id.ilike(like) |
            IntegrationReviewItem.payload_json.ilike(like)
        )
    return [_serialize(row) for row in query.order_by(IntegrationReviewItem.id.desc()).limit(limit).all()]


def summary(db: Session):
    rows = db.query(IntegrationReviewItem.status, func.count(IntegrationReviewItem.id)).group_by(IntegrationReviewItem.status).all()
    by_status = {status: count for status, count in rows}
    return {'total': sum(by_status.values()), 'by_status': by_status, 'needs_review': by_status.get('ready_for_review', 0) + by_status.get('validation_failed', 0)}


def get_item(db: Session, item_id: int):
    row = db.query(IntegrationReviewItem).options(selectinload(IntegrationReviewItem.proposed_account)).filter(IntegrationReviewItem.id == item_id).first()
    if not row: raise ValueError('Review item not found.')
    return row


def accept_item(db: Session, item_id: int, decision: IntegrationReviewDecision, username: str | None):
    row = get_item(db, item_id)
    if row.status == 'accepted': return _serialize(row)
    if row.status not in {'ready_for_review', 'validation_failed'}: raise ValueError('Item is not available for acceptance.')
    links = _loads(row.proposed_links_json); source = f'{row.source_app}:{row.source_event_id}'
    effect = row.financial_effect
    if effect in {'cash_in', 'cash_out', 'settlement'}:
        account_id = decision.account_id or row.proposed_account_id
        if not account_id: raise ValueError('A financial account is required.')
        tx = create_money_transaction(db, MoneyTransactionCreate(
            transaction_date=decision.transaction_date,
            direction='in' if effect in {'cash_in', 'settlement'} else 'out',
            financial_account_id=account_id,
            module=row.source_app,
            category=decision.category or links.get('category') or 'Connected App',
            subcategory=links.get('subcategory'),
            level3_item=links.get('level3_item'),
            amount=row.amount,
            payment_method=decision.payment_method or links.get('payment_method') or 'other',
            reference_no=source,
            counterparty_name=links.get('counterparty_name'),
            notes=decision.notes or f'Accepted from {source}',
            linked_record_type=row.source_entity_type,
            linked_record_id=int(row.source_entity_id) if str(row.source_entity_id or '').isdigit() else None,
            status='posted',
        ), username=username)
        row.accepted_transaction_id = tx['id']
    elif effect == 'journal_only':
        journal = _loads(row.proposed_journal_json)
        entry = JournalEntry(entry_date=decision.transaction_date, reference_no=source, description=decision.notes or journal.get('description') or f'Accepted from {source}', source_module=row.source_app, status='posted')
        db.add(entry); db.flush()
        for line in journal.get('lines', []):
            db.add(JournalLine(journal_entry_id=entry.id, account_code=str(line.get('account_code') or line.get('code') or ''), account_name=str(line.get('account_name') or line.get('name') or ''), debit=float(line.get('debit') or 0), credit=float(line.get('credit') or 0), memo=line.get('memo')))
        row.accepted_journal_entry_id = entry.id
    elif effect == 'receivable':
        rec = Receivable(source_type=row.source_entity_type, source_id=int(row.source_entity_id) if str(row.source_entity_id or '').isdigit() else None, counterparty_name=links.get('counterparty_name') or row.source_app, receivable_type=links.get('receivable_type') or 'connected_app', transaction_date=decision.transaction_date, due_date=links.get('due_date'), gross_amount=row.amount, amount_collected=0, balance_due=row.amount, status='open', notes=decision.notes or source)
        db.add(rec); db.flush(); row.accepted_receivable_id = rec.id
    elif effect == 'payable':
        pay = Payable(source_type=row.source_entity_type, source_id=int(row.source_entity_id) if str(row.source_entity_id or '').isdigit() else None, supplier_name=links.get('supplier_name') or row.source_app, payable_type=links.get('payable_type') or 'connected_app', bill_date=decision.transaction_date, due_date=links.get('due_date'), gross_amount=row.amount, amount_paid=0, balance_due=row.amount, status='open', notes=decision.notes or source)
        db.add(pay); db.flush(); row.accepted_payable_id = pay.id
    else:
        row.validation_json = json.dumps({'valid': True, 'errors': [], 'result': 'reference_linked'})
    row.status='accepted'; row.reviewed_by=username; row.reviewed_at=datetime.utcnow().isoformat(); row.rejection_reason=None
    db.add(row); db.commit(); db.refresh(row)
    return _serialize(row)


def reject_item(db: Session, item_id: int, reason: str | None, username: str | None):
    row = get_item(db, item_id)
    if row.status == 'accepted': raise ValueError('Accepted items cannot be rejected; reverse the accepted accounting record instead.')
    row.status='rejected'; row.rejection_reason=reason or 'Rejected by reviewer'; row.reviewed_by=username; row.reviewed_at=datetime.utcnow().isoformat()
    db.add(row); db.commit(); db.refresh(row); return _serialize(row)


def retry_item(db: Session, item_id: int, username: str | None):
    row = get_item(db, item_id)
    if row.status not in {'validation_failed', 'rejected'}: raise ValueError('Only failed or rejected items can be retried.')
    row.status='ready_for_review'; row.validation_json=json.dumps({'valid': True, 'errors': []}); row.reviewed_by=username; row.reviewed_at=datetime.utcnow().isoformat(); row.rejection_reason=None
    db.add(row); db.commit(); db.refresh(row); return _serialize(row)
