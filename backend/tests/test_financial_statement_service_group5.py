"""Group 5: extraction must preserve the public reporting calculations."""
from decimal import Decimal
from types import SimpleNamespace

from app.api import reports
from app.services import financial_statement_calculations as calc


def test_router_reexports_same_statement_functions_without_http_coupling():
    functions = (
        '_norm', '_round_money', '_account_family', '_chart_account_map',
        '_posted_journal_rows', '_group_lines', '_sum_family',
        '_is_cost_of_sales_account', '_build_profit_and_loss',
        '_build_balance_sheet', '_build_trial_balance',
        '_cash_activity_classification', '_build_cash_flow_statement',
    )
    for function in functions:
        assert getattr(reports, function) is getattr(calc, function)
    assert calc._round_money(Decimal('0.12345')) == 0.1235
    assert calc._account_family('1000', 'asset') == 'assets'
    assert calc._account_family('5100', 'Cost of Goods Sold') == 'expenses'


def test_journal_line_grouping_keeps_debit_credit_sign_and_four_decimal_quantum():
    source = [
        (None, SimpleNamespace(account_code='4000', account_name='Sales', debit=0, credit=Decimal('100.1234'))),
        (None, SimpleNamespace(account_code='4000', account_name='Sales', debit=Decimal('0.0001'), credit=0)),
        (None, SimpleNamespace(account_code='5100', account_name='COGS', debit=Decimal('40.0001'), credit=0)),
        (None, SimpleNamespace(account_code='1000', account_name='Cash', debit=Decimal('100.1234'), credit=0)),
    ]
    chart_map = {
        '4000': SimpleNamespace(name='Sales', account_type='revenue', subtype=None),
        '5100': SimpleNamespace(name='Cost of Goods Sold', account_type='expense', subtype='cogs'),
        '1000': SimpleNamespace(name='Cash', account_type='asset', subtype=None),
    }
    rows = calc._group_lines(source, chart_map)
    by_code = {row['account_code']: row for row in rows}
    assert [x['account_code'] for x in rows] == ['1000', '4000', '5100']
    assert by_code['4000']['credit'] == 100.1234
    assert by_code['4000']['debit'] == 0.0001
    assert by_code['4000']['balance'] == 100.1233
    assert by_code['5100']['balance'] == 40.0001
    assert by_code['1000']['balance'] == 100.1234

    pnl = calc._build_profit_and_loss(rows)
    assert pnl['totals'] == {
        'revenue': 100.1233,
        'cost_of_sales': 40.0001,
        'operating_expenses': 0,
        'expenses': 40.0001,
        'gross_profit': 60.1232,
        'net_income': 60.1232,
    }
    assert calc._build_trial_balance(rows)['totals']['debit'] == 140.1236


def test_balance_sheet_current_earnings_and_cash_movement_metadata_keep_contract():
    rows = [
        {'family': 'assets', 'account_code': '1000', 'balance': 120, 'debit': 120, 'credit': 0},
        {'family': 'liabilities', 'account_code': '2000', 'balance': 20, 'debit': 0, 'credit': 20},
        {'family': 'equity', 'account_code': '3000', 'balance': 60, 'debit': 0, 'credit': 60},
        {'family': 'revenue', 'account_code': '4000', 'balance': 50, 'debit': 0, 'credit': 50},
        {'family': 'expenses', 'account_code': '5000', 'balance': 10, 'debit': 10, 'credit': 0},
    ]
    balance = calc._build_balance_sheet(rows)
    assert balance['totals'] == {
        'assets': 120, 'liabilities': 20, 'equity': 100,
        'liabilities_and_equity': 120, 'balance_check': 0,
    }
    assert balance['equity'][-1]['account_name'] == 'Current Earnings'
    tx = SimpleNamespace(module='finance', category='Equipment Purchase', subcategory='', level3_item='')
    assert calc._cash_activity_classification(tx) == 'investing'
    tx.category = 'Miscellaneous'
    assert calc._cash_activity_classification(tx) == 'unclassified'
