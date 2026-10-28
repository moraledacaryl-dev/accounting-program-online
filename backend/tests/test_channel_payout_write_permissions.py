"""A report reader may inspect OTA payouts without recording financial changes."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import channel, channel_reconciliation, deps
from app.db.database import Base, get_db
from app.models.entities import ChannelPayout


@pytest.fixture
def api(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        actor = SimpleNamespace(username='isolated-auditor', role='auditor', permissions={'reports.view'})
        app = FastAPI()
        app.include_router(channel.router, prefix='/channel')
        app.include_router(channel_reconciliation.router, prefix='/channel-reconciliation')
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[deps.get_current_user] = lambda: actor
        monkeypatch.setattr(deps, 'get_user_permission_keys', lambda _db, user: user.permissions)
        with TestClient(app) as client:
            yield client, actor, db
    engine.dispose()


WRITE_REQUESTS = [
    ('post', '/channel/payouts', {'channel': 'Isolated channel', 'gross_amount': 10}),
    ('put', '/channel/payouts/999', {'notes': 'isolated update'}),
    ('post', '/channel/payouts/999/settle', {'actual_payout_date': '2026-10-27'}),
    ('post', '/channel-reconciliation/reconcile', {
        'channel_id': 999, 'actual_payout_date': '2026-10-27',
        'items': [{'booking_id': 999, 'expected_amount': '10.00', 'actual_amount': '10.00'}],
    }),
]


@pytest.mark.parametrize('method,path,payload', WRITE_REQUESTS)
def test_report_reader_cannot_mutate_channel_payouts(api, method, path, payload):
    client, actor, db = api
    actor.permissions = {'reports.view', 'bookings.view', 'cashflow.view'}
    response = getattr(client, method)(path, json=payload)
    assert response.status_code == 403
    assert db.query(ChannelPayout).count() == 0


@pytest.mark.parametrize('method,path,payload', WRITE_REQUESTS)
@pytest.mark.parametrize('permission', ['cashflow.money_in', 'cashflow.money_out'])
def test_existing_cashflow_writers_pass_authorization(api, method, path, payload, permission):
    client, actor, _db = api
    actor.role = 'cashier'
    actor.permissions = {permission}
    # The disposable missing record/channel must be reached, proving the
    # request passed permission checks without recording a real payout.
    if path == '/channel/payouts':
        payload = {**payload, 'channel_id': 999, 'channel': None}
    response = getattr(client, method)(path, json=payload)
    assert response.status_code in {400, 404}


def test_report_reader_retains_payout_history_access(api):
    client, _actor, _db = api
    assert client.get('/channel/payouts').status_code == 200
    assert client.get('/channel-reconciliation/history').status_code == 200
    assert client.get('/channel-reconciliation/history?before_date=&before_id=7').status_code == 200
    assert client.get('/channel-reconciliation/history?before_id=7').status_code == 400
    assert client.get('/channel-reconciliation/history?limit=501').status_code == 422
