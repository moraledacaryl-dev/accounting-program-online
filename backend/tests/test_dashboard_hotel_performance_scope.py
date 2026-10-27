"""The dashboard hotel view must retain boundary stays without loading old history."""
from datetime import date

from sqlalchemy import create_engine, event, insert
from sqlalchemy.orm import Session

from app.api.dashboard import _hotel_performance
from app.db.database import Base
from app.models.entities import Booking, Room


def test_hotel_performance_uses_overlapping_stays_and_keeps_historical_load_bounded():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            db.execute(insert(Room), [
                {'id': 1, 'name': 'One', 'room_no': '1', 'is_active': True},
                {'id': 2, 'name': 'Two', 'room_no': '2', 'is_active': True},
                {'id': 3, 'name': 'Inactive', 'room_no': '3', 'is_active': False},
            ])
            stays = [
                # The first visible bucket begins 2025-10-01.
                {'room_id': 1, 'check_in': '2025-09-28', 'check_out': '2025-10-03', 'gross_amount': 500},
                {'room_id': 1, 'check_in': '2026-10-05', 'check_out': '2026-10-07', 'gross_amount': 300},
                # Oct 6 belongs to the earlier booking; Oct 7 is new.
                {'room_id': 1, 'check_in': '2026-10-06', 'check_out': '2026-10-08', 'gross_amount': 200},
                {'room_id': 2, 'check_in': '2026-10-30', 'check_out': '2026-11-02', 'gross_amount': 300},
                {'room_id': 2, 'check_in': '2026-11-01', 'check_out': '2026-11-03', 'gross_amount': 200},
                {'room_id': 3, 'check_in': '2026-10-10', 'check_out': '2026-10-12', 'gross_amount': 200},
                {'room_id': 2, 'check_in': '2026-10-10', 'check_out': '2026-10-12', 'gross_amount': 200,
                 'status': 'cancelled'},
            ]
            stays.extend({
                'room_id': 1, 'check_in': '2018-01-01', 'check_out': '2018-01-02', 'gross_amount': 100,
            } for _ in range(100))
            db.execute(insert(Booking), [
                {'guest_name': 'Synthetic Guest', 'status': 'confirmed', **stay}
                for stay in stays
            ])
            db.commit()
            db.expunge_all()

            loaded_bookings = []
            event.listen(db, 'loaded_as_persistent', lambda _session, row: loaded_bookings.append(row)
                         if isinstance(row, Booking) else None)
            result = _hotel_performance(db, date(2026, 10, 27), 2)

            assert len(result['monthly_trend']) == 13
            assert result['monthly_trend'][0]['room_nights'] == 2
            assert result['monthly_trend'][0]['room_revenue'] == 200
            assert result['current_month']['room_nights'] == 5
            assert result['current_month']['room_revenue'] == 600
            assert len(result['room_utilization']) == 2
            assert len(loaded_bookings) <= 4
    finally:
        engine.dispose()
