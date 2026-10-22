"""Synthetic, read-only payment.refunded evidence checks."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/dr/pos_refund_evidence.py"
WORKFLOW = ROOT / ".github/workflows/accounting-pos-direct-parity.yml"
spec = spec_from_file_location("pos_refund_evidence", SCRIPT)
audit = module_from_spec(spec)
spec.loader.exec_module(audit)


def event(tender="gcash", payment_id=17, amount=250, account_id=12, status="synced"):
    payload = {"payment": {"tender_type": tender, "id": payment_id,
                "amount": amount, "accounting_financial_account_id": account_id},
               "guest_name": "PRIVATE GUEST", "reference_no": "SECRET-GCASH"}
    return ("payment.refunded", status, json.dumps(payload))


def test_posted_refund_requires_correct_direction_amount_method_and_account(capsys):
    receiving = [("refund-payment:17", "posted", "in", 249.99, 14,
                  "POS Refund", "cash", False)]
    found = audit.compare_refunds([event()], receiving)
    assert found["refund_direct_cash_receipt_matched"] == 1
    assert found["refund_receiver_wrong_direction"] == 1
    assert found["refund_receiver_amount_mismatch"] == 1
    assert found["refund_receiver_account_mismatch"] == 1
    assert found["refund_receiver_tender_mismatch"] == 1
    print(found)
    captured = capsys.readouterr().out
    assert "PRIVATE" not in captured
    assert "SECRET" not in captured
    assert "refund-payment:17" not in captured


def test_refund_review_delivery_is_not_posted_cash():
    expected = "pos:cash:refund-payment:17"
    matched = audit.compare_refunds([event()], [], [(expected, "ready_for_review")])
    assert matched["refund_review_receipt_matched"] == 1
    assert matched["refund_review_pending_acceptance"] == 1
    assert matched["refund_direct_cash_receipt_matched"] == 0
    assert matched["synced_refund_without_receipt"] == 0


def test_room_charge_refund_has_distinct_owner_not_negative_money_refund():
    matched = audit.compare_refunds([event("room_charge")], [], [])
    assert matched["room_charge_refund_owned_by_separate_reversal"] == 1
    assert matched["source_refund_without_cash_or_review_receipt"] == 0


def test_receiver_duplicate_and_correct_cash_proof():
    rows = [("refund-payment:17", "posted", "out", 250, 12, "POS Refund", "gcash", False)]
    matched = audit.compare_refunds([event()], rows + rows)
    assert matched["duplicate_receiver_refund_identity"] == 1
    assert matched["refund_receiver_wrong_direction"] == 0
    assert matched["refund_receiver_amount_mismatch"] == 0
    assert matched["refund_receiver_account_mismatch"] == 0


@pytest.mark.parametrize("invalid", ['{', '[]', 'null'])
def test_malformed_refund_fails_closed(invalid):
    with pytest.raises(ValueError):
        audit.compare_refunds([("payment.refunded", "synced", invalid)], [])


def test_exact_sha_workflow_stages_refund_helper_and_audit_is_select_only():
    workflow = WORKFLOW.read_text()
    assert 'show "$AUDIT_SHA:scripts/dr/pos_refund_evidence.py"' in workflow
    assert 'test -s "$refund_file"' in workflow
    assert '"$CURRENT/backend/.venv/bin/python" -B "$audit_file"' in workflow
    assert audit.REFUND_SQL.strip().upper().startswith("SELECT")
    for text in ("insert into", "update money", "delete from"):
        assert text not in audit.REFUND_SQL.lower()
