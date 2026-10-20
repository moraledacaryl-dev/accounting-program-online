"""Safety tests for the intentionally narrow historical Beds24 cancellation backfill."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from scripts import repair_known_beds24_cancellations as repair


def sample():
    booking = SimpleNamespace(
        id=567,
        external_source="beds24",
        external_booking_id="86810780",
        status="confirmed",
        deposit_amount=0,
    )
    mapping = SimpleNamespace(local_booking_id=567)
    folio = SimpleNamespace(id=123)
    return booking, mapping, folio


def test_verified_exact_remote_cancel():
    item = {"id": "86810780", "status": "cancelled"}
    assert repair.verify_remote_cancellation("86810780", [item]) is item


@pytest.mark.parametrize("items", [
    [],
    [{"id": "86810780", "status": "confirmed"}],
    [{"id": "86810780", "status": "cancelled"}, {"id": "86810780", "status": "cancelled"}],
    [{"id": "87953694", "status": "cancelled"}],
])
def test_remote_requires_one_exact_cancel(items):
    with pytest.raises(RuntimeError):
        repair.verify_remote_cancellation("86810780", items)


def test_eligible_local_booking_without_receivables():
    booking, mapping, folio = sample()
    assert repair.check_local_safety("86810780", [booking], [mapping], [], [folio]) == "eligible"


def test_already_cancelled_local_is_idempotent():
    booking, mapping, folio = sample()
    booking.status = "cancelled"
    assert repair.check_local_safety("86810780", [booking], [mapping], [], [folio]) == "already_cancelled"


@pytest.mark.parametrize("mutation", ["deposit", "receivable", "map", "folio", "status", "booking_id"])
def test_financial_identity_and_state_guards(mutation):
    booking, mapping, folio = sample()
    receivables = []
    maps = [mapping]
    folios = [folio]
    if mutation == "deposit":
        booking.deposit_amount = 100
    if mutation == "receivable":
        receivables = [SimpleNamespace(id=1, amount_collected=0)]
    if mutation == "map":
        maps = [SimpleNamespace(local_booking_id=1000)]
    if mutation == "folio":
        folios = []
    if mutation == "status":
        booking.status = "checked_in"
    if mutation == "booking_id":
        booking.id = 1000
    with pytest.raises(RuntimeError):
        repair.check_local_safety("86810780", [booking], maps, receivables, folios)


def fake_db(booking, mapping, folio):
    db = MagicMock()
    bq, mq, rq, fq = (MagicMock() for _ in range(4))
    bq.filter.return_value.populate_existing.return_value.with_for_update.return_value.all.return_value = [booking]
    mq.filter.return_value.all.return_value = [mapping]
    rq.filter.return_value.all.return_value = []
    fq.filter.return_value.all.return_value = [folio]
    db.query.side_effect = [bq, mq, rq, fq]
    return db


def test_status_only_repair_commits_only_after_fresh_remote_cancel():
    booking, mapping, folio = sample()
    db = fake_db(booking, mapping, folio)
    with (
        patch.object(repair, "SessionLocal", return_value=db),
        patch.object(repair, "fetch_beds24_bookings", return_value=(
            [{"id": "86810780", "status": "cancelled"}], {}, {},
        )),
        patch.object(repair, "apply_beds24_cancellation", return_value={
            "action": "cancelled", "receivables_closed": 0,
        }) as apply,
    ):
        assert repair.repair_booking("86810780") == "cancelled"
    apply.assert_called_once()
    assert apply.call_args.kwargs["source_type"] == "historical_verified_backfill"
    db.commit.assert_called_once()
    db.close.assert_called_once()


def test_no_mutation_on_non_cancelled_remote_response():
    booking, mapping, folio = sample()
    db = fake_db(booking, mapping, folio)
    with (
        patch.object(repair, "SessionLocal", return_value=db),
        patch.object(repair, "fetch_beds24_bookings", return_value=(
            [{"id": "86810780", "status": "confirmed"}], {}, {},
        )),
        patch.object(repair, "apply_beds24_cancellation") as apply,
    ):
        with pytest.raises(RuntimeError, match="not cancelled"):
            repair.repair_booking("86810780")
    db.commit.assert_not_called()
    apply.assert_not_called()
    db.rollback.assert_called()
