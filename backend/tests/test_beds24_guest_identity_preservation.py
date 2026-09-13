from app.models.entities import Booking, Guest
from app.services.beds24_sync_service import _apply_booking_guest_identity


def test_blank_beds24_name_preserves_real_local_booking_identity():
    booking = Booking(id=26, guest_id=10, guest_name='Maria S. Santos')

    _apply_booking_guest_identity(booking, None, 'Unnamed Guest')

    assert booking.guest_id == 10
    assert booking.guest_name == 'Maria S. Santos'


def test_real_unmatched_beds24_name_can_fill_placeholder_without_unlinking_guest():
    booking = Booking(id=26, guest_id=10, guest_name='Unnamed Guest')

    _apply_booking_guest_identity(booking, None, 'Maria Santos')

    assert booking.guest_id == 10
    assert booking.guest_name == 'Maria Santos'


def test_real_local_name_is_authoritative_when_incoming_guest_is_unmatched():
    booking = Booking(id=26, guest_id=None, guest_name='Workbook Repaired Name')

    _apply_booking_guest_identity(booking, None, 'Different Beds24 Name')

    assert booking.guest_id is None
    assert booking.guest_name == 'Workbook Repaired Name'


def test_matched_guest_can_replace_placeholder_identity():
    booking = Booking(id=26, guest_id=None, guest_name='Unnamed Guest')
    guest = Guest(id=12, full_name='Maria Santos', first_name='Maria', last_name='Santos')

    _apply_booking_guest_identity(booking, guest, 'Maria Santos')

    assert booking.guest_id == 12
    assert booking.guest_name == 'Maria Santos'
