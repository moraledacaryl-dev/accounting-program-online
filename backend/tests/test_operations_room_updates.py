import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.settings import settings
from app.db.database import Base
from app.models.entities import Booking
from app.models.operations_outbox import OperationsOutboxEvent
from app.services.operations_room_updates import enqueue_room_update


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setattr(settings, 'operations_integration_enabled', True)
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, autoflush=False)() as session:
        yield session
    engine.dispose()


def test_repeated_snapshot_is_deduplicated_but_returning_state_has_new_revision(db):
    booking = Booking(guest_name='PRIVATE GUEST', room_name='PRIVATE TEXT',
        check_in='2026-11-02', check_out='2026-11-03', status='confirmed',
        gross_amount=98765, deposit_amount=7654, external_source='beds24')
    db.add(booking)
    first = enqueue_room_update(db, booking)
    assert first is not None
    assert enqueue_room_update(db, booking).id == first.id
    booking.status = 'checked_out'
    second = enqueue_room_update(db, booking)
    booking.status = 'confirmed'
    third = enqueue_room_update(db, booking)
    assert first.id < second.id < third.id
    assert db.query(OperationsOutboxEvent).count() == 3
    for row in (first, second, third):
        envelope = json.loads(row.envelope_json)
        assert envelope['payload']['revision'] == row.id
        assert set(envelope['payload']) == {'booking_id','room_id','check_in','check_out','status','origin','revision'}
        assert 'PRIVATE' not in row.envelope_json and '98765' not in row.envelope_json


def test_business_change_and_outbox_are_one_transaction(db):
    booking = Booking(guest_name='PRIVATE', room_name='', status='checked_out')
    db.add(booking)
    enqueue_room_update(db, booking)
    db.rollback()
    assert db.query(Booking).count() == 0
    assert db.query(OperationsOutboxEvent).count() == 0


def test_disabled_integration_does_not_queue(db, monkeypatch):
    monkeypatch.setattr(settings, 'operations_integration_enabled', False)
    booking = Booking(guest_name='PRIVATE', room_name='', status='confirmed')
    db.add(booking)
    assert enqueue_room_update(db, booking) is None
    assert db.query(OperationsOutboxEvent).count() == 0


def test_accounting_booking_mutations_publish_the_actual_saved_status(db):
    from app.schemas.common import BookingCreate, BookingUpdate
    from app.services.hospitality_service import create_booking_with_accounting, update_booking_with_accounting
    created = create_booking_with_accounting(db, BookingCreate(guest_name='PRIVATE', room_name='Solace',
        check_in='2026-11-02', check_out='2026-11-03', auto_post_accounting=False))
    update_booking_with_accounting(db, created['id'], BookingUpdate(status='checked_out', auto_post_accounting=False))
    rows = db.query(OperationsOutboxEvent).order_by(OperationsOutboxEvent.id).all()
    assert [json.loads(row.envelope_json)['payload']['status'] for row in rows] == ['confirmed', 'checked_out']


def test_beds24_cancellation_worker_queues_status_without_financial_changes(db):
    from app.services.beds24_cancellation_service import apply_beds24_cancellation
    booking = Booking(guest_name='PRIVATE', room_name='Solace', external_source='beds24',
        external_booking_id='test-55', status='confirmed', gross_amount=9000, deposit_amount=2000)
    db.add(booking)
    db.commit()
    apply_beds24_cancellation(db, {'id': 'test-55', 'status': 'cancelled'})
    db.commit()
    envelope = json.loads(db.query(OperationsOutboxEvent).one().envelope_json)
    assert envelope['payload']['status'] == 'cancelled'
    assert booking.gross_amount == 9000 and booking.deposit_amount == 2000
