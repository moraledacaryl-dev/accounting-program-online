"""Owner-only journal exception review: scoped evidence and authorization."""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import deps, journal_review
from app.db.database import Base, get_db
from app.models.entities import FinancialAccount, MoneyTransaction


@pytest.fixture
def client_and_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        acc = FinancialAccount(name='Primary Cash', code='AUDIT-JOURNAL-REVIEW', account_type='cash_drawer')
        db.add(acc)
        db.flush()
        for i, source, day, journal_id in [
            (1, 'legacy_import', '2025-01-10', None),
            (2, 'legacy_import', '2025-02-10', None),
            (3, 'beds24', '2026-04-01', None),
            (4, 'legacy_import', '2026-04-01', None),
            (5, 'legacy_import', '2025-01-10', None),
        ]:
            db.add(MoneyTransaction(
                id=i, financial_account_id=acc.id, transaction_date=day,
                direction='in', amount=100 + i, status='posted',
                module='cashbook', category='historic receipt',
                external_source=source, external_id=f'ext-{i}',
                reference_no=f'PAY-{i}', journal_entry_id=journal_id,
            ))
        db.add(MoneyTransaction(
            financial_account_id=acc.id, transaction_date='2025-01-10',
            direction='out', amount=9, status='draft', module='finance',
            external_source='legacy_import', external_id='draft-7',
        ))
        db.commit()
        actor = SimpleNamespace(username='owner', role='owner')
        app = FastAPI()
        app.include_router(journal_review.router, prefix='/reports')
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[deps.get_current_user] = lambda: actor
        with TestClient(app) as client:
            yield client, db, actor
    engine.dispose()


def test_owner_can_page_and_filter_journal_linkage_without_edits(client_and_db):
    client, db, actor = client_and_db
    response = client.get('/reports/journal-linkage-review?limit=2')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'private, no-store'
    body = response.json()
    assert body['count'] == 5
    assert body['total_pages'] == 3
    assert [row['id'] for row in body['items']] == [1, 5]
    assert {row['source']: row['count'] for row in body['source_counts']} == {
        'legacy_import': 4, 'beds24': 1,
    }
    assert body['classification'] == 'unverified_journal_linkage'
    assert all(row['review_status'] == 'unverified' and row['journal_entry_id'] is None
               for row in body['items'])
    assert client.get('/reports/journal-linkage-review?year=2026&source=beds24').json()['count'] == 1
    assert client.get('/reports/journal-linkage-review?year=2025&source=beds24').json()['count'] == 0
    assert len(client.get('/reports/journal-linkage-review?page=3&limit=2').json()['items']) == 1

    all_rows = db.query(MoneyTransaction).order_by(MoneyTransaction.id).all()
    assert len(all_rows) == 6
    assert sum(row.status == 'posted' and row.journal_entry_id is None for row in all_rows) == 5
    assert all(row.journal_entry_id is None for row in all_rows)


def test_review_access_denied_to_non_owner_even_if_reports_view_permission(client_and_db):
    client, _, actor = client_and_db
    actor.role = 'front_desk'
    assert client.get('/reports/journal-linkage-review').status_code == 403
    actor.role = 'accountant'
    assert client.get('/reports/journal-linkage-review').status_code == 403
    actor.role = 'admin'
    assert client.get('/reports/journal-linkage-review').status_code == 200


@pytest.mark.parametrize('query', ['year=20x5', 'page=0', 'limit=0', 'limit=101', 'page=10001'])
def test_journal_review_rejects_invalid_queries(client_and_db, query):
    client, _, _ = client_and_db
    assert client.get('/reports/journal-linkage-review?' + query).status_code == 422


def test_review_router_exposes_get_only():
    assert [route.methods for route in journal_review.router.routes] == [{'GET'}]
