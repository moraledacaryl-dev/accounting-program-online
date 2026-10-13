from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_closed_cash_day_guard_covers_money_mutations():
    source = (ROOT / 'backend/app/services/cashflow_service.py').read_text()
    assert "action='approve this transaction'" in source
    assert "action='cancel this transaction'" in source
    assert "action='reverse this transaction'" in source
    assert "action='delete this transaction'" in source
    assert "action='edit this transaction'" in source
    assert "action='move or edit this transaction'" in source


def test_closed_cash_day_guard_covers_both_transfer_accounts():
    source = (ROOT / 'backend/app/services/cashflow_service.py').read_text()
    for action in ('approve this transfer', 'cancel this transfer', 'delete this transfer'):
        assert source.count(f"action='{action}'") >= 2
    assert "action='reverse this transfer'" in source
    assert "action='post its reversal'" in source


def test_ledger_uses_posting_status_and_business_date_fallbacks():
    source = (ROOT / 'backend/app/services/cashflow_service.py').read_text()
    assert "if _has_cash_ledger_effect(row) else 0.0" in source
    assert "meta.get('transaction_at') or row.get('date')" in source
    assert "meta.get('transfer_at') or row.get('date')" in source
    assert "row.get('entry_type') == 'money_transaction'" in source


def test_money_transaction_update_persists_movement_timestamp():
    source = (ROOT / 'backend/app/services/cashflow_service.py').read_text()
    assert "if 'transaction_at' in data:" in source
    assert "row.transaction_at = _safe_datetime(data.get('transaction_at')) if data.get('transaction_at') else None" in source
