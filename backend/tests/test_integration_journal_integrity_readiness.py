"""Connected-app journals obey the same ledger rules as manual journals."""
from decimal import Decimal
from unittest.mock import MagicMock
import json

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db.database import Base
from app.models.entities import ChartAccount, IntegrationReviewItem, JournalEntry, JournalLine
from app.schemas.integration_review import IntegrationReviewCreate, IntegrationReviewDecision
from app.services.integration_review_service import accept_item, create_review_item, validate_review_payload


def proposal(**overrides):
    data = dict(
        source_app='inventory', source_event_id='isolated-journal-integrity',
        source_entity_type='stock_document', financial_effect='journal_only', amount=100,
        proposed_journal={'lines': [
            {'account_code': '1000', 'debit': 100, 'credit': 0},
            {'account_code': '4000', 'debit': 0, 'credit': 100},
        ]},
    )
    data.update(overrides)
    return IntegrationReviewCreate(**data)


@pytest.fixture
def db():
    engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        session.add_all([
            ChartAccount(code='1000', name='Cash', account_type='asset', is_active=True),
            ChartAccount(code='4000', name='Revenue', account_type='income', is_active=True),
        ])
        session.commit()
        yield session
    engine.dispose()


def test_subcent_imbalance_cannot_enter_the_reviewable_queue(db):
    item = proposal(proposed_journal={'lines': [
        {'account_code': '1000', 'debit': '100.004', 'credit': 0},
        {'account_code': '4000', 'debit': 0, 'credit': 100},
    ]})
    result = create_review_item(db, item)
    assert result['status'] == 'validation_failed'
    assert any('balance' in e.lower() for e in result['validation']['errors'])
    assert db.query(JournalEntry).count() == 0


@pytest.mark.parametrize('missing', [False, True], ids=['inactive-account', 'unknown-account'])
def test_acceptance_revalidates_active_chart_accounts_without_posting(db, missing):
    item = create_review_item(db, proposal())
    account = db.query(ChartAccount).filter_by(code='4000').one()
    if missing:
        db.delete(account)
    else:
        account.is_active = False
    db.commit()
    with pytest.raises(ValueError, match='active chart accounts'):
        accept_item(db, item['id'], IntegrationReviewDecision(transaction_date='2026-10-25'), 'isolated-reviewer')
    db.rollback()
    assert db.query(JournalEntry).count() == 0
    assert db.query(JournalLine).count() == 0
    assert db.get(IntegrationReviewItem, item['id']).status == 'ready_for_review'


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf')])
def test_nonfinite_event_amount_and_paid_amount_rejected_at_schema_boundary(value):
    with pytest.raises(ValidationError):
        proposal(amount=value)
    with pytest.raises(ValidationError):
        IntegrationReviewDecision(actual_amount_paid=value)


@pytest.mark.parametrize('field', ['proposed_journal', 'proposed_links', 'payload'])
def test_nonfinite_nested_json_is_rejected_before_persistence(field):
    with pytest.raises(ValidationError, match='valid JSON'):
        proposal(**{field: {'invalid': float('nan')}})


@pytest.mark.parametrize('value', ['NaN', 'Infinity', float('nan'), float('inf')])
def test_invalid_http_amount_returns_private_safe_422_without_intake(db, value):
    from app.main import app
    from app.api.integration_review import require_service_integration_key
    from app.db.database import get_db

    overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_service_integration_key] = lambda: True
    try:
        payload = proposal().model_dump()
        payload['amount'] = value
        client = TestClient(app, raise_server_exceptions=False)
        try:
            response = client.post('/api/integration-review/service-intake', content=json.dumps(payload), headers={'Content-Type': 'application/json'})
        finally:
            client.close()
        assert response.status_code == 422
        errors = response.json()['detail']
        assert any(error['loc'][-1] == 'amount' for error in errors)
        assert all(set(error) == {'loc', 'msg', 'type'} for error in errors)
        assert db.query(IntegrationReviewItem).count() == 0
        assert db.query(JournalEntry).count() == 0
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(overrides)


@pytest.mark.parametrize('value', ['not-money', float('nan'), float('inf')])
def test_legacy_row_amount_is_revalidated_without_crashing(value):
    payload = proposal().model_dump()
    payload['amount'] = value
    result = validate_review_payload(MagicMock(), payload)
    assert result['valid'] is False
    assert any('finite' in error for error in result['errors'])


@pytest.mark.parametrize('lines', [
    [None, {'account_code': '4000', 'credit': 100}],
    [{'account_code': '1000', 'debit': 'not-a-number'}, {'account_code': '4000', 'credit': 100}],
    [{'account_code': '1000', 'debit': 'Infinity'}, {'account_code': '4000', 'credit': 'Infinity'}],
    [{'account_code': '1000', 'debit': 'NaN'}, {'account_code': '4000', 'credit': 'NaN'}],
])
def test_malformed_journal_proposals_produce_validation_findings(lines):
    result = validate_review_payload(MagicMock(), proposal(proposed_journal={'lines': lines}))
    assert result['valid'] is False
    assert result['errors']


def test_valid_four_decimal_journal_posts_once_with_exact_values(db):
    item = create_review_item(db, proposal(amount=100.004, proposed_journal={'lines': [
        {'account_code': '1000', 'debit': '100.004', 'credit': 0},
        {'account_code': '4000', 'debit': 0, 'credit': '100.004'},
    ]}))
    decision = IntegrationReviewDecision(transaction_date='2026-10-25')
    first = accept_item(db, item['id'], decision, 'isolated-reviewer')
    second = accept_item(db, item['id'], decision, 'isolated-reviewer')
    assert first['accepted_journal_entry_id'] == second['accepted_journal_entry_id']
    lines = db.query(JournalLine).all()
    assert db.query(JournalEntry).count() == 1 and len(lines) == 2
    assert sum(x.debit for x in lines) == sum(x.credit for x in lines) == Decimal('100.0040')
