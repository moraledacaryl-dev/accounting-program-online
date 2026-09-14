from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.api.channel_reconciliation import PayoutReconcileBatch, _deduction_amount, _deduction_percent


def test_channel_deduction_uses_actual_receipt():
    assert _deduction_amount('3500', '2975') == Decimal('525.00')
    assert _deduction_percent('3500', '2975') == 15.0


def test_zero_original_has_no_misleading_percentage():
    assert _deduction_amount(0, 0) == Decimal('0.00')
    assert _deduction_percent(0, 0) is None


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
