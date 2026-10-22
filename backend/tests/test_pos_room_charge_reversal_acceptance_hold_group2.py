"""No historical negative POS room-charge receipt may create a receivable."""
import pytest

from app.services.integration_review_service import _positive_pos_room_charge_amount


@pytest.mark.parametrize("gross", [-125.0, -0.01, 0, float("nan"), float("inf"), "-40.00", "bad"])
def test_negative_or_nonfinite_legacy_room_charge_fails_closed(gross):
    with pytest.raises(ValueError):
        _positive_pos_room_charge_amount({"gross_amount": gross}, 125)


def test_valid_original_room_charge_keeps_positive_receivable_contract():
    assert _positive_pos_room_charge_amount({"gross_amount": "125.55"}, 999) == 125.55
    assert _positive_pos_room_charge_amount({}, 125.55) == 125.55
