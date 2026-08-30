from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import records


class FakeDB:
    pass


def user(role='front_desk'):
    return SimpleNamespace(role=role, username='scope-test')


def test_front_desk_cannot_read_payroll_generic_records(monkeypatch):
    monkeypatch.setattr(records, 'get_user_permission_keys', lambda db, actor: {'bookings.view', 'guests.view'})
    monkeypatch.setattr(records, 'list_records', lambda *args, **kwargs: pytest.fail('unauthorized query reached record store'))

    with pytest.raises(HTTPException) as exc:
        records.module_records('payroll', db=FakeDB(), user=user(), limit=200, search=None)

    assert exc.value.status_code == 403


def test_front_desk_can_read_rooms_generic_records(monkeypatch):
    monkeypatch.setattr(records, 'get_user_permission_keys', lambda db, actor: {'bookings.view'})
    monkeypatch.setattr(records, 'list_records', lambda *args, **kwargs: ['allowed'])

    assert records.module_records('rooms', db=FakeDB(), user=user(), limit=200, search=None) == ['allowed']


def test_single_record_checks_its_module_before_serializing(monkeypatch):
    monkeypatch.setattr(records, 'get_user_permission_keys', lambda db, actor: {'bookings.view'})
    monkeypatch.setattr(records, 'get_record_obj', lambda db, record_id: SimpleNamespace(module_slug='payroll'))
    monkeypatch.setattr(records, 'get_record', lambda *args, **kwargs: pytest.fail('unauthorized record was serialized'))

    with pytest.raises(HTTPException) as exc:
        records.single_record(42, db=FakeDB(), user=user())

    assert exc.value.status_code == 403


def test_owner_retains_cross_module_record_read(monkeypatch):
    monkeypatch.setattr(records, 'get_user_permission_keys', lambda *args, **kwargs: pytest.fail('owner should bypass permission lookup'))
    monkeypatch.setattr(records, 'list_records', lambda *args, **kwargs: ['owner-visible'])

    assert records.module_records('payroll', db=FakeDB(), user=user('owner'), limit=200, search=None) == ['owner-visible']


def test_unknown_record_module_fails_closed(monkeypatch):
    monkeypatch.setattr(records, 'get_user_permission_keys', lambda *args, **kwargs: {'dashboard.view'})

    with pytest.raises(HTTPException) as exc:
        records.module_meta('unknown-module', db=FakeDB(), user=user())

    assert exc.value.status_code == 404
