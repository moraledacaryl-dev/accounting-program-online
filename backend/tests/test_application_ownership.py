from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.deps import (
    _enforce_external_ownership,
    enforce_external_record_ownership,
    external_owner_for_request,
)
from app.core.settings import settings


def make_request(method: str, path: str) -> Request:
    return Request({
        'type': 'http',
        'method': method,
        'scheme': 'https',
        'server': ('accounting.hiddenoasis.app', 443),
        'client': ('127.0.0.1', 10000),
        'root_path': '',
        'path': path,
        'raw_path': path.encode(),
        'query_string': b'',
        'headers': [],
    })


def human(username='owner'):
    return SimpleNamespace(username=username, role='owner')


def integration_user():
    return SimpleNamespace(username=settings.integration_username, role='pos_integration')


@pytest.mark.parametrize(
    ('path', 'owner'),
    [
        ('/api/stock/items', 'Inventory & Procurement'),
        ('/api/suppliers', 'Inventory & Procurement'),
        ('/api/purchase-requests/4/status', 'Inventory & Procurement'),
        ('/api/purchase-orders/7', 'Inventory & Procurement'),
        ('/api/receiving/9/status', 'Inventory & Procurement'),
        ('/api/setup-imports', 'Inventory & Procurement'),
        ('/api/menu/sales', 'POS Cloud'),
        ('/api/records/inventory/records', 'Inventory & Procurement'),
        ('/api/records/procurement/records', 'Inventory & Procurement'),
        ('/api/records/restaurant/records', 'POS Cloud'),
    ],
)
def test_external_owner_inventory_covers_operational_mutation_paths(path, owner):
    assert external_owner_for_request(make_request('POST', path)) == owner


def test_safe_reads_remain_available_to_human_users():
    request = make_request('GET', '/api/stock/items')
    _enforce_external_ownership(request, human())


def test_human_direct_mutation_is_blocked_before_business_logic():
    request = make_request('POST', '/api/stock/items')
    with pytest.raises(HTTPException) as exc_info:
        _enforce_external_ownership(request, human())
    assert exc_info.value.status_code == 409
    assert 'Inventory & Procurement owns this operational workflow' in exc_info.value.detail


def test_pos_human_mutation_is_blocked():
    request = make_request('POST', '/api/menu/sales')
    with pytest.raises(HTTPException) as exc_info:
        _enforce_external_ownership(request, human('admin'))
    assert exc_info.value.status_code == 409
    assert 'POS Cloud owns this operational workflow' in exc_info.value.detail


def test_trusted_integration_identity_can_write_external_owned_routes(monkeypatch):
    monkeypatch.setattr(settings, 'integration_username', 'service-integration')
    request = make_request('POST', '/api/menu/sales')
    _enforce_external_ownership(
        request,
        SimpleNamespace(username='service-integration', role='pos_integration'),
    )


def test_accounting_owned_mutations_are_not_affected():
    request = make_request('POST', '/api/cashflow/transactions')
    _enforce_external_ownership(request, human())


def test_existing_external_record_cannot_be_mutated_by_human():
    with pytest.raises(HTTPException) as exc_info:
        enforce_external_record_ownership('inventory', human())
    assert exc_info.value.status_code == 409


def test_existing_external_record_can_be_mutated_by_integration(monkeypatch):
    monkeypatch.setattr(settings, 'integration_username', 'service-integration')
    enforce_external_record_ownership(
        'inventory',
        SimpleNamespace(username='service-integration', role='pos_integration'),
    )


def test_accounting_owned_generic_record_remains_mutable_by_human():
    enforce_external_record_ownership('assets', human())
