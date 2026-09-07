from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import records, journals, reports
from app.db.database import Base
from app.models.entities import Record, JournalEntry, JournalLine, ChartAccount, AccountMappingRule, AuditEvent
from app.schemas.common import RecordUpdate, RecordCreate, JournalEntryCreate
from app.services import record_service
from app.services.accounting_service import autopost_record
from app.services.account_mapping_service import update_chart_account, delete_chart_account
from app.schemas.accounting_setup import ChartAccountUpdate


@pytest.fixture
def db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session
    engine.dispose()


def record(db, status='approved'):
    row = Record(module_slug='payroll', module_name='Payroll', category='Audit', bucket='Audit', item='Audit',
                 name='Audit', direction='expense', workflow_status=status, amount=100, transaction_date='2026-09-07', payment_method='cash')
    db.add(row)
    db.commit()
    return row


def accounts(db):
    db.add_all([ChartAccount(code='1000', name='Cash', account_type='asset'),
                ChartAccount(code='4000', name='Income', account_type='income')])
    db.commit()


def payload(**extra):
    values = dict(entry_date='2026-09-07', lines=[dict(account_code='1000', debit='0.3'), dict(account_code='4000', credit='0.3')])
    values.update(extra)
    return JournalEntryCreate(**values)


def test_booking_editor_cannot_change_payroll_or_approve_rooms(db, monkeypatch):
    actor = SimpleNamespace(role='front_desk', username='limited')
    monkeypatch.setattr(records, 'get_user_permission_keys', lambda *_: {'bookings.edit'})
    row = record(db, 'draft')
    with pytest.raises(HTTPException) as exc:
        records.single_update(row.id, RecordUpdate(amount=200), db=db, user=actor)
    assert exc.value.status_code == 403
    assert db.get(Record, row.id).amount == 100
    with pytest.raises(HTTPException) as exc:
        records._authorize_record_write(db, actor, 'rooms', approval=True)
    assert exc.value.status_code == 403


def test_finance_editor_cannot_change_money_in_to_money_out(db, monkeypatch):
    monkeypatch.setattr(records, 'get_user_permission_keys', lambda *_: {'journals.post', 'cashflow.money_in'})
    actor = SimpleNamespace(role='staff', username='limited')
    records._authorize_record_write(db, actor, 'finance', direction='income')
    with pytest.raises(HTTPException):
        records._authorize_record_write(db, actor, 'finance', direction='expense')


def test_posted_record_edit_and_delete_preserve_ledger(db):
    row = record(db)
    journal = autopost_record(db, row)
    with pytest.raises(ValueError, match='Posted records'):
        record_service.update_record(db, row.id, RecordUpdate(amount=250))
    with pytest.raises(ValueError, match='Posted records'):
        record_service.delete_record(db, row.id)
    assert row.amount == 100
    assert sum(line.debit for line in db.query(JournalLine).filter_by(journal_entry_id=journal.id)) == Decimal('100')
    record_service.update_record(db, row.id, RecordUpdate(notes='Evidence reviewed'), approver='auditor')
    assert db.query(AuditEvent).filter_by(entity_type='record', action='updated').count() == 1


def test_record_and_posting_failure_roll_back_together(db, monkeypatch):
    monkeypatch.setattr(record_service, 'validate_record', lambda *args: (True, None))
    monkeypatch.setattr(record_service, 'get_module_name', lambda *args: 'Payroll')
    def fail(*args, **kwargs):
        raise ValueError('posting failed')
    monkeypatch.setattr(record_service, 'autopost_record', fail)
    with pytest.raises(ValueError):
        record_service.create_record(db, 'payroll', RecordCreate(category='a', bucket='b', item='c', amount=100, direction='expense', workflow_status='approved'))
    db.rollback()
    assert db.query(Record).count() == 0
    assert db.query(JournalEntry).count() == 0


@pytest.mark.parametrize('extra', [
    {'entry_date': ''}, {'entry_date': '2026-02-30'}, {'status': 'unexpected'}, {'lines': []},
    {'lines': [dict(account_code='1000', debit=-100), dict(account_code='4000', credit=-100)]},
    {'lines': [dict(account_code='1000', debit=10, credit=10), dict(account_code='4000', debit=10, credit=10)]},
    {'lines': [dict(account_code='1000', debit='NaN'), dict(account_code='4000', credit=1)]},
    {'lines': [dict(account_code='1000', debit='0.00001'), dict(account_code='4000', credit='0.00001')]},
])
def test_invalid_journal_payloads_rejected(extra):
    with pytest.raises(ValidationError):
        payload(**extra)


def test_manual_journal_requires_active_chart_and_canonical_names(db):
    with pytest.raises(HTTPException, match='') as exc:
        journals.create_entry(payload(), db=db, user=SimpleNamespace(username='auditor'))
    assert exc.value.status_code == 400
    accounts(db)
    result = journals.create_entry(payload(status='posted'), db=db, user=SimpleNamespace(username='auditor'))
    assert result.lines[0].account_name == 'Cash'
    assert result.lines[0].debit == Decimal('0.3000')


def test_reports_share_posted_status_and_reversals_net_to_zero(db):
    accounts(db)
    actor = SimpleNamespace(username='auditor')
    original = journals.create_entry(payload(status='posted'), db=db, user=actor)
    legacy = JournalEntry(entry_date='2026-09-07', status='unexpected')
    db.add(legacy); db.flush()
    db.add(JournalLine(journal_entry_id=legacy.id, account_code='9999', account_name='Invalid status', debit=37, credit=0)); db.commit()
    assert all(entry.id != legacy.id for entry, _ in reports._posted_journal_rows(db))
    assert all(line['account_code'] != '9999' for line in journals.trial_balance(db=db, user=actor))
    journals.reverse_entry(original.id, db=db, user=actor)
    with pytest.raises(HTTPException):
        journals.reverse_entry(original.id, db=db, user=actor)
    assert all(line['debit'] == line['credit'] for line in journals.trial_balance(db=db, user=actor))


def test_posting_rule_controls_generated_accounts(db):
    accounts(db)
    db.add(AccountMappingRule(module_slug='payroll', direction='expense', debit_account_code='4000', credit_account_code='1000', priority=1, is_active=True))
    db.commit()
    row = record(db)
    entry = autopost_record(db, row)
    debit = db.query(JournalLine).filter(JournalLine.journal_entry_id == entry.id, JournalLine.debit > 0).one()
    assert debit.account_code == '4000'


def test_inactive_rule_account_blocks_posting(db):
    accounts(db)
    db.query(ChartAccount).filter_by(code='4000').update({'is_active': False})
    db.add(AccountMappingRule(module_slug='payroll', debit_account_code='4000', credit_account_code='1000', is_active=True))
    db.commit()
    with pytest.raises(ValueError, match='inactive'):
        autopost_record(db, record(db))


def test_chart_accounts_cannot_cycle_or_delete_used_accounts(db):
    accounts(db)
    cash = db.query(ChartAccount).filter_by(code='1000').one()
    income = db.query(ChartAccount).filter_by(code='4000').one()
    update_chart_account(db, income.id, ChartAccountUpdate(parent_id=cash.id))
    with pytest.raises(ValueError, match='cycle'):
        update_chart_account(db, cash.id, ChartAccountUpdate(parent_id=income.id))
    journals.create_entry(payload(), db=db, user=SimpleNamespace(username='auditor'))
    with pytest.raises(ValueError, match='journals'):
        delete_chart_account(db, income.id)


def test_journal_retries_return_one_entry_and_conflicting_key_is_rejected(db):
    accounts(db)
    actor = SimpleNamespace(username='auditor')
    first = journals.create_entry(payload(), db=db, user=actor, idempotency_key='journal-retry-test')
    second = journals.create_entry(payload(), db=db, user=actor, idempotency_key='journal-retry-test')
    assert first.id == second.id
    assert db.query(JournalEntry).count() == 1
    with pytest.raises(HTTPException) as exc:
        journals.create_entry(payload(description='different request'), db=db, user=actor, idempotency_key='journal-retry-test')
    assert exc.value.status_code == 409


def test_sql_aggregated_financial_statements_preserve_coverage(db):
    accounts(db)
    for _ in range(3):
        journals.create_entry(payload(status='posted'), db=db, user=SimpleNamespace(username='auditor'))
    statements = reports._build_financial_statements(db, start_date='2026-09-01', end_date='2026-09-07')
    assert statements['ledger_coverage']['posted_journal_entries_in_period'] == 3
    assert statements['ledger_coverage']['posted_journal_lines_in_period'] == 6
    assert statements['trial_balance']['totals']['debit'] == 0.9


def test_read_only_integrity_preflight_detects_historical_mismatches(db):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('integrity_preflight', Path(__file__).resolve().parents[1] / 'scripts/check_accounting_integrity.py')
    preflight = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(preflight)
    row = record(db)
    autopost_record(db, row)
    assert preflight.inspect_integrity(db) == []
    # Simulate old persisted corruption without using the newly guarded mutation path.
    row.amount = 250
    db.commit()
    assert any(issue['type'] == 'source_journal_mismatch' for issue in preflight.inspect_integrity(db))
    assert row.amount == 250


def test_legacy_zero_payroll_lines_remain_reversible(db):
    accounts(db)
    actor = SimpleNamespace(username='auditor')
    entry = journals.create_entry(payload(status='posted'), db=db, user=actor)
    db.add(JournalLine(journal_entry_id=entry.id, account_code='2100', account_name='Unused deduction', debit=0, credit=0))
    db.commit()
    reversal = journals.reverse_entry(entry.id, db=db, user=actor)
    assert reversal.reversed_from_id == entry.id


def test_preview_uses_same_bank_and_ewallet_accounts_as_posting():
    from app.services.journal_posting_service import preview_journal_impact
    assert preview_journal_impact('in', 100, 'bank_transfer')['debit_line']['code'] == '1020'
    assert preview_journal_impact('in', 100, 'gcash')['debit_line']['code'] == '1010'
    with pytest.raises(ValueError):
        preview_journal_impact('out', -1, 'cash')


def test_manual_journal_cannot_impersonate_generated_record_reference():
    with pytest.raises(ValidationError, match='reserved'):
        payload(reference_no='REC-1000')


def test_record_update_rejects_explicit_null_workflow_status():
    with pytest.raises(ValidationError, match='cannot be null'):
        RecordUpdate(workflow_status=None)
