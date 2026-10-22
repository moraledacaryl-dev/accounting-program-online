"""Read-only audit of *accepted* integration review record links.

A link proves only that the referenced local Accounting record exists and
has a compatible lifecycle state. It cannot prove delivery completeness,
bank settlement, account balance correctness or source-side acknowledgement.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    IntegrationReviewItem, JournalEntry, MoneyTransaction, Payable, Receivable,
)
from app.models.payable_adjustments import PayableAdjustment, SupplierCredit

CASH_EFFECTS = frozenset({'cash_in', 'cash_out', 'settlement'})
REFERENCES = frozenset({'reference_only', 'folio_charge'})
TARGETS = {
    'transaction': (MoneyTransaction, 'accepted_transaction_id'),
    'journal': (JournalEntry, 'accepted_journal_entry_id'),
    'receivable': (Receivable, 'accepted_receivable_id'),
    'payable': (Payable, 'accepted_payable_id'),
}
PROBLEM_STATES = frozenset({
    'missing_expected_link', 'dangling_link', 'unexpected_record_status',
    'amount_difference', 'unbalanced_journal', 'missing_adjustment_evidence',
    'dangling_adjustment_evidence', 'unclassified_effect',
    'missing_rounding_record', 'missing_payable_evidence', 'journal_amount_mismatch',
})


def _json_object(value):
    try:
        result = json.loads(value or '{}')
        return result if isinstance(result, dict) else {}
    except (TypeError, ValueError):
        return {}


def _cents(value):
    try:
        return Decimal(str(value or 0)).quantize(Decimal('0.01'))
    except (TypeError, InvalidOperation, ValueError):
        return None


def _load_targets(db: Session, cls, ids, *, journal=False):
    """Chunk IN queries for SQLite parameter limits and large intake histories."""
    collected = {}
    ordered = sorted(set(int(value) for value in ids if value is not None))
    for i in range(0, len(ordered), 400):
        query = db.query(cls).filter(cls.id.in_(ordered[i:i + 400]))
        if journal:
            query = query.options(selectinload(JournalEntry.lines))
        collected.update({row.id: row for row in query.all()})
    return collected


def _journal_integrity(journal, *, expected_amount=None):
    """Check both posted lifecycle and signed debit/credit equality."""
    if journal is None:
        return ('dangling_link', 'Linked journal entry cannot be found.')
    if journal.is_reversed or str(journal.status or '').lower() == 'reversed':
        return ('reversed_target', 'Linked journal has been reversed; inspect its reversal trail.')
    if str(journal.status or '').lower() != 'posted':
        return ('unexpected_record_status', 'Linked journal entry is not posted.')
    debit = sum((Decimal(str(line.debit or 0)) for line in journal.lines), Decimal('0'))
    credit = sum((Decimal(str(line.credit or 0)) for line in journal.lines), Decimal('0'))
    if debit <= 0 or debit != credit:
        return ('unbalanced_journal', 'Linked journal entry has no positive balanced debit/credit lines.')
    if expected_amount is not None and _cents(debit) != expected_amount:
        return ('journal_amount_mismatch', 'Linked journal amount differs from its cash transaction.')
    return ('verified_record_link', '')


def accepted_linkage_audit(db: Session, *, source_app: str | None = None, finding_limit: int = 40):
    """No database mutations, retries, journal postings or producer API calls."""
    query = db.query(IntegrationReviewItem).filter(IntegrationReviewItem.status == 'accepted')
    if source_app:
        query = query.filter(IntegrationReviewItem.source_app == source_app.strip().lower())
    rows = query.order_by(IntegrationReviewItem.id.desc()).all()

    ids = defaultdict(set)
    for row in rows:
        for kind, (_, field) in TARGETS.items():
            value = getattr(row, field, None)
            if value is not None:
                ids[kind].add(value)
        if row.source_app == 'staff' and str(row.source_event_id or '').endswith(':Paid'):
            payroll_proof = _json_object(row.validation_json).get('payroll_payment_reconciliation') or {}
            if isinstance(payroll_proof, dict):
                for key, kind in (('rounding_transaction_id', 'transaction'), ('payable_id', 'payable')):
                    reference = payroll_proof.get(key)
                    if type(reference) is int and reference > 0:
                        ids[kind].add(reference)
        if row.financial_effect == 'payable_adjustment':
            adjustment = _json_object(row.validation_json).get('payable_adjustment') or {}
            if isinstance(adjustment, dict):
                ids['adjustment'].update(v for v in adjustment.get('adjustment_ids', []) if isinstance(v, int))
                if isinstance(adjustment.get('supplier_credit_id'), int):
                    ids['credit'].add(adjustment['supplier_credit_id'])

    targets = {
        kind: _load_targets(db, cls, ids[kind], journal=(kind == 'journal'))
        for kind, (cls, _) in TARGETS.items()
    }
    targets['adjustment'] = _load_targets(db, PayableAdjustment, ids['adjustment'])
    targets['credit'] = _load_targets(db, SupplierCredit, ids['credit'])

    by_state = Counter()
    by_source = {}
    findings = []
    for row in rows:
        effect = str(row.financial_effect or '')
        state = 'verified_record_link'
        note = ''
        target_kind = None
        target_id = None
        if effect in CASH_EFFECTS:
            target_kind = 'transaction'
        elif effect == 'journal_only':
            target_kind = 'journal'
        elif effect == 'receivable':
            target_kind = 'receivable'
        elif effect == 'payable':
            target_kind = 'payable'
        elif effect == 'payable_adjustment':
            metadata = _json_object(row.validation_json).get('payable_adjustment')
            if not isinstance(metadata, dict):
                state, note = 'missing_adjustment_evidence', 'No recorded adjustment result.'
            else:
                adjustments = metadata.get('adjustment_ids') or []
                credit_id = metadata.get('supplier_credit_id')
                if not adjustments and not credit_id:
                    state, note = 'missing_adjustment_evidence', 'No adjustment or supplier credit IDs recorded.'
                elif (
                    any(not isinstance(x, int) or x not in targets['adjustment'] for x in adjustments)
                    or (credit_id is not None and credit_id not in targets['credit'])
                ):
                    state, note = 'dangling_adjustment_evidence', 'A recorded adjustment or supplier credit cannot be found.'
        elif effect in REFERENCES:
            state, note = 'reference_only', 'No direct financial record is expected for this effect.'
        else:
            state, note = 'unclassified_effect', 'Accepted effect has no recognized linkage verification rule.'

        if target_kind:
            field = TARGETS[target_kind][1]
            target_id = getattr(row, field, None)
            if target_id is None:
                state, note = 'missing_expected_link', 'Accepted effect lacks its expected Accounting record ID.'
            else:
                target = targets[target_kind].get(target_id)
                if target is None:
                    state, note = 'dangling_link', 'Referenced Accounting record does not exist.'
                elif target_kind == 'transaction':
                    if target.is_reversed or str(target.status or '').lower() == 'reversed':
                        state, note = 'reversed_target', 'Linked money transaction is reversed; inspect its reversal trail.'
                    elif str(target.status or '').lower() != 'posted':
                        state, note = 'unexpected_record_status', 'Linked money transaction is not posted.'
                    elif (source_amount := _cents(row.amount)) is None or _cents(target.amount) != source_amount:
                        state, note = 'amount_difference', 'Linked transaction amount differs from accepted source amount.'
                    elif target.direction != ('out' if effect == 'cash_out' else 'in'):
                        state, note = 'unexpected_record_status', 'Linked transaction direction differs from the accepted effect.'
                elif target_kind == 'journal':
                    state, note = _journal_integrity(target)

        # Some accepted events create MORE THAN ONE accounting object.
        # POS settlements/refunds require a balanced journal as well as the
        # posted cash transaction; previously only the cash link was checked.
        if effect in CASH_EFFECTS and state == 'verified_record_link':
            links = _json_object(row.proposed_links_json)
            pos_journal_required = (
                row.source_app == 'pos'
                and links.get('category') in {'POS Settlement', 'POS Refund'}
            )
            journal_id = row.accepted_journal_entry_id
            if pos_journal_required or journal_id is not None:
                if journal_id is None:
                    state, note = 'missing_expected_link', 'POS settlement or refund has no linked journal ID.'
                    target_kind, target_id = 'journal', None
                else:
                    transaction = targets['transaction'].get(row.accepted_transaction_id)
                    state, note = _journal_integrity(
                        targets['journal'].get(journal_id),
                        expected_amount=_cents(transaction.amount) if transaction else None,
                    )
                    if state != 'verified_record_link':
                        target_kind, target_id = 'journal', journal_id

        # Staff Paid creates the exact-net settlement and may create a
        # SEPARATE rounding expense. Audit the recorded identifiers without
        # treating the rounding expense as a second payroll disbursement.
        if effect == 'cash_out' and row.source_app == 'staff' and str(row.source_event_id or '').endswith(':Paid') and state == 'verified_record_link':
            reconciliation = _json_object(row.validation_json).get('payroll_payment_reconciliation')
            if isinstance(reconciliation, dict):
                payable_id = reconciliation.get('payable_id')
                if type(payable_id) is int and payable_id > 0 and payable_id not in targets['payable']:
                    state, note = 'missing_payable_evidence', 'Payroll settlement references a missing payable.'
                    target_kind, target_id = 'payable', payable_id
                rounding = _cents(reconciliation.get('rounding_difference'))
                rounding_id = reconciliation.get('rounding_transaction_id')
                if state == 'verified_record_link' and rounding is not None and rounding > 0:
                    if type(rounding_id) is not int or rounding_id <= 0:
                        state, note = 'missing_rounding_record', 'Positive payroll rounding has no linked rounding expense transaction.'
                        target_kind, target_id = 'transaction', None
                    else:
                        expense = targets['transaction'].get(rounding_id)
                        if expense is None:
                            state, note = 'dangling_link', 'Linked payroll rounding expense does not exist.'
                        elif expense.is_reversed or str(expense.status or '').lower() == 'reversed':
                            state, note = 'reversed_target', 'Linked payroll rounding expense is reversed.'
                        elif str(expense.status or '').lower() != 'posted' or expense.direction != 'out':
                            state, note = 'unexpected_record_status', 'Payroll rounding expense is not a posted cash-out.'
                        elif _cents(expense.amount) != rounding:
                            state, note = 'amount_difference', 'Payroll rounding expense differs from recorded rounding difference.'
                        if state != 'verified_record_link':
                            target_kind, target_id = 'transaction', rounding_id

        by_state[state] += 1
        source = str(row.source_app or 'unspecified')
        group = by_source.setdefault(source, {'accepted': 0, 'verified_record_links': 0, 'needs_review': 0, 'reversed_targets': 0, 'reference_only': 0})
        group['accepted'] += 1
        if state == 'verified_record_link':
            group['verified_record_links'] += 1
        elif state == 'reversed_target':
            group['reversed_targets'] += 1
        elif state == 'reference_only':
            group['reference_only'] += 1
        else:
            group['needs_review'] += 1
        if state in PROBLEM_STATES and len(findings) < max(0, finding_limit):
            findings.append({
                'review_id': row.id, 'source_app': source, 'source_event_id': row.source_event_id,
                'financial_effect': effect, 'state': state, 'target_kind': target_kind,
                'target_id': target_id, 'reason': note,
            })

    total_problems = sum(by_state[key] for key in PROBLEM_STATES)
    return {
        'scope': 'accounting_accepted_record_links_only',
        'total_accepted': len(rows),
        'verified_record_links': by_state['verified_record_link'],
        'reference_only': by_state['reference_only'],
        'reversed_targets': by_state['reversed_target'],
        'needs_review': total_problems,
        'by_state': dict(sorted(by_state.items())),
        'by_source': dict(sorted(by_source.items())),
        'findings': findings,
        'findings_total': total_problems,
        'findings_truncated': total_problems > len(findings),
        'caveat': 'Local record linkage only: does not certify posting correctness, upstream delivery completeness, ledger balances, source acknowledgements, or bank settlement.',
    }
