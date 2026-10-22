import json

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.entities import (
    FinancialAccount, IntegrationReviewItem, JournalEntry, JournalLine,
    MoneyTransaction, Payable, Receivable,
)
from app.models.payable_adjustments import PayableAdjustment, SupplierCredit
from app.services.integration_linkage_audit_service import accepted_linkage_audit


@pytest.fixture
def db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session
    engine.dispose()


def review(db, name, effect, *, source='pos', amount=100, **kwargs):
    row = IntegrationReviewItem(
        source_app=source, source_event_id=name, source_entity_type='integration_test',
        source_entity_id=name, source_revision=1, financial_effect=effect,
        amount=amount, currency='PHP', status='accepted',
        idempotency_key='proof:' + name, **kwargs,
    )
    db.add(row)
    db.flush()
    return row


def test_empty_does_not_claim_producer_health(db):
    result = accepted_linkage_audit(db)
    assert result['total_accepted'] == 0
    assert result['needs_review'] == 0
    assert 'upstream delivery completeness' in result['caveat']


def test_cash_links_missing_dangling_reversed_and_amount_discrepancy_are_distinct(db):
    account = FinancialAccount(name='Cash', code='CASH-AUDIT', account_type='cash_drawer')
    db.add(account)
    db.flush()
    good = MoneyTransaction(financial_account_id=account.id, direction='in', amount=100, status='posted')
    wrong = MoneyTransaction(financial_account_id=account.id, direction='in', amount=120, status='posted')
    reversed_tx = MoneyTransaction(financial_account_id=account.id, direction='out', amount=100, status='posted', is_reversed=True)
    db.add_all([good, wrong, reversed_tx])
    db.flush()
    review(db, 'correct', 'cash_in', accepted_transaction_id=good.id)
    review(db, 'missing', 'cash_in')
    review(db, 'dangling', 'settlement', accepted_transaction_id=999999)
    review(db, 'amount', 'cash_in', accepted_transaction_id=wrong.id)
    review(db, 'reversed', 'cash_out', accepted_transaction_id=reversed_tx.id)
    review(db, 'nonfinancial', 'reference_only')
    review(db, 'folio', 'folio_charge')
    db.commit()
    result = accepted_linkage_audit(db)
    assert result['total_accepted'] == 7
    assert result['verified_record_links'] == 1
    assert result['reference_only'] == 2
    assert result['reversed_targets'] == 1
    assert result['needs_review'] == 3
    assert {v['state'] for v in result['findings']} == {'missing_expected_link', 'dangling_link', 'amount_difference'}
    assert len(accepted_linkage_audit(db, finding_limit=1)['findings']) == 1
    assert accepted_linkage_audit(db, finding_limit=1)['findings_truncated'] is True


def test_journal_validation_and_payable_and_receivable_links(db):
    okay = JournalEntry(entry_date='2026-10-22', status='posted')
    broken = JournalEntry(entry_date='2026-10-22', status='posted')
    db.add_all([okay, broken])
    db.flush()
    db.add_all([
        JournalLine(journal_entry_id=okay.id, account_code='1000', account_name='Cash', debit=50, credit=0),
        JournalLine(journal_entry_id=okay.id, account_code='4000', account_name='Revenue', debit=0, credit=50),
        JournalLine(journal_entry_id=broken.id, account_code='1000', account_name='Cash', debit=50, credit=0),
        JournalLine(journal_entry_id=broken.id, account_code='4000', account_name='Revenue', debit=0, credit=49),
    ])
    receivable = Receivable(counterparty_name='Guest', gross_amount=100, balance_due=100, status='open')
    payable = Payable(supplier_name='Supplier', gross_amount=100, balance_due=100, status='open')
    db.add_all([receivable, payable])
    db.flush()
    review(db, 'balanced', 'journal_only', accepted_journal_entry_id=okay.id)
    review(db, 'unbalanced', 'journal_only', accepted_journal_entry_id=broken.id)
    review(db, 'AR', 'receivable', accepted_receivable_id=receivable.id)
    review(db, 'AP', 'payable', accepted_payable_id=payable.id, source='inventory')
    db.commit()
    result = accepted_linkage_audit(db)
    assert result['verified_record_links'] == 3
    assert result['by_state']['unbalanced_journal'] == 1
    pos = accepted_linkage_audit(db, source_app='pos')
    assert pos['total_accepted'] == 3
    assert pos['needs_review'] == 1


def test_payable_adjustment_ids_are_audited_not_counted_as_missing_payable_link(db):
    pay = Payable(supplier_name='Supplier', gross_amount=100, balance_due=60, status='open')
    db.add(pay)
    db.flush()
    adjustment = PayableAdjustment(
        payable_id=pay.id, adjustment_date='2026-10-22', amount=40,
        source_app='inventory', source_event_id='return-1',
        purchase_order_id='PO-1', supplier_name='Supplier',
    )
    db.add(adjustment)
    db.flush()
    review(db, 'return-1', 'payable_adjustment', source='inventory', amount=40,
           validation_json=json.dumps({'payable_adjustment': {
               'adjustment_ids': [adjustment.id], 'supplier_credit_id': None,
           }}))
    review(db, 'return-2', 'payable_adjustment', source='inventory',
           validation_json=json.dumps({'payable_adjustment': {'adjustment_ids': [999999]}}))
    review(db, 'return-3', 'payable_adjustment', source='inventory')
    db.commit()
    report = accepted_linkage_audit(db)
    assert report['verified_record_links'] == 1
    assert report['by_state']['dangling_adjustment_evidence'] == 1
    assert report['by_state']['missing_adjustment_evidence'] == 1


def test_audit_performs_only_selects_and_does_not_change_database(db):
    review(db, 'missing-money', 'cash_out')
    db.commit()
    observed = []
    engine = db.get_bind()
    def observe(conn, cursor, statement, parameters, context, executemany):
        observed.append(statement.lstrip().split(None, 1)[0].upper())
    event.listen(engine, 'before_cursor_execute', observe)
    try:
        result = accepted_linkage_audit(db)
    finally:
        event.remove(engine, 'before_cursor_execute', observe)
    assert result['needs_review'] == 1
    assert observed and set(observed) == {'SELECT'}
    assert not db.dirty and not db.new and not db.deleted


def test_many_accepted_rows_use_bounded_sql_batches(db):
    for index in range(430):
        review(db, f'row-{index}', 'cash_in', accepted_transaction_id=100000 + index)
    db.commit()
    result = accepted_linkage_audit(db, finding_limit=5)
    assert result['total_accepted'] == 430
    assert result['needs_review'] == 430
    assert len(result['findings']) == 5
    assert result['findings_truncated'] is True
