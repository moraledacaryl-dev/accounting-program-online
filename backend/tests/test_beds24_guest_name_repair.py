import json

from app.models.entities import Beds24BookingMap, Booking, Guest
from app.services.beds24_guest_repair_service import repair_beds24_placeholder_guest_names


class _FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def join(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return list(self.rows)


class _FakeSession:
    def __init__(self, mappings, bookings, guests):
        self.mappings = mappings
        self.bookings = bookings
        self.guests = guests
        self.added = []
        self.commit_count = 0

    def query(self, model):
        assert model is Beds24BookingMap
        return _FakeQuery(self.mappings)

    def get(self, model, row_id):
        if model is Booking:
            return self.bookings.get(int(row_id))
        if model is Guest:
            return self.guests.get(int(row_id))
        raise AssertionError(f'unexpected model: {model}')

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.commit_count += 1


def _mapping(booking_id, snapshot):
    return Beds24BookingMap(
        id=1,
        beds24_booking_id='78444215',
        local_booking_id=booking_id,
        raw_snapshot=json.dumps(snapshot),
    )


def test_repairs_placeholder_guest_and_booking_from_fresh_snapshot():
    guest = Guest(id=10, full_name='Unnamed Guest', first_name=None, last_name=None)
    booking = Booking(id=26, guest_id=10, guest_name='Unnamed Guest')
    mapping = _mapping(26, {'firstName': 'Maria', 'lastName': 'Santos'})
    db = _FakeSession([mapping], {26: booking}, {10: guest})

    result = repair_beds24_placeholder_guest_names(db)

    assert result['repaired'] == 1
    assert booking.guest_name == 'Maria Santos'
    assert guest.full_name == 'Maria Santos'
    assert guest.first_name == 'Maria'
    assert guest.last_name == 'Santos'
    assert db.commit_count == 1


def test_preserves_real_local_guest_name_instead_of_overwriting_it():
    guest = Guest(id=10, full_name='Maria S. Santos', first_name='Maria', last_name='Santos')
    booking = Booking(id=26, guest_id=10, guest_name='Unnamed Guest')
    mapping = _mapping(26, {'firstName': 'Maria', 'lastName': 'Santos'})
    db = _FakeSession([mapping], {26: booking}, {10: guest})

    result = repair_beds24_placeholder_guest_names(db)

    assert result['repaired'] == 1
    assert result['preserved_real_guest'] == 1
    assert guest.full_name == 'Maria S. Santos'
    assert booking.guest_name == 'Maria S. Santos'


def test_does_not_replace_placeholder_when_snapshot_still_has_no_name():
    guest = Guest(id=10, full_name='Unnamed Guest', first_name=None, last_name=None)
    booking = Booking(id=26, guest_id=10, guest_name='Unnamed Guest')
    mapping = _mapping(26, {'firstName': '', 'lastName': ''})
    db = _FakeSession([mapping], {26: booking}, {10: guest})

    result = repair_beds24_placeholder_guest_names(db)

    assert result['repaired'] == 0
    assert result['skipped_no_name_in_snapshot'] == 1
    assert booking.guest_name == 'Unnamed Guest'
    assert guest.full_name == 'Unnamed Guest'
    assert db.commit_count == 0
