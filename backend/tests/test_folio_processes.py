import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.entities import Booking, BookingFolio, BookingFolioLine
from app.services.beds24_sync_service import (
    _classify_charge_line_type,
    _extract_invoice_item_entries,
    reclassify_historical_folio_lines,
)
from app.services.guest_service import POSITIVE_FOLIO_TYPES
from app.services.hospitality_service import list_booking_calendar


class FolioProcessTests(unittest.TestCase):
    def make_session(self):
        engine = create_engine('sqlite:///:memory:', future=True)
        testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
        Base.metadata.create_all(bind=engine)
        return testing_session()

    def test_beds24_invoice_charge_classification(self):
        cases = {
            'Extra Guest Fee': 'extra_person',
            'additional pax': 'extra_person',
            'Extra bed charge': 'extra_bed',
            'Roll-away bed': 'extra_bed',
            'Breakfast add on': 'breakfast_addon',
            'BFAST package': 'breakfast_addon',
            'Mini Bar': 'minibar',
            'Cafe room service': 'cafe_room_charge',
            'Kitchen dinner charge': 'cafe_room_charge',
            'Room charge': 'room_charge',
            'Accommodation': 'room_charge',
        }
        for description, expected in cases.items():
            with self.subTest(description=description):
                self.assertEqual(_classify_charge_line_type(description), expected)

    def test_cafe_room_charge_counts_as_folio_charge(self):
        self.assertIn('cafe_room_charge', POSITIVE_FOLIO_TYPES)
        self.assertIn('minibar', POSITIVE_FOLIO_TYPES)

    def test_negative_invoice_total_does_not_override_clear_charge_description(self):
        entries = _extract_invoice_item_entries(
            {'invoiceItems': [{'description': 'Breakfast add on', 'lineTotal': -350}]},
            'beds-101',
        )
        self.assertEqual(entries[0]['line_type'], 'breakfast_addon')
        self.assertEqual(entries[0]['amount'], 350)

    def test_explicit_payment_context_stays_payment(self):
        entries = _extract_invoice_item_entries(
            {'invoicePayments': [{'description': 'GCash payment for breakfast', 'lineTotal': -350}]},
            'beds-102',
        )
        self.assertEqual(entries[0]['line_type'], 'payment')

    def test_historical_payment_reclassification_previews_balance_adjustment(self):
        db = self.make_session()
        booking = Booking(
            guest_name='Old Guest',
            room_name='101',
            channel='Beds24',
            external_source='beds24',
            external_booking_id='beds-103',
            check_in='2026-06-01',
            check_out='2026-06-02',
        )
        db.add(booking)
        db.flush()
        folio = BookingFolio(booking_id=booking.id, folio_no='FOL-OLD-103', status='open')
        db.add(folio)
        db.flush()
        misclassified = BookingFolioLine(
            folio_id=folio.id,
            line_type='payment',
            description='Breakfast add on',
            amount=100,
            external_source='beds24',
            external_line_key='beds24:beds-103:invoice:item:1',
        )
        real_payment = BookingFolioLine(
            folio_id=folio.id,
            line_type='payment',
            description='GCash payment',
            amount=100,
            external_source='beds24',
            external_line_key='beds24:beds-103:invoice:payment:2',
        )
        db.add_all([misclassified, real_payment])
        db.commit()

        preview = reclassify_historical_folio_lines(
            db,
            dry_run=True,
            include_payment_lines=True,
            booking_id=booking.id,
        )
        self.assertEqual(preview['changed'], 1)
        self.assertEqual(preview['balance_affecting_changes'], 1)
        self.assertEqual(preview['balance_adjustment'], 200)
        self.assertEqual(misclassified.line_type, 'payment')

        applied = reclassify_historical_folio_lines(
            db,
            dry_run=False,
            include_payment_lines=True,
            booking_id=booking.id,
        )
        db.refresh(misclassified)
        db.refresh(real_payment)
        self.assertEqual(applied['changed'], 1)
        self.assertEqual(misclassified.line_type, 'breakfast_addon')
        self.assertEqual(real_payment.line_type, 'payment')

    def test_calendar_excludes_checkout_boundary(self):
        db = self.make_session()
        multi_night = Booking(
            guest_name='Multi Night Guest',
            room_name='100',
            channel='Walk-in',
            check_in='2026-06-01',
            check_out='2026-06-03',
        )
        one_night = Booking(
            guest_name='One Night Guest',
            room_name='101',
            channel='Walk-in',
            check_in='2026-06-01',
            check_out='2026-06-02',
        )
        arriving = Booking(
            guest_name='Arriving Guest',
            room_name='102',
            channel='Walk-in',
            check_in='2026-06-02',
            check_out='2026-06-03',
        )
        day_use = Booking(
            guest_name='Day Use Guest',
            room_name='103',
            channel='Walk-in',
            check_in='2026-06-04',
            check_out='2026-06-04',
        )
        db.add_all([multi_night, one_night, arriving, day_use])
        db.commit()

        rows = list_booking_calendar(db, start_date='2026-06-01', end_date='2026-06-01')
        self.assertEqual([row['guest_name'] for row in rows], ['Multi Night Guest', 'One Night Guest'])

        rows = list_booking_calendar(db, start_date='2026-06-02', end_date='2026-06-02')
        self.assertEqual([row['guest_name'] for row in rows], ['Multi Night Guest', 'Arriving Guest'])

        rows = list_booking_calendar(db, start_date='2026-06-03', end_date='2026-06-03')
        self.assertEqual([row['guest_name'] for row in rows], [])

        rows = list_booking_calendar(db, start_date='2026-06-04', end_date='2026-06-04')
        self.assertEqual([row['guest_name'] for row in rows], ['Day Use Guest'])

        rows = list_booking_calendar(db, start_date='2026-06-05', end_date='2026-06-05')
        self.assertEqual([row['guest_name'] for row in rows], [])


if __name__ == '__main__':
    unittest.main()
