from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.api import records, journals, deps, approvals
from app.db.database import Base, get_db
from app.models.entities import Record


@pytest.fixture
def api(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    row = Record(module_slug='payroll', module_name='Payroll', category='Payroll', bucket='Wages', item='Wages', workflow_status='draft', amount=100, direction='expense', transaction_date='2026-09-07')
    db.add(row); db.commit()
    actor = SimpleNamespace(username='booking-editor', role='front_desk')
    app = FastAPI()
    app.include_router(records.router, prefix='/records')
    app.include_router(journals.router, prefix='/journals')
    app.include_router(approvals.router, prefix='/approvals')
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[deps.get_current_user] = lambda: actor
    monkeypatch.setattr(records, 'get_user_permission_keys', lambda *_: {'bookings.edit'})
    monkeypatch.setattr(deps, 'get_user_permission_keys', lambda *_: {'bookings.edit'})
    with TestClient(app) as client:
        yield client, row.id, actor
    db.close(); engine.dispose()


@pytest.mark.parametrize('method,path,payload', [
    ('put', '/records/single/{id}', {'amount': 999}),
    ('put', '/records/single/{id}', {'workflow_status': 'approved'}),
    ('delete', '/records/single/{id}', None),
    ('post', '/records/single/{id}/approve', {'approved': True}),
    ('post', '/approvals/records/{id}/approve', None),
    ('post', '/records/payroll/records', {'category': 'Payroll', 'bucket': 'Wages', 'item': 'Wages', 'amount': 99, 'direction': 'expense', 'workflow_status': 'approved'}),
])
def test_booking_role_cannot_mutate_payroll_over_http(api, method, path, payload):
    client, record_id, _ = api
    response = client.request(method, path.format(id=record_id), json=payload)
    assert response.status_code == 403


def test_empty_posted_journal_rejected_at_http_boundary(api):
    client, _, actor = api
    actor.role = 'owner'
    response = client.post('/journals/entries', json={'status': 'posted', 'lines': []})
    assert response.status_code == 422
