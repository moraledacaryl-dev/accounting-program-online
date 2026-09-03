from pathlib import Path


def test_money_transaction_mutation_service_locks_transaction_row():
    root = Path(__file__).resolve().parents[1]
    source = (root / 'app/services/money_transaction_mutation_service.py').read_text()

    assert 'db.query(MoneyTransaction)' in source
    assert '.populate_existing()' in source
    assert '.with_for_update()' in source
    assert '_lock_money_transaction(db, tx_id)' in source


def test_cashflow_routes_use_locked_mutation_boundary():
    root = Path(__file__).resolve().parents[1]
    source = (root / 'app/api/cashflow.py').read_text()

    assert 'from app.services.money_transaction_mutation_service import (' in source
    assert 'approve_money_transaction,' in source
    assert 'cancel_money_transaction,' in source
    assert 'update_money_transaction,' in source
