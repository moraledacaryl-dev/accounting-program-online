"""Group 1: financial reporting must not invent historical balances or activity classes."""
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.reports import (
    _account_family, _build_aging_report, _build_cash_flow_statement,
    _build_profit_and_loss, _sum_settlements_by_record,
)
from app.db.database import Base
from app.models.entities import FinancialAccount, MoneyTransaction, Record, RecordSettlement


@pytest.fixture
def db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session
    engine.dispose()


def make_record(db, *, direction='income', amount=1000, day='2026-09-01'):
    row = Record(
        module_slug='events', module_name='Events', category='Events',
        bucket='Bookings', item='Booking', name='Historical invoice',
        direction=direction, amount=amount, workflow_status='approved',
        payment_method='on_account', transaction_date=day, due_date='2026-09-20',
    )
    db.add(row)
    db.flush()
    return row


def settle(db, record, *, amount, day):
    db.add(RecordSettlement(
        record_id=record.id, amount=amount, settlement_date=day,
        payment_method='bank_transfer',
    ))


def test_aging_uses_dated_transactions_and_settlements_as_of_each_cutoff(db):
    ar = make_record(db, amount=1000)
    ap = make_record(db, direction='expense', amount=300)
    future = make_record(db, amount=500, day='2026-10-10')
    settle(db, ar, amount=200, day='2026-09-15')
    settle(db, ar, amount=250, day='2026-10-05')
    settle(db, ap, amount=50, day='2026-10-10')
    settle(db, ar, amount=25, day=None)  # No reliable historical effective date.
    db.commit()

    past = _build_aging_report(db, '2026-09-30')
    assert past['receivables']['count'] == 1
    assert past['receivables']['total_outstanding'] == 800
    assert past['payables']['total_outstanding'] == 300
    assert past['receivables']['items'][0]['record_id'] == ar.id
    assert past['receivables']['items'][0]['settled_amount'] == 200

    october = _build_aging_report(db, '2026-10-06')
    assert october['receivables']['total_outstanding'] == 550
    assert october['payables']['total_outstanding'] == 300
    assert future.id not in [x['record_id'] for x in october['receivables']['items']]

    later = _build_aging_report(db, '2026-10-11')
    assert later['receivables']['total_outstanding'] == 1050  # 550 + 500
    assert later['payables']['total_outstanding'] == 250
    assert later['receivables']['count'] == 2
    assert _sum_settlements_by_record(db, [ar.id], as_of_date='2026-09-30')[ar.id] == Decimal('200.0000')


def test_aging_rejects_invalid_as_of_and_uses_decimal_peso_balances(db):
    ar = make_record(db, amount=0.3)
    settle(db, ar, amount=0.1, day='2026-09-20')
    settle(db, ar, amount=0.1, day='2026-09-25')
    db.commit()
    assert _build_aging_report(db, '2026-09-30')['receivables']['total_outstanding'] == 0.1
    with pytest.raises(ValueError, match='as_of_date'):
        _build_aging_report(db, '2026-02-31')


def test_profit_and_loss_separates_cogs_from_operating_expenses():
    lines = [
        {'family': 'revenue', 'account_code': '4000', 'account_name': 'Sales', 'balance': 1000},
        {'family': 'expenses', 'account_code': '5100', 'account_name': 'Kitchen inventory used',
         'account_type': 'expense', 'account_subtype': 'Cost of Goods Sold', 'balance': 400},
        {'family': 'expenses', 'account_code': '5300', 'account_name': 'Payroll Expense',
         'account_type': 'expense', 'balance': 150},
        {'family': 'expenses', 'account_code': '5400', 'account_name': 'Cost of Services',
         'account_type': 'expense', 'balance': 50},
    ]
    pnl = _build_profit_and_loss(lines)
    assert pnl['totals'] == {
        'revenue': 1000, 'cost_of_sales': 450, 'operating_expenses': 150,
        'expenses': 600, 'gross_profit': 550, 'net_income': 400,
    }
    assert len(pnl['cost_of_sales']) == 2
    assert pnl['cost_of_sales_identified'] is True
    assert pnl['totals']['gross_profit'] - pnl['totals']['operating_expenses'] == pnl['totals']['net_income']
    assert _account_family('7600', 'cogs') == 'expenses'


def test_profit_and_loss_discloses_missing_cogs_without_reclassifying_expenses():
    pnl = _build_profit_and_loss([
        {'family': 'revenue', 'account_name': 'Room Revenue', 'balance': 100},
        {'family': 'expenses', 'account_name': 'Utilities', 'balance': 30},
    ])
    assert pnl['cost_of_sales_identified'] is False
    assert pnl['totals']['gross_profit'] == 100
    assert pnl['totals']['expenses'] == 30
    assert pnl['totals']['net_income'] == 70


def test_cash_movements_keep_unknown_finance_flows_unclassified(db):
    account = FinancialAccount(name='BPI', code='BNK-CF-01', account_type='bank')
    db.add(account)
    db.flush()
    movements = [
        ('events', 'Event payment', 'in', 300),
        ('finance', 'Equipment Purchase', 'out', 90),
        ('finance', 'Owner Contribution', 'in', 120),
        ('finance', 'Miscellaneous', 'out', 25),
    ]
    for module, category, direction, amount in movements:
        db.add(MoneyTransaction(
            financial_account_id=account.id, transaction_date='2026-09-10',
            module=module, category=category, direction=direction,
            amount=amount, status='posted', is_reversed=False,
        ))
    db.commit()
    cash = _build_cash_flow_statement(db, '2026-09-01', '2026-09-30')
    assert cash['classification_counts'] == {
        'operating': 1, 'investing': 1, 'financing': 1, 'unclassified': 1,
    }
    assert cash['classification_status'] == 'requires_review'
    assert cash['operating_activities'][0]['net'] == 300
    assert cash['investing_activities'][0]['net'] == -90
    assert cash['financing_activities'][0]['net'] == 120
    assert cash['unclassified_activities'][0]['net'] == -25
    assert cash['totals'] == {'cash_in': 420, 'cash_out': 115, 'net_cash_flow': 305}
    assert cash['method'] == 'management_direct_cash_movements'


def test_cash_reversal_offsets_original_across_reporting_periods(db):
    account = FinancialAccount(name='Cash', code='CASH-REV-01', account_type='cash_drawer')
    db.add(account)
    db.flush()
    db.add(MoneyTransaction(
        financial_account_id=account.id, transaction_date='2026-09-10',
        posted_at='2026-09-10', module='events', category='Event payment',
        direction='in', amount=300, status='reversed', is_reversed=True,
    ))
    db.flush()
    original = db.query(MoneyTransaction).one()
    db.add(MoneyTransaction(
        financial_account_id=account.id, transaction_date='2026-10-02',
        posted_at='2026-10-02', module='events', category='Event payment',
        direction='out', amount=300, status='posted', is_reversed=False,
        reversed_from_id=original.id,
    ))
    db.commit()
    september = _build_cash_flow_statement(db, '2026-09-01', '2026-09-30')
    october = _build_cash_flow_statement(db, '2026-10-01', '2026-10-31')
    both = _build_cash_flow_statement(db, '2026-09-01', '2026-10-31')
    assert september['totals']['net_cash_flow'] == 300
    assert october['totals']['net_cash_flow'] == -300
    assert both['totals']['net_cash_flow'] == 0
    assert both['classification_counts']['operating'] == 2
