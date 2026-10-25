"""Financial review actions require their dedicated server-side permission."""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import deps, financial_accounts, integration_review
from app.db.database import Base, get_db


@pytest.fixture
def api(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        actor = SimpleNamespace(username='isolated-reviewer', role='payroll_admin', permissions=set())
        app = FastAPI()
        app.include_router(integration_review.router, prefix='/integration-review')
        app.include_router(financial_accounts.router, prefix='/financial-accounts')
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[deps.get_current_user] = lambda: actor
        monkeypatch.setattr(deps, 'get_user_permission_keys', lambda _db, user: user.permissions)
        with TestClient(app) as client:
            yield client, actor
    engine.dispose()


@pytest.mark.parametrize('role,permissions', [
    ('payroll_admin', {'approvals.act'}),
    ('accounting_operator', {'integrations.manage'}),
    ('cashier', {'review_inbox.view'}),
    ('auditor', {'integrations.view', 'approvals.view'}),
])
@pytest.mark.parametrize('action', ['accept', 'reject'])
def test_broader_workflow_permissions_cannot_make_financial_review_decisions(api, role, permissions, action):
    client, actor = api
    actor.role, actor.permissions = role, permissions
    payload = {'transaction_date': '2026-10-25'} if action == 'accept' else {'reason': 'isolated review'}
    response = client.post(f'/integration-review/999/{action}', json=payload)
    assert response.status_code == 403


@pytest.mark.parametrize('role,permissions', [
    ('accounting_admin', {'review_inbox.act'}),
    ('manager', {'review_inbox.act'}),
    ('owner', set()),
])
@pytest.mark.parametrize('action', ['accept', 'reject'])
def test_dedicated_review_permission_passes_authorization(api, role, permissions, action):
    client, actor = api
    actor.role, actor.permissions = role, permissions
    payload = {'transaction_date': '2026-10-25'} if action == 'accept' else {'reason': 'isolated review'}
    response = client.post(f'/integration-review/999/{action}', json=payload)
    assert response.status_code == 400
    assert response.json()['detail'] == 'Review item not found.'


@pytest.mark.parametrize('role,permissions,expected', [
    ('payroll_admin', {'approvals.act', 'integrations.view'}, 403),
    ('reviewer', {'review_inbox.act'}, 200),
    ('accounting_admin', {'cashflow.view'}, 200),
])
def test_account_choices_are_available_only_to_cashflow_or_decision_reviewer(api, role, permissions, expected):
    client, actor = api
    actor.role, actor.permissions = role, permissions
    response = client.get('/financial-accounts/')
    assert response.status_code == expected
