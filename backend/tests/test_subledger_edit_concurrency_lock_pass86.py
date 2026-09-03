from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_subledger_edit_guard_locks_and_refreshes_parent_rows():
    source = (ROOT / 'app/services/subledger_edit_guard.py').read_text()
    assert 'def _lock_subledger_row' in source
    assert '.populate_existing()' in source
    assert '.with_for_update()' in source
    assert '_lock_subledger_row(db, Receivable, receivable_id)' in source
    assert '_lock_subledger_row(db, Payable, payable_id)' in source


def test_http_edits_use_reusable_locked_service_boundary():
    receivables = (ROOT / 'app/api/receivables.py').read_text()
    payables = (ROOT / 'app/api/payables.py').read_text()
    service = (ROOT / 'app/services/subledger_edit_service.py').read_text()

    assert 'update_receivable_safely(db, receivable_id, payload)' in receivables
    assert 'update_payable_safely(db, payable_id, payload)' in payables
    assert 'ensure_receivable_edit_preserves_settlement(db, receivable_id, payload)' in service
    assert 'ensure_payable_edit_preserves_settlement(db, payable_id, payload)' in service
