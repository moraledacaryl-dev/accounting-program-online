"""Publish room/date/status facts through the existing transactional outbox.

Beds24 still owns its reservations. Guest, price, payment and narrative fields
are deliberately excluded. Repeated webhooks do not create repeated work.
"""
import json
from datetime import date
from uuid import uuid4

from app.models.operations_outbox import OperationsOutboxEvent
from app.services.operations_outbox_service import enqueue_operations_event

STATUSES = {'confirmed', 'checked_in', 'checked_out', 'cancelled', 'no_show'}


def _day(value):
    try:
        return date.fromisoformat(str(value or '')).isoformat()
    except ValueError:
        return None


def enqueue_room_update(db, booking):
    db.flush()
    prefix = f'room-booking:{booking.id}:'
    facts = {
        'booking_id': booking.id,
        'room_id': booking.room_id,
        'check_in': _day(booking.check_in),
        'check_out': _day(booking.check_out),
        'status': booking.status if booking.status in STATUSES else 'unknown',
        'origin': 'beds24' if booking.external_source == 'beds24' else 'accounting',
    }
    previous = db.query(OperationsOutboxEvent).filter(
        OperationsOutboxEvent.event_id.startswith(prefix)
    ).order_by(OperationsOutboxEvent.id.desc()).first()
    if previous:
        prior = json.loads(previous.envelope_json)['payload']
        if facts == {key: prior.get(key) for key in facts}:
            return previous
    row = enqueue_operations_event(
        db, event_id=prefix + uuid4().hex, event_type='room.booking.updated',
        title='Room booking update', summary='Room and checkout status from Accounting',
        subject_type='room_booking', subject_id=booking.id, payload=facts,
    )
    if row:
        # The durable outbox sequence orders snapshots even when retries arrive
        # after a newer update. A -> B -> A still receives three distinct revisions.
        envelope = json.loads(row.envelope_json)
        envelope['payload']['revision'] = row.id
        row.envelope_json = json.dumps(envelope, separators=(',', ':'), sort_keys=True)
        db.flush()
    return row
