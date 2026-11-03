"""Preview/queue current room and future event handoffs; never edit bookings.

Run from backend with PYTHONPATH=. Defaults to a count-only dry run.
"""
import argparse
import json

from app.core.business_clock import business_today
from app.db.database import SessionLocal
from app.models.entities import Booking, EventBooking
from app.models.operations_outbox import OperationsOutboxEvent
from app.services.event_service import _enqueue_event_work
from app.services.operations_room_updates import enqueue_room_update


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    today = business_today()
    with SessionLocal() as db:
        bookings = db.query(Booking).filter(Booking.check_out >= today).order_by(Booking.id).all()
        events = db.query(EventBooking).filter(EventBooking.event_date >= today,
            EventBooking.status == 'confirmed').order_by(EventBooking.id).all()
        before = db.query(OperationsOutboxEvent).count()
        if args.apply:
            for booking in bookings:
                enqueue_room_update(db, booking)
            for event in events:
                _enqueue_event_work(db, event, 'confirmed')
            db.commit()
        print(json.dumps({'mode': 'queued' if args.apply else 'preview', 'from_date': today,
            'room_bookings': len(bookings), 'confirmed_events': len(events),
            'new_outbox_events': db.query(OperationsOutboxEvent).count() - before}))


if __name__ == '__main__':
    main()
