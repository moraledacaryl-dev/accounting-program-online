import pytest

from app.services.beds24_sync_service import _build_folio_entries


def entry(description, amount, kind='charge', **kwargs):
    return {'id': 1, 'type': kind, 'description': description, 'amount': abs(amount),
            'lineTotal': amount, **kwargs}


@pytest.mark.parametrize('description,expected', [
    ('50% Non-refundable deposit', 'nonrefundable_charge'),
    ('Nonrefundable deposit', 'nonrefundable_charge'),
    ('Deposit processing fee', 'manual_charge'),
    ('GCash processing fee', 'manual_charge'),
    ('Refunded last May 3, 2026', 'refund'),
])
def test_explicit_charge_does_not_invent_cash(description, expected):
    rows = _build_folio_entries({'invoiceItems': [entry(description, 3000)]}, '42')
    assert rows[0]['line_type'] == expected
    assert rows[0]['amount'] == 3000


def test_actual_nonrefundable_deposit_remains_payment():
    rows = _build_folio_entries({'invoiceItems': [entry('Non-refundable deposit', -3000, 'payment')]}, '42')
    assert rows[0]['line_type'] == 'deposit'


def test_ota_settlement_excludes_guest_extras():
    items = [entry('[ROOMNAME1] [FIRSTNIGHT] - [LEAVINGDAY]', 5343.36),
             entry('Extra Breakfast', 400, id=2), entry('LATE CHECK-OUT CHARGE', 450, id=3),
             entry('Food', 624, id=4)]
    rows = _build_folio_entries({'invoiceItems': items}, '42', force_prepaid_settlement=True)
    assert sum(r['amount'] for r in rows[:-1]) == 6817.36
    assert rows[-1]['external_line_key'] == 'beds24:42:prepaid_settlement'
    assert rows[-1]['amount'] == 5343.36
    assert len(rows) == 5


def test_extra_only_invoice_does_not_create_ota_payment():
    rows = _build_folio_entries({'invoiceItems': [entry('Extra Bed', 300)]}, '42', force_prepaid_settlement=True)
    assert len(rows) == 1 and rows[0]['line_type'] == 'extra_bed'


def test_existing_payment_is_not_duplicated():
    rows = _build_folio_entries({'invoiceItems': [entry('Room accommodation', 4000),
                               entry('Paid via Agoda', -4000, 'payment', id=2)]}, '42', force_prepaid_settlement=True)
    assert len(rows) == 2
    assert rows[1]['line_type'] == 'payment'


def test_summary_room_prepaid_still_works():
    rows = _build_folio_entries({'price': 4000}, '42', force_prepaid_settlement=True)
    assert [r['amount'] for r in rows] == [4000, 4000]


def test_ota_settlement_preserves_separate_stay_taxes():
    rows = _build_folio_entries({'invoiceItems': [
        entry('Room accommodation', 3200), entry('VAT', 384, id=2),
        entry('City tax', 320, id=3), entry('Extra Breakfast', 200, id=4),
    ]}, '42', force_prepaid_settlement=True)
    assert rows[-1]['amount'] == 3904
