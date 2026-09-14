import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import Base
from app.models.entities import Booking, Guest, Beds24GuestMap
from app.services.beds24_sync_service import (
    _apply_booking_guest_identity, _match_or_create_guest,
)


@pytest.mark.parametrize('incoming', [None, '', '  ', 'Unnamed Guest', 'Unknown', 'N/A'])
def test_blank_beds24_name_preserves_real_local_booking_identity(incoming):
    booking = Booking(id=26, guest_id=10, guest_name='Maria S. Santos')
    # Even an upstream contact match cannot replace verified history on blanks.
    _apply_booking_guest_identity(booking, Guest(id=12, full_name='Other Person'), incoming)
    assert (booking.guest_id, booking.guest_name) == (10, 'Maria S. Santos')


def test_historical_manually_repaired_name_survives_blank_upstream():
    booking = Booking(id=26, guest_id=10, guest_name='Workbook Repaired Name', check_in='2025-05-01')
    _apply_booking_guest_identity(booking, None, 'Unnamed Guest')
    assert (booking.guest_id, booking.guest_name) == (10, 'Workbook Repaired Name')


@pytest.mark.parametrize('local_name', ['Stale Person', 'Unnamed Guest'])
def test_nonblank_beds24_name_replaces_name_and_clears_contradictory_guest(local_name):
    old = Guest(id=10, full_name='Stale Person')
    booking = Booking(id=26, guest_id=10, guest=old, guest_name=local_name)
    _apply_booking_guest_identity(booking, None, 'Maria Santos')
    assert (booking.guest_id, booking.guest_name) == (None, 'Maria Santos')
    assert booking.guest is None
    assert old.full_name == 'Stale Person'


def test_nonblank_name_replaces_unlinked_local_name():
    booking = Booking(id=26, guest_name='Workbook Repaired Name')
    _apply_booking_guest_identity(booking, None, 'Different Beds24 Name')
    assert (booking.guest_id, booking.guest_name) == (None, 'Different Beds24 Name')


def test_matched_guest_replaces_stale_guest_linkage():
    booking = Booking(id=26, guest_id=10, guest_name='Other Person')
    guest = Guest(id=12, full_name='Maria Santos')
    _apply_booking_guest_identity(booking, guest, 'Maria Santos')
    assert (booking.guest_id, booking.guest_name) == (12, 'Maria Santos')
    assert booking.guest is guest


def test_same_identity_preserves_correct_link_even_without_new_match():
    guest = Guest(id=10, full_name='Maria Santos')
    booking = Booking(id=26, guest_id=10, guest=guest, guest_name='Maria Santos')
    _apply_booking_guest_identity(booking, None, 'Maria Santos')
    assert (booking.guest_id, booking.guest_name) == (10, 'Maria Santos')


def test_contradictory_resolved_guest_cannot_override_beds24_name():
    guest = Guest(id=10, full_name='Shared Booker')
    booking = Booking(id=26, guest_id=10, guest=guest, guest_name='Shared Booker')
    _apply_booking_guest_identity(booking, guest, 'Maria Santos')
    assert (booking.guest_id, booking.guest_name) == (None, 'Maria Santos')
    assert guest.full_name == 'Shared Booker'


def test_both_blank_remains_placeholder():
    booking = Booking(id=26, guest_name='')
    _apply_booking_guest_identity(booking, None, '')
    assert (booking.guest_id, booking.guest_name) == (None, 'Unnamed Guest')


@pytest.fixture
def db():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.mark.parametrize('key', ['email', 'phone', 'mobile', 'guestId'])
@pytest.mark.parametrize('auto_create', [False, True])
def test_shared_contact_or_stable_key_does_not_resolve_another_person(db, key, auto_create):
    old = Guest(full_name='Shared Booker', email='booker@example.test', phone='123456789', is_active=True)
    db.add(old)
    db.flush()
    db.add(Beds24GuestMap(beds24_guest_key='beds24:guestId:7', local_guest_id=old.id))
    db.flush()
    value = {'email': old.email, 'phone': old.phone, 'mobile': old.phone, 'guestId': '7'}[key]
    guest, strategy = _match_or_create_guest(db, {'firstName': 'Maria', 'lastName': 'Santos', key: value}, auto_create_guest=auto_create)
    if auto_create:
        assert guest.id != old.id
        assert guest.full_name == 'Maria Santos'
    else:
        assert guest is None
    assert old.full_name == 'Shared Booker'


def test_correct_existing_named_guest_wins_over_wrong_contact_match(db):
    old = Guest(full_name='Shared Booker', email='booker@example.test', is_active=True)
    correct = Guest(full_name='Maria Santos', is_active=True)
    db.add_all([old, correct])
    db.flush()
    guest, strategy = _match_or_create_guest(db, {'firstName': 'Maria', 'lastName': 'Santos', 'email': old.email}, auto_create_guest=True)
    assert guest.id == correct.id
    assert strategy == 'normalized_name'


def test_blank_name_never_matches_guest_by_shared_contact(db):
    db.add(Guest(full_name='Shared Booker', email='booker@example.test', is_active=True))
    db.flush()
    guest, _ = _match_or_create_guest(db, {'email': 'booker@example.test'}, auto_create_guest=True)
    assert guest is None


@pytest.mark.parametrize('incoming,auto_create', [('', False), ('Maria Santos', False), ('Maria Santos', True)])
def test_sync_persists_consistent_booking_and_mapping_without_renaming_shared_guest(db, monkeypatch, incoming, auto_create):
    from app.models.entities import Beds24BookingMap
    from app.services import beds24_sync_service as service
    from app.services.beds24_service import DEFAULT_BEDS24_SETTINGS

    old = Guest(full_name='Shared Booker', email='booker@example.test', is_active=True)
    db.add(old)
    db.flush()
    booking = Booking(guest_id=old.id, guest_name=old.full_name, external_source='beds24', external_booking_id='123')
    other_booking = Booking(guest_id=old.id, guest_name=old.full_name)
    db.add_all([booking, other_booking])
    db.flush()
    mapping = Beds24BookingMap(beds24_booking_id='123', local_booking_id=booking.id, local_guest_id=old.id)
    db.add(mapping)
    db.commit()
    old_id = old.id
    monkeypatch.setattr(service, 'load_beds24_settings', lambda db: {**DEFAULT_BEDS24_SETTINGS, 'auto_create_guest': auto_create, 'auto_link_channel': False})
    service.sync_booking_payload(db, {'id': '123', 'guestName': incoming, 'email': old.email})
    db.expire_all()
    assert mapping.local_guest_id == booking.guest_id
    if not incoming:
        assert (booking.guest_name, booking.guest_id) == ('Shared Booker', old_id)
    else:
        assert booking.guest_name == incoming
        if auto_create:
            assert booking.guest_id != old_id
            assert booking.guest.full_name == incoming
        else:
            assert booking.guest_id is None
    assert old.full_name == 'Shared Booker'
    assert (other_booking.guest_id, other_booking.guest_name) == (old_id, 'Shared Booker')
