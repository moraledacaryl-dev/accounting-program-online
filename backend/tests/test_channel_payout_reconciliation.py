from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.channel_reconciliation import PayoutReconcileBatch, _deduction_amount, _deduction_percent, _normal_room_rate


class _RatePlanQuery:
    def __init__(self, plans):
        self.plans = plans

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self.plans


class _Db:
    def __init__(self, plans):
        self.plans = plans

    def query(self, model):
        return _RatePlanQuery(self.plans)


def test_channel_deduction_uses_actual_receipt():
    assert _deduction_amount('3500', '2975') == Decimal('525.00')
    assert _deduction_percent('3500', '2975') == 15.0


def test_zero_original_has_no_misleading_percentage():
    assert _deduction_amount(0, 0) == Decimal('0.00')
    assert _deduction_percent(0, 0) is None


def test_normal_room_rate_uses_room_types_standard_plan_not_booking_ota_plan():
    booking = SimpleNamespace(
        gross_amount=2100,
        room_type_id=4,
        room_name='Cafe Suite',
        room=None,
        rate_plan=SimpleNamespace(id=99, code='AGODA', name='Agoda Promo', base_rate=2100),
    )
    plans = [
        SimpleNamespace(id=99, code='AGODA', name='Agoda Promo', base_rate=2100),
        SimpleNamespace(id=7, code='STANDARD', name='Standard Flexible', base_rate=2500),
    ]
    assert _normal_room_rate(_Db(plans), booking) == Decimal('2500.00')


def test_normal_room_rate_accepts_standard_named_plan():
    booking = SimpleNamespace(gross_amount=2200, room_type_id=4, room_name='Cafe Suite', room=None)
    plans = [SimpleNamespace(id=7, code='FLEX', name='Standard Flexible', base_rate=2500)]
    assert _normal_room_rate(_Db(plans), booking) == Decimal('2500.00')


@pytest.mark.parametrize(
    ('room_name', 'expected'),
    [
        ('Cafe Suite', '2500.00'),
        ('Grandeur', '3500.00'),
        ('Solace', '4000.00'),
        ('Twinspire', '3000.00'),
        ('Skyroom', '3200.00'),
        ('Sky Room', '3200.00'),
        ('Perch 1', '4200.00'),
        ('Perch 2', '4300.00'),
        ('Crown', '3300.00'),
    ],
)
def test_normal_room_rate_uses_hidden_oasis_published_rate_when_standard_plan_missing(room_name, expected):
    booking = SimpleNamespace(gross_amount=1999, room_type_id=4, room_name=room_name, room=None)
    plans = [SimpleNamespace(id=9, code='AGODA', name='Agoda Promo', base_rate=1999)]
    assert _normal_room_rate(_Db(plans), booking) == Decimal(expected)


def test_normal_room_rate_falls_back_to_booking_value_for_unknown_room_without_standard_plan():
    booking = SimpleNamespace(gross_amount=5400, room_type_id=4, room_name='Unknown Room', room=None)
    plans = [SimpleNamespace(id=9, code='AGODA', name='Agoda Promo', base_rate=3000)]
    assert _normal_room_rate(_Db(plans), booking) == Decimal('5400.00')


def test_reconcile_payload_accepts_user_entered_expected_payout():
    payload = PayoutReconcileBatch(
        channel_id=1,
        actual_payout_date='2026-09-15',
        items=[{'booking_id': 7, 'expected_amount': '3220.00', 'actual_amount': '3180.00'}],
    )
    assert payload.items[0].expected_amount == Decimal('3220.00')
    assert payload.items[0].actual_amount == Decimal('3180.00')


def test_reconcile_payload_rejects_duplicate_booking_ids():
    with pytest.raises(ValidationError):
        PayoutReconcileBatch(
            channel_id=1,
            actual_payout_date='2026-09-15',
            items=[
                {'booking_id': 7, 'expected_amount': '100.00', 'actual_amount': '100.00'},
                {'booking_id': 7, 'expected_amount': '90.00', 'actual_amount': '90.00'},
            ],
        )