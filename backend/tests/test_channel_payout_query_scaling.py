"""Channel Payouts keeps rate calculations stable as the booking list grows."""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.channel_reconciliation import _normal_room_rate, payout_bookings, reconciliation_history
from app.db.database import Base
from app.models.channel_payout_reconciliation import ChannelBookingStaySnapshot, ChannelPayoutBookingLink
from app.models.entities import Booking, BookingChannel, ChannelPayout, RatePlan, Room, RoomType


def test_payout_pages_batch_rate_inputs_without_changing_amounts():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            db.add_all([
                BookingChannel(id=1, code='SYNTH', name='Synthetic channel', is_active=True),
                RoomType(id=1, code='SYNTH', name='Synthetic type'),
                Room(id=1, room_no='SYNTH-1', name='Synthetic room', room_type_id=1),
                RatePlan(id=1, code='STANDARD', name='Standard', room_type_id=1, base_rate=1000, is_active=True),
            ])
            for booking_id in range(1, 61):
                db.add(Booking(
                    id=booking_id, guest_name='Synthetic guest', room_id=1, channel_id=1,
                    room_name='Synthetic room', status='confirmed', check_in='2026-10-01',
                    check_out='2026-10-02', gross_amount=900,
                ))
                if booking_id % 2 == 0:
                    db.add(ChannelBookingStaySnapshot(
                        booking_id=booking_id, ota_check_in='2026-10-01',
                        ota_check_out='2026-10-03', source='synthetic',
                    ))
                if booking_id % 3 == 0:
                    payout_id = booking_id // 3
                    db.add(ChannelPayout(
                        id=payout_id, channel_id=1, channel='Synthetic channel',
                        status='paid', gross_amount=900, net_amount=850,
                        actual_payout_date='2026-10-27',
                    ))
                    db.add(ChannelPayoutBookingLink(payout_id=payout_id, booking_id=booking_id))
            db.commit()
            expected = {
                booking.id: float(_normal_room_rate(db, booking))
                for booking in db.query(Booking).all()
            }
            db.expunge_all()

            statements = 0

            def count_statements(*_args):
                nonlocal statements
                statements += 1

            event.listen(engine, 'before_cursor_execute', count_statements)
            try:
                pending = payout_bookings(channel_id=1, search='', db=db, user=None)
                pending_statements = statements
                statements = 0
                history = reconciliation_history(channel_id=1, db=db, user=None)
                history_statements = statements
            finally:
                event.remove(engine, 'before_cursor_execute', count_statements)

            assert len(pending) == 40  # paid bookings are absent from the pending list
            assert len(history) == 20
            assert all(row['original_amount'] == expected[row['booking_id']] for row in pending)
            assert all(row['gross_amount'] == expected[row['booking_id']] for row in history)
            assert pending_statements <= 6
            assert history_statements <= 6
    finally:
        engine.dispose()


def test_unpaid_booking_is_not_hidden_behind_two_thousand_paid_bookings():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            db.add(BookingChannel(id=1, code='SYNTH', name='Synthetic channel', is_active=True))
            db.add_all([
                Booking(id=booking_id, guest_name='Synthetic guest', channel_id=1,
                        status='confirmed', check_in='2026-10-01', check_out='2026-10-02',
                        gross_amount=900)
                for booking_id in range(1, 2002)
            ])
            db.add_all([
                ChannelPayout(id=booking_id, channel_id=1, channel='Synthetic channel',
                              status=' PAID ' if booking_id == 2 else 'paid', gross_amount=900, net_amount=850)
                for booking_id in range(2, 2002)
            ])
            db.add_all([
                ChannelPayoutBookingLink(payout_id=booking_id, booking_id=booking_id)
                for booking_id in range(2, 2002)
            ])
            db.commit()

            pending = payout_bookings(channel_id=1, search='', db=db, user=None)
            assert [row['booking_id'] for row in pending] == [1]
    finally:
        engine.dispose()
