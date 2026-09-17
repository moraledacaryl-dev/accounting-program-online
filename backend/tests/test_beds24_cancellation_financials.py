from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import Base
from app.models.entities import Booking, BookingFolio, BookingFolioLine, Receivable
from app.services.beds24_cancellation_service import neutralize_cancelled_beds24_bookings


def _db():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    return engine, Session(engine)


def test_cancelled_beds24_booking_keeps_audit_row_but_neutralizes_mirrored_financials():
    engine, db = _db()
    try:
        booking = Booking(
            guest_name='Cancelled Guest',
            external_source='beds24',
            external_booking_id='B24-CANCEL-1',
            status='cancelled',
            check_out='2026-09-20',
            gross_amount=7500,
            deposit_amount=1000,
        )
        db.add(booking)
        db.flush()
        folio = BookingFolio(booking_id=booking.id, folio_no='F-CANCEL-1')
        db.add(folio)
        db.flush()
        db.add_all([
            BookingFolioLine(folio_id=folio.id, description='Beds24 room charge', amount=7500, external_source='beds24'),
            BookingFolioLine(folio_id=folio.id, description='Manual cancellation fee', amount=500, external_source=None),
            Receivable(
                source_type='booking', source_id=booking.id, counterparty_name='Cancelled Guest',
                receivable_type='guest_balance', gross_amount=7500, amount_collected=1000,
                balance_due=6500, status='open',
            ),
        ])
        db.commit()

        result = neutralize_cancelled_beds24_bookings(db, beds24_booking_ids=['B24-CANCEL-1'])

        db.refresh(booking)
        assert booking.status == 'cancelled'
        assert booking.gross_amount == 0
        assert booking.deposit_amount == 0
        lines = db.query(BookingFolioLine).filter(BookingFolioLine.folio_id == folio.id).all()
        assert [(line.description, line.amount) for line in lines] == [('Manual cancellation fee', 500)]
        receivable = db.query(Receivable).filter(Receivable.source_id == booking.id).one()
        assert (receivable.gross_amount, receivable.amount_collected, receivable.balance_due) == (0, 0, 0)
        assert receivable.status == 'closed'
        assert receivable.closed_at == '2026-09-20'
        assert 'financial mirror neutralized' in receivable.notes.lower()
        assert result == {
            'cancelled_bookings_neutralized': 1,
            'beds24_folio_lines_removed': 1,
            'receivables_closed': 1,
        }
    finally:
        db.close()
        engine.dispose()


def test_non_cancelled_beds24_booking_is_untouched():
    engine, db = _db()
    try:
        booking = Booking(
            guest_name='Active Guest', external_source='beds24', external_booking_id='B24-ACTIVE-1',
            status='confirmed', gross_amount=7500, deposit_amount=1000,
        )
        db.add(booking)
        db.commit()

        result = neutralize_cancelled_beds24_bookings(db, beds24_booking_ids=['B24-ACTIVE-1'])

        db.refresh(booking)
        assert (booking.gross_amount, booking.deposit_amount, booking.status) == (7500, 1000, 'confirmed')
        assert result['cancelled_bookings_neutralized'] == 0
    finally:
        db.close()
        engine.dispose()
