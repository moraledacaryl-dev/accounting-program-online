import inspect

from app.api import cashflow, reconciliations
from app.services.permission_service import ROLE_PERMISSION_PRESETS


def test_reconciliation_reads_use_view_permission_but_mutations_require_manage():
    read_source = inspect.getsource(reconciliations.get_reconciliations)
    assert "require_permissions('cashflow.view')" in read_source
    assert "require_permissions('cashflow.reconcile')" not in read_source

    for endpoint in (
        reconciliations.add_reconciliation,
        reconciliations.edit_reconciliation,
        reconciliations.approve_reconciliation,
        reconciliations.close_reconciliation,
        reconciliations.reverse_reconciliation,
    ):
        assert "require_permissions('cashflow.reconcile')" in inspect.getsource(endpoint)


def test_restaurant_admin_has_only_the_booking_read_dependency_needed_for_room_charge():
    permissions = ROLE_PERMISSION_PRESETS['restaurant_admin']
    assert 'bookings.view' in permissions
    assert 'bookings.create' not in permissions
    assert 'bookings.edit' not in permissions
    assert 'bookings.cancel' not in permissions
    assert 'folios.manage' not in permissions


def test_posted_money_reversal_requires_explicit_reverse_authority_and_direction_scope():
    source = inspect.getsource(cashflow.reverse_transaction)
    assert "require_permissions('money.reverse')" in source
    assert '_transaction_for_direction_auth(db, transaction_id)' in source
    assert '_authorize_cashflow_direction(db, user, current.direction)' in source


def test_read_only_auditor_does_not_gain_mutation_permissions():
    permissions = ROLE_PERMISSION_PRESETS['auditor']
    assert 'cashflow.view' in permissions
    assert 'cash_treasury.view' in permissions
    assert 'cashflow.money_in' not in permissions
    assert 'cashflow.money_out' not in permissions
    assert 'cashflow.transfers' not in permissions
    assert 'cashflow.reconcile' not in permissions
    assert 'money.reverse' not in permissions
