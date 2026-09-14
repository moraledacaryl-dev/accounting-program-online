from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.channel_reconciliation import PayoutReconcileBatch, _deduction_amount, _deduction_percent, _normal_room_rate


def test_channel_deduction_uses_actual_receipt():
    assert _deduction_amount('3500', '2975') == Decimal('525.00')
    assert _deduction_percent('3500', '2975') == 15.0


def test_zero_original_has_no_misleading_percentage():
    assert _deduction_amount(0, 0) == Decimal('0.00')
    assert _deduction_percent(0, 0) is None


def test_normal_room_rate_uses_rate_plan_for_entire_stay():
    booking = SimpleNamespace(
        gross_amount=5400,
        check_in='2026-09-15',
        check_out='2026-09-17',
        rate_plan=SimpleNamespace(base_rate=3000),
    )
    assert _normal_room_rate(booking) == Decimal('6000.00')


def test_normal_room_rate_falls_back_to_booking_value_without_rate_plan():
    booking = SimpleNamespace(gross_amount=5400, check_in='2026-09-15', check_out='2026-09-17', rate_plan=None)
    assert _normal_room_rate(booking) == Decimal('5400.00')


def test_reconcile_payload_rejects_duplicate_booking_ids():
    with pytest.raises(ValidationError):
        PayoutReconcileBatch(
            channel_id=1,
            actual_payout_date='2026-09-15',
            items=[
                {'booking_id': 7, 'actual_amount': '100.00'},
                {'booking_id': 7, 'actual_amount': '90.00'},
            ],
        )
