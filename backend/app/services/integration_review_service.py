from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models.entities import FinancialAccount, IntegrationReviewItem, JournalEntry, JournalLine, Payable, Receivable
from app.schemas.cashflow import MoneyTransactionCreate
from app.schemas.integration_review import IntegrationReviewCreate, IntegrationReviewDecision
from app.services.audit_service import record_audit
from app.services.bir_service import ensure_date_unlocked
from app.services.cashflow_service import create_money_transaction

ALLOWED_EFFECTS = {
    'cash_in', 'cash_out', 'journal_only', 'receivable', 'payable',
    'folio_charge', 'reference_only', 'settlement',
}
CASH_EFFECTS = {'cash_in', 'cash_out', 'settlement'}
REFERENCE_EFFECTS = {'folio_charge', 'reference_only'}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _actor(username: str | None):
    return SimpleNamespace(id=None, username=username)


def _loads(value):
    if not value:
        return {}
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return {}


def _journal_lines(journal: dict) -> list[dict]:
    lines = journal.get('lines') if isinstance(journal, dict) else None
    return lines if isinstance(lines, list) else []


def validate_review_payload(db: Session, payload: IntegrationReviewCreate | dict) -> dict:
    data = payload.model_dump() if hasattr(payload, 'model_dump') else dict(payload or {})
    effect = str(data.get('financial_effect') or '').strip().lower()
    source_app = str(data.get('source_app') or '').strip().lower()
    source_event_id = str(data.get('source_event_id') or '').strip()
    source_entity_type = str(data.get('source_entity_type') or '').strip()
    currency = str(data.get('currency') or 'PHP').strip().upper()
    amount = float(data.get('amount') or 0)
    links = data.get('proposed_links') or {}
    journal = data.get('proposed_journal') or {}
    account_id = data.get('proposed_account_id')

    errors: list[str] = []
    warnings: list[str] = []

    if not source_app:
        errors.append('source_app is required.')
    if not source_event_id:
        errors.append('source_event_id is required.')
    if not source_entity_type:
        errors.append('source_entity_type is required.')
    if int(data.get('source_revision') or 0) < 1:
        errors.append('source_revision must be at least 1.')
    if effect not in ALLOWED_EFFECTS:
        errors.append('Unsupported financial effect.')
    if len(currency) != 3 or not currency.isalpha():
        errors.append('currency must be a three-letter ISO code.')

    if effect not in {'journal_only', 'reference_only'} and amount <= 0:
        errors.append('amount must be greater than zero for this financial effect.')

    if effect in CASH_EFFECTS:
        if not account_id:
            errors.append('A proposed financial account is required for cash and settlement effects.')
        else:
            account = db.query(FinancialAccount).filter(FinancialAccount.id == int(account_id)).first()
            if not account:
                errors.append('The proposed financial account does not exist.')
            elif not account.is_active:
                errors.append('The proposed financial account is inactive.')
            elif str(account.currency or 'PHP').upper() != currency:
                errors.append('The proposed financial account currency does not match the event currency.')

    if effect == 'journal_only':
        lines = _journal_lines(journal)
        if len(lines) < 2:
            errors.append('A journal proposal requires at least two lines.')
        debit_total = 0.0
        credit_total = 0.0
        for index, line in enumerate(lines, start=1):
            code = str(line.get('account_code') or line.get('code') or '').strip()
            debit = float(line.get('debit') or 0)
            credit = float(line.get('credit') or 0)
            if not code:
                errors.append(f'Journal line {index} requires an account code.')
            if debit < 0 or credit < 0:
                errors.append(f'Journal line {index} cannot contain negative debit or credit values.')
            if debit > 0 and credit > 0:
                errors.append(f'Journal line {index} cannot contain both a debit and a credit.')
            if debit == 0 and credit == 0:
                errors.append(f'Journal line {index} must contain a debit or credit amount.')
            debit_total += debit
            credit_total += credit
        if round(debit_total, 2) != round(credit_total, 2):
            errors.append('Proposed journal debits and credits must balance.')
        if round(debit_total, 2) <= 0:
            errors.append('Proposed journal total must be greater than zero.')
        if amount and round(amount, 2) != round(debit_total, 2):
            warnings.append('Event amount differs from the proposed journal total.')

    if effect == 'receivable' and not str(links.get('counterparty_name') or '').strip():
        errors.append('Receivable effects require proposed_links.counterparty_name.')
    if effect == 'payable' and not str(links.get('supplier_name') or '').strip():
        errors.append('Payable effects require proposed_links.supplier_name.')
    if effect in REFERENCE_EFFECTS:
        if not str(links.get('target_type') or '').strip() or not str(links.get('target_id') or '').strip():
            errors.append('Reference and folio effects require proposed_links.target_type and target_id.')

    return {
        'valid': not errors,
        'errors': errors,
        'warnings': warnings,
        'validated_at': _now_iso(),
    }


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
    validation = validate_review_payload(db, payload)
    source_app = payload.source_app.strip().lower()
    key = payload.idempotency_key or f'{source_app}:{payload.source_event_id}:{payload.source_revision}'
    existing = db.query(IntegrationReviewItem).filter(IntegrationReviewItem.idempotency_key == key).first()
    if existing:
        return _serialize(existing)

    source_match = db.query(IntegrationReviewItem).filter(
        IntegrationReviewItem.source_app == source_app,
        IntegrationReviewItem.source_event_id == payload.source_event_id,
    ).order_by(IntegrationReviewItem.source_revision.desc()).first()
    if source_match and int(payload.source_revision) <= int(source_match.source_revision):
        raise ValueError('source_revision must be newer than the latest received revision.')

    row = IntegrationReviewItem(
        source_app=source_app,
        source_event_id=payload.source_event_id,
        source_entity_type=payload.source_entity_type,
        source_entity_id=payload.source_entity_id,
        source_revision=payload.source_revision,
        financial_effect=payload.financial_effect,
        amount=payload.amount,
        currency=payload.currency.upper(),
        proposed_account_id=payload.proposed_account_id,
        proposed_journal_json=json.dumps(payload.proposed_journal or {}),
        proposed_links_json=json.dumps(payload.proposed_links or {}),
        payload_json=json.dumps(payload.payload or {}),
        validation_json=json.dumps(validation),
        status='ready_for_review' if validation['valid'] else 'validation_failed',
        idempotency_key=key,
        correlation_id=payload.correlation_id,
    )
    db.add(row)
    db.flush()
    record_audit(
        db,
        entity_type='integration_review_item',
        entity_id=row.id,
        action='intake_validated' if validation['valid'] else 'intake_validation_failed',
        after={'status': row.status, 'validation': validation},
        source_app=source_app,
        correlation_id=payload.correlation_id,
    )
    db.commit()
    db.refresh(row)
    return _serialize(row)


def list_review_items(db: Session, *, status=None, source_app=None, financial_effect=None, q=None, limit=200):
    query = db.query(IntegrationReviewItem).options(selectinload(IntegrationReviewItem.proposed_account))
    if status:
        query = query.filter(IntegrationReviewItem.status == status)
    if source_app:
        query = query.filter(IntegrationReviewItem.source_app == source_app)
    if financial_effect:
        query = query.filter(IntegrationReviewItem.financial_effect == financial_effect)
    if q:
        like = f'%{q}%'
        query = query.filter(
            IntegrationReviewItem.source_event_id.ilike(like)
            | IntegrationReviewItem.source_entity_id.ilike(like)
            | IntegrationReviewItem.payload_json.ilike(like)
        )
    return [_serialize(row) for row in query.order_by(IntegrationReviewItem.id.desc()).limit(limit).all()]


def summary(db: Session):
    rows = db.query(IntegrationReviewItem.status, func.count(IntegrationReviewItem.id)).group_by(IntegrationReviewItem.status).all()
    by_status = {status: count for status, count in rows}
    return {
        'total': sum(by_status.values()),
        'by_status': by_status,
        'needs_review': by_status.get('ready_for_review', 0) + by_status.get('validation_failed', 0),
    }


def get_item(db: Session, item_id: int):
    row = db.query(IntegrationReviewItem).options(selectinload(IntegrationReviewItem.proposed_account)).filter(IntegrationReviewItem.id == item_id).first()
    if not row:
        raise ValueError('Review item not found.')
    return row


def _current_validation(db: Session, row: IntegrationReviewItem) -> dict:
    payload = {
        'source_app': row.source_app,
        'source_event_id': row.source_event_id,
        'source_entity_type': row.source_entity_type,
        'source_entity_id': row.source_entity_id,
        'source_revision': row.source_revision,
        'financial_effect': row.financial_effect,
        'amount': row.amount,
        'currency': row.currency,
        'proposed_account_id': row.proposed_account_id,
        'proposed_journal': _loads(row.proposed_journal_json),
        'proposed_links': _loads(row.proposed_links_json),
        'payload': _loads(row.payload_json),
    }
    return validate_review_payload(db, payload)


def accept_item(db: Session, item_id: int, decision: IntegrationReviewDecision, username: str | None):
    row = get_item(db, item_id)
    if row.status == 'accepted':
        return _serialize(row)
    if row.status != 'ready_for_review':
        raise ValueError('Only validated items ready for review can be accepted.')

    validation = _current_validation(db, row)
    row.validation_json = json.dumps(validation)
    if not validation['valid']:
        row.status = 'validation_failed'
        db.add(row)
        db.commit()
        raise ValueError('; '.join(validation['errors']))

    transaction_date = (decision.transaction_date or '').strip()
    if not transaction_date:
        raise ValueError('transaction_date is required for acceptance.')
    ensure_date_unlocked(db, transaction_date, scope='bir', action='accept connected-app financial event')

    links = _loads(row.proposed_links_json)
    source = f'{row.source_app}:{row.source_event_id}'
    effect = row.financial_effect

    if effect in CASH_EFFECTS:
        account_id = decision.account_id or row.proposed_account_id
        account = db.query(FinancialAccount).filter(FinancialAccount.id == int(account_id)).first() if account_id else None
        if not account or not account.is_active:
            raise ValueError('An active financial account is required.')
        if str(account.currency or 'PHP').upper() != str(row.currency or 'PHP').upper():
            raise ValueError('Financial account currency does not match the event currency.')
        tx = create_money_transaction(
            db,
            MoneyTransactionCreate(
                transaction_date=transaction_date,
                direction='in' if effect in {'cash_in', 'settlement'} else 'out',
                financial_account_id=account.id,
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
            ),
            username=username,
        )
        row.accepted_transaction_id = tx['id']
    elif effect == 'journal_only':
        journal = _loads(row.proposed_journal_json)
        lines = _journal_lines(journal)
        debit_total = round(sum(float(line.get('debit') or 0) for line in lines), 2)
        credit_total = round(sum(float(line.get('credit') or 0) for line in lines), 2)
        if debit_total != credit_total or debit_total <= 0:
            raise ValueError('Proposed journal must be balanced and greater than zero.')
        entry = JournalEntry(
            entry_date=transaction_date,
            reference_no=source,
            description=decision.notes or journal.get('description') or f'Accepted from {source}',
            source_module=row.source_app,
            status='posted',
            posted_by=username,
        )
        db.add(entry)
        db.flush()
        for line in lines:
            db.add(JournalLine(
                journal_entry_id=entry.id,
                account_code=str(line.get('account_code') or line.get('code') or '').strip(),
                account_name=str(line.get('account_name') or line.get('name') or '').strip(),
                debit=float(line.get('debit') or 0),
                credit=float(line.get('credit') or 0),
                memo=line.get('memo'),
            ))
        record_audit(
            db,
            entity_type='journal_entry',
            entity_id=entry.id,
            action='posted_from_integration_review',
            user=_actor(username),
            after={'reference_no': source, 'debit_total': debit_total, 'credit_total': credit_total},
            source_app=row.source_app,
            correlation_id=row.correlation_id,
        )
        row.accepted_journal_entry_id = entry.id
    elif effect == 'receivable':
        rec = Receivable(
            source_type=row.source_entity_type,
            source_id=int(row.source_entity_id) if str(row.source_entity_id or '').isdigit() else None,
            counterparty_name=links['counterparty_name'],
            receivable_type=links.get('receivable_type') or 'connected_app',
            transaction_date=transaction_date,
            due_date=links.get('due_date'),
            gross_amount=row.amount,
            amount_collected=0,
            balance_due=row.amount,
            status='open',
            notes=decision.notes or source,
        )
        db.add(rec)
        db.flush()
        row.accepted_receivable_id = rec.id
    elif effect == 'payable':
        pay = Payable(
            source_type=row.source_entity_type,
            source_id=int(row.source_entity_id) if str(row.source_entity_id or '').isdigit() else None,
            supplier_name=links['supplier_name'],
            payable_type=links.get('payable_type') or 'connected_app',
            bill_date=transaction_date,
            due_date=links.get('due_date'),
            gross_amount=row.amount,
            amount_paid=0,
            balance_due=row.amount,
            status='open',
            notes=decision.notes or source,
        )
        db.add(pay)
        db.flush()
        row.accepted_payable_id = pay.id
    else:
        row.validation_json = json.dumps({
            **validation,
            'result': 'reference_linked',
            'target_type': links.get('target_type'),
            'target_id': links.get('target_id'),
        })

    row.status = 'accepted'
    row.reviewed_by = username
    row.reviewed_at = _now_iso()
    row.rejection_reason = None
    db.add(row)
    db.flush()
    record_audit(
        db,
        entity_type='integration_review_item',
        entity_id=row.id,
        action='accepted',
        user=_actor(username),
        after={
            'status': row.status,
            'accepted_transaction_id': row.accepted_transaction_id,
            'accepted_journal_entry_id': row.accepted_journal_entry_id,
            'accepted_receivable_id': row.accepted_receivable_id,
            'accepted_payable_id': row.accepted_payable_id,
        },
        source_app=row.source_app,
        correlation_id=row.correlation_id,
    )
    db.commit()
    db.refresh(row)
    return _serialize(row)


def reject_item(db: Session, item_id: int, reason: str | None, username: str | None):
    row = get_item(db, item_id)
    if row.status == 'accepted':
        raise ValueError('Accepted items cannot be rejected; reverse the accepted accounting record instead.')
    before = {'status': row.status}
    row.status = 'rejected'
    row.rejection_reason = reason or 'Rejected by reviewer'
    row.reviewed_by = username
    row.reviewed_at = _now_iso()
    db.add(row)
    db.flush()
    record_audit(
        db,
        entity_type='integration_review_item',
        entity_id=row.id,
        action='rejected',
        user=_actor(username),
        before=before,
        after={'status': row.status, 'reason': row.rejection_reason},
        source_app=row.source_app,
        correlation_id=row.correlation_id,
    )
    db.commit()
    db.refresh(row)
    return _serialize(row)


def retry_item(db: Session, item_id: int, username: str | None):
    row = get_item(db, item_id)
    if row.status not in {'validation_failed', 'rejected'}:
        raise ValueError('Only failed or rejected items can be retried.')
    validation = _current_validation(db, row)
    row.validation_json = json.dumps(validation)
    row.status = 'ready_for_review' if validation['valid'] else 'validation_failed'
    row.reviewed_by = username
    row.reviewed_at = _now_iso()
    row.rejection_reason = None
    db.add(row)
    db.flush()
    record_audit(
        db,
        entity_type='integration_review_item',
        entity_id=row.id,
        action='revalidated',
        user=_actor(username),
        after={'status': row.status, 'validation': validation},
        source_app=row.source_app,
        correlation_id=row.correlation_id,
    )
    db.commit()
    db.refresh(row)
    return _serialize(row)
