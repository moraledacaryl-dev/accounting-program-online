from pathlib import Path
from types import SimpleNamespace

from app.services.cashflow_service import _has_cash_ledger_effect, _cash_ledger_effect_filter
from app.models.entities import MoneyTransaction, AccountTransfer


def test_reversed_posted_original_still_has_cash_effect():
    assert _has_cash_ledger_effect(SimpleNamespace(status='posted', is_reversed=False, posted_at='2026-10-13'))
    assert _has_cash_ledger_effect(SimpleNamespace(status='reversed', is_reversed=True, posted_at='2026-10-12'))
    assert not _has_cash_ledger_effect(SimpleNamespace(status='reversed', is_reversed=True, posted_at=None))
    for status in ('draft', 'pending', 'cancelled'):
        assert not _has_cash_ledger_effect(SimpleNamespace(status=status, is_reversed=False, posted_at=None))


def test_reconciliation_queries_share_ledger_effect_predicate():
    source = (Path(__file__).resolve().parents[1] / 'app/services/cashflow_service.py').read_text()
    for start, end in [('def _account_opening_balance_at', 'def _resolve_bir_status'),
                       ('def _account_day_expected_values', 'def create_cash_reconciliation')]:
        chunk = source.split(start, 1)[1].split(end, 1)[0]
        assert chunk.count('_cash_ledger_effect_filter(MoneyTransaction)') == 2
        assert chunk.count('_cash_ledger_effect_filter(AccountTransfer)') == 2
    ledger = source.split('def account_ledger(', 1)[1].split('def combined_cash_ledger(', 1)[0]
    assert ledger.count('_has_cash_ledger_effect(row)') == 2
    assert _cash_ledger_effect_filter(MoneyTransaction) is not None
    assert _cash_ledger_effect_filter(AccountTransfer) is not None
