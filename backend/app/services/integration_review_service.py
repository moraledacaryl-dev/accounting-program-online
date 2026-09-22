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
from app.services.payable_adjustment_service import apply_purchase_return_adjustment

ALLOWED_EFFECTS = {
    'cash_in', 'cash_out', 'journal_only', 'receivable', 'payable', 'payable_adjustment',
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
            # Connected source apps know that cash moved, but they do not own
            # Accounting's cash/bank/GCash account master. Keep the event
            # reviewable and require the reviewer to choose the real account
            # before acceptance/posting.
            warnings.append('Select the actual financial account before posting this cash or settlement event.')
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
    if effect == 'payable_adjustment':
        if source_app != 'inventory':
            errors.append('Payable adjustments are currently supported only for Inventory events.')
        if not str(links.get('supplier_name') or '').strip():
            errors.append('Payable adjustments require proposed_links.supplier_name.')
        if not str(links.get('purchase_order_id') or '').strip():
            errors.append('Payable adjustments require proposed_links.purchase_order_id.')
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


def _staff_payroll_approval_has_paid_partner(db: Session, row: IntegrationReviewItem) -> bool:
    if row.source_app != 'staff' or not str(row.source_event_id or '').endswith(':Approved'):
        return False
    return db.query(IntegrationReviewItem.id).filter(
        IntegrationReviewItem.source_app == 'staff',
        IntegrationReviewItem.source_entity_id == row.source_entity_id,
        IntegrationReviewItem.source_event_id.endswith(':Paid'),
    ).first() is not None


def _staff_payroll_revision_of(row: IntegrationReviewItem) -> int | None:
    if row.source_app != 'staff' or not str(row.source_event_id or '').endswith(':Paid'):
        return None
    payload = _loads(row.payload_json)
    run = payload.get('run') if isinstance(payload, dict) else None
    if not isinstance(run, dict):
        nested = payload.get('payload') if isinstance(payload, dict) else None
        run = nested.get('run') if isinstance(nested, dict) else None
    try:
        revision_of = int((run or {}).get('revision_of_run_id') or 0)
    except (TypeError, ValueError):
        return None
    return revision_of or None


def _staff_payroll_superseded_paid_ids(rows: list[IntegrationReviewItem]) -> set[str]:
    return {
        str(revision_of)
        for row in rows
        if (revision_of := _staff_payroll_revision_of(row)) is not None
    }


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
    rows = query.order_by(IntegrationReviewItem.id.desc()).limit(limit).all()
    superseded_paid_ids = _staff_payroll_superseded_paid_ids(rows)
    # Staff sends both Approved (liability) and Paid (settlement) lifecycle
    # events. Once Paid exists, present the run as one review workflow instead
    # of two apparently duplicated rows. Paid revisions also supersede their
    # original Paid run; keep the original row for audit but hide it from the
    # actionable queue so one payroll period cannot look like two cash-outs.
    return [
        _serialize(row)
        for row in rows
        if not _staff_payroll_approval_has_paid_partner(db, row)
        and not (
            row.source_app == 'staff'
            and str(row.source_event_id or '').endswith(':Paid')
            and str(row.source_entity_id or '') in superseded_paid_ids
        )
    ]


def summary(db: Session):
    rows = db.query(IntegrationReviewItem).all()
    superseded_paid_ids = _staff_payroll_superseded_paid_ids(rows)
    visible = [
        row
        for row in rows
        if not _staff_payroll_approval_has_paid_partner(db, row)
        and not (
            row.source_app == 'staff'
            and str(row.source_event_id or '').endswith(':Paid')
            and str(row.source_entity_id or '') in superseded_paid_ids
        )
    ]
    by_status: dict[str, int] = {}
    for row in visible:
        by_status[row.status] = by_status.get(row.status, 0) + 1
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


def _locked_item(db: Session, item_id: int):
    row = (
        db.query(IntegrationReviewItem)
        .filter(IntegrationReviewItem.id == int(item_id))
        .populate_existing()
        .with_for_update()
        .first()
    )
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
    row = _locked_item(db, item_id)
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
    payable_adjustment_result = None

    if decision.actual_amount_paid is not None and not (row.source_app == 'staff' and row.source_event_id.endswith(':Paid') and effect == 'cash_out'):
        raise ValueError('actual_amount_paid is supported only for Staff & Payroll paid cash-out events.')

    is_staff_payroll_paid = row.source_app == 'staff' and row.source_event_id.endswith(':Paid') and effect == 'cash_out'

    if is_staff_payroll_paid:
        # A later Staff Paid revision replaces this run as the authoritative
        # payroll for the period. Never let a hidden superseded row be posted
        # directly by ID as an additional cash disbursement.
        paid_rows = db.query(IntegrationReviewItem).filter(
            IntegrationReviewItem.source_app == 'staff',
            IntegrationReviewItem.source_event_id.endswith(':Paid'),
        ).all()
        if str(row.source_entity_id or '') in _staff_payroll_superseded_paid_ids(paid_rows):
            raise ValueError('This payroll payment was superseded by a paid revision and cannot be accepted as a separate cash disbursement.')

        account_id = decision.account_id or row.proposed_account_id
        account = db.query(FinancialAccount).filter(FinancialAccount.id == int(account_id)).first() if account_id else None
        if not account or not account.is_active:
            raise ValueError('An active financial account is required.')
        if str(account.currency or 'PHP').upper() != str(row.currency or 'PHP').upper():
            raise ValueError('Financial account currency does not match the event currency.')

        source_amount = round(float(row.amount or 0), 2)
        actual_amount = round(float(decision.actual_amount_paid), 2) if decision.actual_amount_paid is not None else source_amount
        if actual_amount < source_amount:
            raise ValueError('Actual payroll payment cannot be below exact net pay. Record an underpayment as an outstanding payroll payable instead.')
        rounding_difference = round(actual_amount - source_amount, 2)

        approval = db.query(IntegrationReviewItem).filter(
            IntegrationReviewItem.source_app == 'staff',
            IntegrationReviewItem.source_entity_id == row.source_entity_id,
            IntegrationReviewItem.source_event_id.endswith(':Approved'),
        ).order_by(IntegrationReviewItem.source_revision.desc()).with_for_update().first()

        payable = None
        if approval and approval.status == 'accepted' and approval.accepted_payable_id:
            payable = db.get(Payable, int(approval.accepted_payable_id))
        elif approval and approval.status == 'ready_for_review':
            approval_links = _loads(approval.proposed_links_json)
            payable = Payable(
                source_type=approval.source_entity_type,
                source_id=int(approval.source_entity_id) if str(approval.source_entity_id or '').isdigit() else None,
                supplier_name=approval_links.get('supplier_name') or approval_links.get('counterparty_name') or 'Employees',
                payable_type=approval_links.get('payable_type') or 'payroll',
                bill_date=transaction_date,
                due_date=approval_links.get('due_date'),
                gross_amount=source_amount,
                amount_paid=0,
                balance_due=source_amount,
                status='open',
                notes=f'Payroll liability from staff:{approval.source_event_id}',
            )
            db.add(payable)
            db.flush()
            approval.accepted_payable_id = payable.id
            approval.status = 'accepted'
            approval.reviewed_by = username
            approval.reviewed_at = _now_iso()
            approval.rejection_reason = None
            db.add(approval)
        elif approval:
            raise ValueError(f'Matching payroll approval is not ready for settlement (status: {approval.status}).')
        else:
            raise ValueError('Matching payroll approval event was not found; payroll payment cannot be posted without its liability.')

        if not payable or round(float(payable.balance_due or 0), 2) < source_amount:
            raise ValueError('Matching payroll payable is missing or does not have the exact net pay outstanding.')

        base_notes = decision.notes or f'Payroll settlement from {source}'
        exact_tx = create_money_transaction(
            db,
            MoneyTransactionCreate(
                transaction_date=transaction_date,
                direction='out',
                financial_account_id=account.id,
                module='staff',
                category='Payroll',
                subcategory='Net Pay',
                amount=source_amount,
                payment_method=decision.payment_method or links.get('payment_method') or 'other',
                reference_no=source,
                counterparty_name=links.get('counterparty_name') or 'Employees',
                notes=f'{base_notes} | Exact payroll liability: {source_amount:.2f}.',
                linked_record_type=row.source_entity_type,
                linked_record_id=int(row.source_entity_id) if str(row.source_entity_id or '').isdigit() else None,
                payable_id=payable.id,
                status='posted',
            ),
            username=username,
            commit=False,
        )
        row.accepted_transaction_id = exact_tx['id']

        rounding_tx_id = None
        if rounding_difference > 0:
            rounding_tx = create_money_transaction(
                db,
                MoneyTransactionCreate(
                    transaction_date=transaction_date,
                    direction='out',
                    financial_account_id=account.id,
                    module='staff',
                    category='Payroll',
                    subcategory='Rounding',
                    level3_item='Payroll rounding expense',
                    amount=rounding_difference,
                    payment_method=decision.payment_method or links.get('payment_method') or 'other',
                    reference_no=f'{source}:rounding',
                    counterparty_name=links.get('counterparty_name') or 'Employees',
                    notes=f'Payroll rounding expense: exact {source_amount:.2f}; actual paid {actual_amount:.2f}; difference +{rounding_difference:.2f}.',
                    linked_record_type=row.source_entity_type,
                    linked_record_id=int(row.source_entity_id) if str(row.source_entity_id or '').isdigit() else None,
                    status='posted',
                ),
                username=username,
                commit=False,
            )
            rounding_tx_id = rounding_tx['id']

        row.validation_json = json.dumps({
            **validation,
            'payroll_payment_reconciliation': {
                'exact_net_pay': source_amount,
                'actual_amount_paid': actual_amount,
                'rounding_difference': rounding_difference,
                'payable_id': payable.id,
                'rounding_transaction_id': rounding_tx_id,
            },
        })
    elif effect in CASH_EFFECTS:
        account_id = decision.account_id or row.proposed_account_id
        account = db.query(FinancialAccount).filter(FinancialAccount.id == int(account_id)).first() if account_id else None
        if not account or not account.is_active:
            raise ValueError('An active financial account is required.')
        if str(account.currency or 'PHP').upper() != str(row.currency or 'PHP').upper():
            raise ValueError('Financial account currency does not match the event currency.')
        source_amount = round(float(row.amount or 0), 2)
        actual_amount = round(float(decision.actual_amount_paid), 2) if decision.actual_amount_paid is not None else source_amount
        rounding_difference = round(actual_amount - source_amount, 2)
        base_notes = decision.notes or f'Accepted from {source}'
        if decision.actual_amount_paid is not None:
            direction_label = 'up' if rounding_difference > 0 else ('down' if rounding_difference < 0 else 'exactly')
            base_notes = (
                f'{base_notes} | Payroll exact net pay: {source_amount:.2f}; '
                f'actual amount paid: {actual_amount:.2f}; rounding difference: {rounding_difference:+.2f} ({direction_label}).'
            )
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
                amount=actual_amount,
                payment_method=decision.payment_method or links.get('payment_method') or 'other',
                reference_no=source,
                counterparty_name=links.get('counterparty_name'),
                notes=base_notes,
                linked_record_type=row.source_entity_type,
                linked_record_id=int(row.source_entity_id) if str(row.source_entity_id or '').isdigit() else None,
                status='posted',
            ),
            username=username,
        )
        row.accepted_transaction_id = tx['id']
        if decision.actual_amount_paid is not None:
            row.validation_json = json.dumps({
                **validation,
                'payroll_payment_reconciliation': {
                    'exact_net_pay': source_amount,
                    'actual_amount_paid': actual_amount,
                    'rounding_difference': rounding_difference,
                },
            })
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
    elif effect == 'payable_adjustment':
        payable_adjustment_result = apply_purchase_return_adjustment(
            db,
            row,
            links,
            transaction_date,
            notes=decision.notes,
        )
        row.validation_json = json.dumps({
            **validation,
            'result': 'payable_adjusted',
            'payable_adjustment': payable_adjustment_result,
            'actual_amount_paid': float(decision.actual_amount_paid) if decision.actual_amount_paid is not None else None,
            'source_amount': float(row.amount or 0),
            'rounding_difference': round(float(decision.actual_amount_paid) - float(row.amount or 0), 2) if decision.actual_amount_paid is not None else None,
        })
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
            'payable_adjustment': payable_adjustment_result,
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
