from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_transfer_mutation_service_locks_transfer_and_accounts():
    source = (ROOT / 'backend/app/services/transfer_mutation_service.py').read_text()
    assert 'db.query(AccountTransfer)' in source
    assert '.populate_existing()' in source
    assert source.count('.with_for_update()') >= 2
    assert '.order_by(FinancialAccount.id.asc())' in source
    assert "account_ids.add(int(data['from_account_id']))" in source
    assert "account_ids.add(int(data['to_account_id']))" in source


def test_transfer_api_routes_mutations_through_locking_service():
    source = (ROOT / 'backend/app/api/transfers.py').read_text()
    assert 'from app.services.transfer_mutation_service import approve_transfer, cancel_transfer, update_transfer' in source
    assert 'return update_transfer(db, transfer_id, payload' in source
    assert 'return approve_transfer(db, transfer_id, payload' in source
    assert 'return cancel_transfer(db, transfer_id, payload)' in source


def test_transfer_creation_and_reversal_keep_deterministic_account_locking():
    source = (ROOT / 'backend/app/services/cashflow_service.py').read_text()
    assert source.count('.order_by(FinancialAccount.id.asc())') >= 2
    assert source.count('.with_for_update()') >= 2
