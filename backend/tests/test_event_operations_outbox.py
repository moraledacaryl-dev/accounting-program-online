"""Confirmed event bookings publish minimum-data, durable Operations work notices."""
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.settings import settings
from app.db.database import Base
from app.models.operations_outbox import OperationsOutboxEvent
from app.schemas.events import EventActionPayload, EventBookingPayload, EventBookingUpdate, EventLinePayload
from app.services.event_service import create_event, confirm_event, update_event, cancel_event


def test_confirmed_event_queues_one_privacy_safe_project_request(monkeypatch):
    monkeypatch.setattr(settings, "operations_integration_enabled", True)
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, autoflush=False, future=True)()
    try:
        event = create_event(db, EventBookingPayload(
            event_name="Private family party", client_name="PRIVATE GUEST NAME",
            event_date="2026-12-19", venue="Function Hall", guest_count=60,
            lines=[EventLinePayload(line_type="addon",
                                    description="Balloon decoration for PRIVATE GUEST NAME",
                                    quantity=1, unit_price=2500)],
        ))
        confirmed = confirm_event(db, event["id"], EventActionPayload())
        assert confirmed["status"] == "confirmed"
        rows = db.query(OperationsOutboxEvent).all()
        assert len(rows) == 1
        event_row = rows[0]
        assert event_row.event_type == "event.booking.confirmed"
        envelope = json.loads(event_row.envelope_json)
        assert envelope["subject"] == {"type": "event_booking", "id": str(event["id"])}
        assert envelope["payload"]["booking_id"] == event["id"]
        assert "design" in envelope["payload"]["services"]
        text = event_row.envelope_json
        assert "PRIVATE GUEST NAME" not in text
        assert "2500" not in text
        assert "Private family party" not in text

        update_event(db, event["id"], EventBookingUpdate(event_date="2026-12-20"))
        rows = db.query(OperationsOutboxEvent).order_by(OperationsOutboxEvent.id).all()
        assert len(rows) == 2
        assert rows[1].event_type == "event.booking.changed"
        assert rows[0].status == "pending"
    finally:
        db.close()
        engine.dispose()


def test_event_cancellation_queues_review_without_auto_project_mutation(monkeypatch):
    monkeypatch.setattr(settings, "operations_integration_enabled", True)
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, autoflush=False, future=True)()
    try:
        event = create_event(db, EventBookingPayload(
            event_name="Small seminar", client_name="PRIVATE NAME",
            event_date="2026-12-19", venue="Garden",
            lines=[EventLinePayload(description="Venue", quantity=1, unit_price=2500)],
        ))
        confirm_event(db, event["id"], EventActionPayload())
        cancel_event(db, event["id"], EventActionPayload())
        types = [row.event_type for row in db.query(OperationsOutboxEvent).order_by(OperationsOutboxEvent.id)]
        assert types == ["event.booking.confirmed", "event.booking.cancelled"]
    finally:
        db.close()
        engine.dispose()
