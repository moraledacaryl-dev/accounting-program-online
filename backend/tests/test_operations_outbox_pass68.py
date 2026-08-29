from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.settings import settings
from app.db.database import Base
from app.models.operations_outbox import OperationsOutboxEvent
from app.services import operations_integration
from app.services.operations_outbox_service import (
    OUTBOX_MAX_ATTEMPTS,
    claim_next_operations_event,
    enqueue_operations_event,
    mark_operations_event_delivered,
    mark_operations_event_failed,
    operations_outbox_status,
)


def make_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    return Session()


def enqueue_sample(db, event_id='pass68:event:1'):
    return enqueue_operations_event(
        db,
        event_id=event_id,
        event_type='payable.due',
        title='Payable due',
        summary='Durable delivery test',
        subject_type='payable',
        subject_id=1,
        priority='High',
        payload={'balance_due': 125.0},
    )


def test_outbox_enqueue_rolls_back_with_business_transaction(monkeypatch):
    monkeypatch.setattr(settings, 'operations_integration_enabled', True)
    db = make_session()

    enqueue_sample(db)
    assert db.query(OperationsOutboxEvent).count() == 1

    db.rollback()
    assert db.query(OperationsOutboxEvent).count() == 0


def test_outbox_enqueue_is_idempotent_by_event_id(monkeypatch):
    monkeypatch.setattr(settings, 'operations_integration_enabled', True)
    db = make_session()

    first = enqueue_sample(db)
    second = enqueue_sample(db)
    db.commit()

    assert first.id == second.id
    assert db.query(OperationsOutboxEvent).count() == 1
    assert second.status == 'pending'


def test_claim_retry_and_delivery_lifecycle(monkeypatch):
    monkeypatch.setattr(settings, 'operations_integration_enabled', True)
    db = make_session()
    enqueue_sample(db)
    db.commit()

    claimed = claim_next_operations_event(db, now=datetime(2026, 8, 29, 10, 0, tzinfo=timezone.utc))
    assert claimed is not None
    assert claimed.status == 'processing'
    assert claimed.attempt_count == 1

    failed = mark_operations_event_failed(
        db,
        claimed.id,
        error_message='temporary outage',
        http_status=503,
        now=datetime(2026, 8, 29, 10, 0, tzinfo=timezone.utc),
    )
    assert failed.status == 'retry'
    assert failed.next_attempt_at is not None
    assert failed.last_http_status == 503

    failed.next_attempt_at = datetime(2026, 8, 29, 10, 0, tzinfo=timezone.utc)
    db.add(failed)
    db.commit()

    claimed_again = claim_next_operations_event(
        db,
        now=datetime(2026, 8, 29, 10, 1, tzinfo=timezone.utc),
    )
    assert claimed_again.id == claimed.id
    assert claimed_again.attempt_count == 2

    delivered = mark_operations_event_delivered(
        db,
        claimed_again.id,
        http_status=200,
        now=datetime(2026, 8, 29, 10, 1, tzinfo=timezone.utc),
    )
    assert delivered.status == 'delivered'
    assert delivered.delivered_at is not None
    assert delivered.next_attempt_at is None


def test_max_attempts_dead_letters_event(monkeypatch):
    monkeypatch.setattr(settings, 'operations_integration_enabled', True)
    db = make_session()
    row = enqueue_sample(db)
    row.attempt_count = OUTBOX_MAX_ATTEMPTS
    row.status = 'processing'
    db.add(row)
    db.commit()

    dead = mark_operations_event_failed(
        db,
        row.id,
        error_message='permanent failure',
        http_status=400,
    )
    assert dead.status == 'dead'
    assert dead.next_attempt_at is None
    assert dead.last_http_status == 400


def test_outbox_status_surfaces_pending_and_dead(monkeypatch):
    monkeypatch.setattr(settings, 'operations_integration_enabled', True)
    db = make_session()
    pending = enqueue_sample(db, 'pass68:pending')
    dead = enqueue_sample(db, 'pass68:dead')
    dead.status = 'dead'
    dead.attempt_count = OUTBOX_MAX_ATTEMPTS
    db.add_all([pending, dead])
    db.commit()

    status = operations_outbox_status(db)
    assert status['enabled'] is True
    assert status['pending'] == 1
    assert status['dead'] == 1
    assert status['healthy'] is False


def test_due_date_uses_manila_business_clock(monkeypatch):
    monkeypatch.setattr(operations_integration, 'business_today', lambda: '2026-08-29')

    assert operations_integration.is_due_or_overdue('2026-08-29') is True
    assert operations_integration.is_due_or_overdue('2026-08-30') is False


def test_best_effort_background_publisher_cannot_reappear():
    backend_root = Path(__file__).resolve().parents[1]
    payables = (backend_root / 'app/api/payables.py').read_text(encoding='utf-8')
    integration = (backend_root / 'app/services/operations_integration.py').read_text(encoding='utf-8')

    assert 'BackgroundTasks' not in payables
    assert 'publish_operations_event' not in payables
    assert 'publish_operations_event' not in integration
    assert 'enqueue_operations_event' in payables
