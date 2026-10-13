from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'app/services/cashflow_service.py').read_text()


def _chunk(start, end):
    return SOURCE.split(start, 1)[1].split(end, 1)[0]


def test_account_summary_today_totals_only_count_cash_effect_rows():
    chunk = _chunk('def list_financial_accounts(', 'def create_financial_account(')
    assert chunk.count('_cash_ledger_effect_filter(MoneyTransaction)') == 2
    assert chunk.count('_cash_ledger_effect_filter(AccountTransfer)') == 2


def test_full_balance_recompute_ignores_nonposting_rows_but_preserves_reversed_posted_history():
    chunk = _chunk('def recompute_all_financial_balances(', 'def _account_balances_as_of(')
    assert chunk.count('if not _has_cash_ledger_effect(row):') == 2


def test_as_of_balances_use_same_cash_effect_predicate():
    chunk = _chunk('def _account_balances_as_of(', 'def _account_opening_balance_at(')
    assert chunk.count('if not _has_cash_ledger_effect(row):') == 2
