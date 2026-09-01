import inspect

import pytest
from fastapi import HTTPException

from app.api import cashflow


class _User:
    def __init__(self, role='staff'):
        self.role = role


def test_money_in_permission_cannot_authorize_money_out(monkeypatch):
    monkeypatch.setattr(cashflow, 'get_user_permission_keys', lambda db, user: {'cashflow.money_in'})
    user = _User()

    cashflow._authorize_cashflow_direction(None, user, 'in')

    with pytest.raises(HTTPException) as exc:
        cashflow._authorize_cashflow_direction(None, user, 'out')
    assert exc.value.status_code == 403
    assert 'cashflow.money_out' in str(exc.value.detail)


def test_money_out_permission_cannot_authorize_money_in(monkeypatch):
    monkeypatch.setattr(cashflow, 'get_user_permission_keys', lambda db, user: {'cashflow.money_out'})
    user = _User()

    cashflow._authorize_cashflow_direction(None, user, 'out')

    with pytest.raises(HTTPException) as exc:
        cashflow._authorize_cashflow_direction(None, user, 'in')
    assert exc.value.status_code == 403
    assert 'cashflow.money_in' in str(exc.value.detail)


def test_owner_and_admin_bypass_direction_permission_lookup(monkeypatch):
    def should_not_run(db, user):
        raise AssertionError('owner/admin should not need permission lookup')

    monkeypatch.setattr(cashflow, 'get_user_permission_keys', should_not_run)
    for role in ('owner', 'admin'):
        cashflow._authorize_cashflow_direction(None, _User(role), 'in')
        cashflow._authorize_cashflow_direction(None, _User(role), 'out')


def test_invalid_direction_fails_closed(monkeypatch):
    monkeypatch.setattr(cashflow, 'get_user_permission_keys', lambda db, user: {'cashflow.money_in', 'cashflow.money_out'})

    with pytest.raises(HTTPException) as exc:
        cashflow._authorize_cashflow_direction(None, _User(), 'sideways')
    assert exc.value.status_code == 400


def test_all_money_transaction_mutations_apply_direction_scope():
    create_source = inspect.getsource(cashflow.add_transaction)
    update_source = inspect.getsource(cashflow.edit_transaction)

    assert '_authorize_cashflow_direction(db, user, payload.direction)' in create_source
    assert '_transaction_for_direction_auth(db, transaction_id)' in update_source
    assert '_authorize_cashflow_direction(db, user, current.direction)' in update_source
    assert '_authorize_cashflow_direction(db, user, payload.direction)' in update_source

    for endpoint in (
        cashflow.remove_transaction,
        cashflow.approve_transaction,
        cashflow.cancel_transaction,
        cashflow.reverse_transaction,
    ):
        source = inspect.getsource(endpoint)
        assert '_transaction_for_direction_auth(db, transaction_id)' in source
        assert '_authorize_cashflow_direction(db, user, current.direction)' in source
