"""Reject malformed dates and amounts before a payout can touch accounting."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import channel, channel_reconciliation, deps
from app.api.channel_reconciliation import PayoutReconcileBatch
from app.db.database import Base, get_db
from app.models.channel_payout_reconciliation import ChannelPayoutBookingLink
from app.models.entities import Booking, BookingChannel, ChannelPayout
from app.schemas.common import ChannelPayoutCreate, ChannelPayoutSettle, ChannelPayoutUpdate


@pytest.mark.parametrize('model,payload', [
    (ChannelPayoutCreate, {'channel': 'Synthetic', 'gross_amount': -1}),
    (ChannelPayoutCreate, {'channel': 'Synthetic', 'gross_amount': 'NaN'}),
    (ChannelPayoutCreate, {'channel': 'Synthetic', 'commission_amount': 'Infinity'}),
    (ChannelPayoutUpdate, {'net_amount': -1}),
    (ChannelPayoutUpdate, {'net_amount': 'NaN'}),
    (ChannelPayoutCreate, {'channel': 'Synthetic', 'expected_payout_date': '2026-02-30'}),
    (ChannelPayoutUpdate, {'actual_payout_date': '2026-10-27T09:00:00'}),
    (ChannelPayoutSettle, {'actual_payout_date': 'not-a-date'}),
    (PayoutReconcileBatch, {
        'channel_id': 1, 'actual_payout_date': '2026-02-30',
        'items': [{'booking_id': 1, 'expected_amount': '10', 'actual_amount': '10'}],
    }),
])
def test_payout_models_reject_invalid_amounts_and_dates(model, payload):
    with pytest.raises(ValidationError):
        model(**payload)


def test_optional_payout_dates_normalize_empty_input():
    assert ChannelPayoutCreate(channel='Synthetic', expected_payout_date='').expected_payout_date is None
    assert ChannelPayoutUpdate(actual_payout_date='').actual_payout_date is None
    assert ChannelPayoutSettle(actual_payout_date='').actual_payout_date is None
    assert ChannelPayoutCreate(channel='Synthetic', actual_payout_date='2026-10-27').actual_payout_date == '2026-10-27'


@pytest.mark.parametrize('method,path,payload', [
    ('post', '/channel/payouts', {'channel': 'Synthetic', 'gross_amount': 'NaN'}),
    ('put', '/channel/payouts/999', {'commission_amount': -1}),
    ('post', '/channel/payouts/999/settle', {'actual_payout_date': '2026-02-30'}),
    ('post', '/channel-reconciliation/reconcile', {
        'channel_id': 999, 'actual_payout_date': 'invalid',
        'items': [{'booking_id': 999, 'expected_amount': '10', 'actual_amount': '10'}],
    }),
])
def test_invalid_payout_request_returns_422_without_mutation(monkeypatch, method, path, payload):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    try:
        with sessionmaker(bind=engine)() as db:
            actor = SimpleNamespace(username='isolated-cashier', role='cashier', permissions={'cashflow.money_in'})
            app = FastAPI()
            app.include_router(channel.router, prefix='/channel')
            app.include_router(channel_reconciliation.router, prefix='/channel-reconciliation')
            app.dependency_overrides[get_db] = lambda: db
            app.dependency_overrides[deps.get_current_user] = lambda: actor
            monkeypatch.setattr(deps, 'get_user_permission_keys', lambda _db, user: user.permissions)
            with TestClient(app) as client:
                response = getattr(client, method)(path, json=payload)
            assert response.status_code == 422
            assert db.query(ChannelPayout).count() == 0
    finally:
        engine.dispose()


def test_valid_payout_can_be_created_updated_and_settled_in_isolation(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    try:
        with sessionmaker(bind=engine)() as db:
            actor = SimpleNamespace(username='isolated-cashier', role='cashier', permissions={'cashflow.money_in'})
            app = FastAPI()
            app.include_router(channel.router, prefix='/channel')
            app.dependency_overrides[get_db] = lambda: db
            app.dependency_overrides[deps.get_current_user] = lambda: actor
            monkeypatch.setattr(deps, 'get_user_permission_keys', lambda _db, user: user.permissions)
            with TestClient(app) as client:
                created = client.post('/channel/payouts', json={
                    'channel': 'Synthetic', 'gross_amount': 100,
                    'commission_amount': 10, 'net_amount': 90,
                    'expected_payout_date': '2026-10-27',
                })
                assert created.status_code == 200
                payout_id = created.json()['id']
                updated = client.put(f'/channel/payouts/{payout_id}', json={
                    'net_amount': 85, 'notes': 'isolated adjustment',
                })
                assert updated.status_code == 200
                settled = client.post(f'/channel/payouts/{payout_id}/settle', json={
                    'actual_payout_date': '2026-10-28',
                })
                assert settled.status_code == 200
            row = db.get(ChannelPayout, payout_id)
            assert row.net_amount == 85
            assert row.actual_payout_date == '2026-10-28'
            assert row.status == 'paid'
    finally:
        engine.dispose()


def test_repeated_batch_payout_returns_conflict_without_second_record(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    try:
        with sessionmaker(bind=engine)() as db:
            db.add(BookingChannel(id=1, code='SYNTH', name='Synthetic channel', is_active=True))
            db.add(Booking(id=1, guest_name='Synthetic guest', channel_id=1,
                           status='confirmed', check_in='2026-10-27', check_out='2026-10-28',
                           gross_amount=100))
            db.commit()
            actor = SimpleNamespace(username='isolated-cashier', role='cashier', permissions={'cashflow.money_in'})
            app = FastAPI()
            app.include_router(channel_reconciliation.router, prefix='/channel-reconciliation')
            app.dependency_overrides[get_db] = lambda: db
            app.dependency_overrides[deps.get_current_user] = lambda: actor
            monkeypatch.setattr(deps, 'get_user_permission_keys', lambda _db, user: user.permissions)
            payload = {
                'channel_id': 1, 'actual_payout_date': '2026-10-28',
                'auto_post_accounting': False,
                'items': [{'booking_id': 1, 'expected_amount': '100.00', 'actual_amount': '100.00'}],
            }
            with TestClient(app) as client:
                assert client.post('/channel-reconciliation/reconcile', json=payload).status_code == 200
                replay = client.post('/channel-reconciliation/reconcile', json=payload)
            assert replay.status_code == 409
            assert 'already marked paid' in replay.json()['detail']
            assert db.query(ChannelPayoutBookingLink).count() == 1
            assert db.query(ChannelPayout).count() == 1
    finally:
        engine.dispose()
