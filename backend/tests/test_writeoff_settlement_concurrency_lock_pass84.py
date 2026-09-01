from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_settlement_guard_locks_parent_rows_before_state_check():
    source = (ROOT / 'backend/app/services/settlement_reversal_guard.py').read_text()
    assert 'with_for_update()' in source
    assert '_lock_parent(db, Receivable' in source
    assert '_lock_parent(db, Payable' in source
    assert source.index('_lock_parent(db, Receivable') < source.index("== 'written_off'")


def test_writeoff_locks_same_subledger_rows_before_transition():
    source = (ROOT / 'backend/app/services/writeoff_service.py').read_text()
    assert 'with_for_update()' in source
    assert '_lock_subledger_row(db, Receivable, receivable_id)' in source
    assert '_lock_subledger_row(db, Payable, payable_id)' in source
    assert source.index('_lock_subledger_row(db, Receivable, receivable_id)') < source.index("row.status = 'written_off'")


def test_guard_and_writeoff_use_populate_existing_for_fresh_locked_state():
    guard = (ROOT / 'backend/app/services/settlement_reversal_guard.py').read_text()
    writeoff = (ROOT / 'backend/app/services/writeoff_service.py').read_text()
    assert '.populate_existing()' in guard
    assert '.populate_existing()' in writeoff
