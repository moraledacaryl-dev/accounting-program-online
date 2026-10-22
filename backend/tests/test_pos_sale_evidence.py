"""POS sale and void receipt checks use synthetic identities; no live writes."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json
import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/dr/pos_sale_evidence.py"
spec = spec_from_file_location("pos_sale_evidence", SOURCE)
helper = module_from_spec(spec)
spec.loader.exec_module(helper)


def event(kind, status, payload):
    return (kind, status, json.dumps({**payload, "guest_name": "SECRET_GUEST", "amount": 99999}))


def test_exact_sale_uuid_and_void_effect_not_conflated_with_gl(capsys):
    source = [
        event("order.finalized", "synced", {"order_uuid": "uuid-one", "order_no": "ORD-1"}),
        event("order.finalized", "synced", {"order_uuid": "uuid-two", "order_no": "ORD-2"}),
        event("order.finalized", "pending", {"order_uuid": "uuid-three", "order_no": "ORD-3"}),
        event("order.voided", "synced", {"order_no": "ORD-1"}),
        event("order.voided", "synced", {"order_no": "ORD-2"}),
        event("order.voided", "synced", {"order_no": "ORD-NO-SALE"}),
    ]
    sales = [
        ("uuid-one", "ORD-1", "voided", None, None, 1),
        ("unmatched-accounting-uuid", "ORD-2", "posted", 77, None, 0),
    ]
    report = helper.compare_sales(source, sales)
    assert report["source_finalized"] == 3
    assert report["matched_sale_uuid"] == 1
    assert report["sale_order_no_only_review_candidate"] == 1
    assert report["unsynced_sale_missing_receiver"] == 1
    assert report["void_status_and_event_received"] == 1
    assert report["synced_void_without_receiver_effect"] == 1
    assert report["void_no_receiver_sale_noop_candidate"] == 1
    assert report["accounting_sales_without_scanned_finalized_uuid"] == 1
    print(report)
    rendered = capsys.readouterr().out
    assert "uuid-one" not in rendered
    assert "ORD-1" not in rendered
    assert "SECRET_GUEST" not in rendered


def test_uuid_order_no_disagreement_and_duplicate_events():
    source = [
        event("order.finalized", "synced", {"order_uuid": "dup", "order_no": "ORDER-A"}),
        event("order.finalized", "synced", {"order_uuid": "dup", "order_no": "ORDER-A"}),
    ]
    output = helper.compare_sales(source, [("dup", "ORDER-B", "posted", None, None, 0)])
    assert output["matched_sale_uuid"] == 2
    assert output["duplicate_source_finalized_uuid"] == 1
    assert output["sale_uuid_order_no_mismatch"] == 2


@pytest.mark.parametrize("raw", ["{", "[]", "null"])
def test_malformed_scoped_pos_sale_fails_closed(raw):
    with pytest.raises(ValueError):
        helper.compare_sales([("order.finalized", "synced", raw)], [])


def test_sale_query_only_reads_scoped_accounting_receiver():
    query = helper.SALES_SQL.lower()
    assert "from sale_orders" in query
    assert "sale_void_events" in query
    assert "dedicated_pos_cloud" in query
    for word in ("insert into", "update sale_orders", "delete from", "drop table"):
        assert word not in query
