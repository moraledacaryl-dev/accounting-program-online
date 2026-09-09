from pathlib import Path


def test_supplier_credit_reversal_route_and_permission_contract():
    source = Path('backend/app/api/supplier_credits.py').read_text()
    assert "@router.post('/applications/{application_id}/reverse')" in source
    assert "require_permissions('cashflow.money_out')" in source
    assert 'SupplierCreditReversePayload' in source
    assert 'SupplierCreditReversalIdempotencyConflict' in source


def test_supplier_credit_reversal_ui_contract():
    panel = Path('frontend/components/cashflow/SupplierCreditsPanel.js').read_text()
    api = Path('frontend/lib/supplierCreditApi.js').read_text()
    assert 'Credit Application History' in panel
    assert 'Reverse Application' in panel
    assert 'reverseSupplierCreditApplication' in panel
    assert '/reverse' in api
