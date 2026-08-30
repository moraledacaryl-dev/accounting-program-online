from types import SimpleNamespace

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from app.api.journals import reverse_entry
from app.api.reports import _build_financial_statements
from app.db.database import Base
from app.models.entities import JournalEntry, JournalLine, Record
from app.services.accounting_service import autopost_record


def make_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    return TestingSession()


def _totals(db):
    debit, credit = db.query(
        func.coalesce(func.sum(JournalLine.debit), 0),
        func.coalesce(func.sum(JournalLine.credit), 0),
    ).join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id).filter(
        JournalEntry.status == 'posted'
    ).one()
    return round(float(debit or 0), 4), round(float(credit or 0), 4)


def test_golden_ledger_autopost_trial_balance_and_financial_statements_reconcile():
    db = make_session()
    fixtures = [
        Record(module_slug='rooms', direction='income', workflow_status='approved', amount=5000, transaction_date='2026-08-29', payment_method='cash', name='Room revenue'),
        Record(module_slug='restaurant', direction='income', workflow_status='approved', amount=1500, transaction_date='2026-08-29', payment_method='bank_transfer', name='Restaurant revenue'),
        Record(module_slug='restaurant', direction='expense', workflow_status='approved', amount=600, transaction_date='2026-08-29', payment_method='cash', name='Restaurant expense'),
        Record(module_slug='assets', direction='asset', workflow_status='approved', amount=2000, transaction_date='2026-08-29', payment_method='bank_transfer', name='Equipment purchase'),
    ]
    db.add_all(fixtures)
    db.flush()

    for record in fixtures:
        assert autopost_record(db, record, commit=False) is not None
    db.commit()

    debit, credit = _totals(db)
    assert debit == credit == 9100

    statements = _build_financial_statements(
        db,
        start_date='2026-08-01',
        end_date='2026-08-31',
        as_of_date='2026-08-31',
    )
    assert statements['trial_balance']['totals']['is_balanced'] is True
    assert statements['trial_balance']['totals']['variance'] == 0
    assert statements['balance_sheet']['totals']['balance_check'] == 0
    assert statements['profit_and_loss']['totals']['revenue'] == 6500
    assert statements['profit_and_loss']['totals']['expenses'] == 600
    assert statements['profit_and_loss']['totals']['net_income'] == 5900


def test_golden_ledger_reversal_preserves_balance_and_neutralizes_economic_effect():
    db = make_session()
    record = Record(
        module_slug='rooms',
        direction='income',
        workflow_status='approved',
        amount=2500,
        transaction_date='2026-08-29',
        payment_method='cash',
        name='Reversible room revenue',
    )
    db.add(record)
    db.flush()
    original = autopost_record(db, record, commit=False)
    db.commit()

    reversal = reverse_entry(
        original.id,
        db=db,
        user=SimpleNamespace(username='pass72-auditor'),
    )

    db.refresh(original)
    assert original.is_reversed is True
    assert reversal.reversed_from_id == original.id

    debit, credit = _totals(db)
    assert debit == credit == 5000

    net_by_account = db.query(
        JournalLine.account_code,
        func.sum(JournalLine.debit - JournalLine.credit),
    ).join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id).filter(
        JournalEntry.id.in_([original.id, reversal.id])
    ).group_by(JournalLine.account_code).all()
    assert all(round(float(net or 0), 4) == 0 for _code, net in net_by_account)
