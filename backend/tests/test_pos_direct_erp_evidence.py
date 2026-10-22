"""Synthetic POS -> Accounting direct-ERP linkage audit contract.

Never run a sending worker, replay any transaction, or access production data.
"""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/dr/pos-direct-erp-evidence.py"
WORKFLOW = ROOT / ".github/workflows/accounting-pos-direct-parity.yml"
spec = importlib.util.spec_from_file_location("pos_direct_erp_evidence", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def row(event_type, status, body):
    return event_type, status, json.dumps({
        **body,
        "guest_name": "PRIVATE GUEST",
        "note": "SECRET FINANCIAL NOTES",
        "amount": 999999,
    })


def test_pos_direct_cash_transfer_refund_and_room_charge_match_real_external_id_contract(capsys):
    source = [
        row("cash_movement.created", "synced", {
            "cash_event_uuid": "cashuuid1", "integration_identity_version": 2}),
        row("transfer.created", "synced", {
            "cash_event_uuid": "transferuuid1", "integration_identity_version": 2}),
        row("cash_movement.created", "synced", {
            "reference_no": "legacy-cash-uuid", "integration_identity_version": 1}),
        row("payment.collected", "synced", {
            "order_no": "ORD-11",
            "payment": {"tender_type": "gcash", "reference_no": "gcash-11"}}),
        row("payment.refunded", "synced", {
            "payment": {"id": 88, "tender_type": "cash", "reference_no": "same-paper-ref"}}),
        row("room_charge.request_created", "synced", {
            "room_charge_posting": {"posting_uuid": "room-11", "charge_amount": 110}}),
        row("order.finalized", "synced", {"order_uuid": "PRIVATE ORDER"}),
        row("order.voided", "pending", {"order_no": "PRIVATE ORDER"}),
        row("session.closed", "synced", {"session_code": "PRIVATE SESSION"}),
        row("payment.folio_pending", "synced", {"payment": {"tender_type": "room_charge"}}),
    ]
    receiving = {
        "money": [
            ("cash-movement:cashuuid1", "posted", False),
            ("legacy-cash-uuid", "posted", False),
            ("gcash-11", "posted", False),
            ("refund-payment:88", "posted", False),
        ],
        "transfer": [("cash-transfer:transferuuid1", "posted", False)],
        "receivable": [("room-charge:room-11", "open", None)],
    }
    report = audit.compare(source, receiving)
    assert report["pos_scoped_events"] == 10
    assert report["direct_target_expected"] == 6
    assert report["direct_target_present"] == 6
    assert report["synced_source_without_direct_target"] == 0
    assert report["not_compared_distinct_erp_endpoint"] == 3
    assert report["excluded_legitimate_no_cash_target"] == 1
    audit.render(report)
    output = capsys.readouterr().out
    for sensitive in ("PRIVATE GUEST", "PRIVATE ORDER", "SECRET FINANCIAL", "999999",
                      "cashuuid1", "gcash-11", "room-11", "legacy-cash-uuid"):
        assert sensitive not in output
    assert "POS_SYNCED_DOES_NOT_PROVE_GENERAL_LEDGER_JOURNAL=YES" in output
    assert "ACCOUNTING_REVIEW_INBOX_IS_NOT_GENERIC_POS_RECEIVER=YES" in output


def test_synced_without_receiver_and_receiver_without_ack_are_not_equated():
    source = [
        row("cash_movement.created", "synced", {"cash_event_uuid": "missing-v2",
                                                  "integration_identity_version": 2}),
        row("transfer.created", "failed", {"reference_no": "transfer-ack-missing"}),
    ]
    receiving = {"money": [], "transfer": [
        ("transfer-ack-missing", "draft", False)
    ], "receivable": []}
    report = audit.compare(source, receiving)
    assert report["synced_source_without_direct_target"] == 1
    assert report["receiver_exists_sender_not_synced"] == 1
    assert report["direct_cash_or_transfer_not_posted"] == 1
    assert report["direct_target_present"] == 1
    assert report["unsynced_source_without_direct_target"] == 0


def test_cash_reversal_and_duplicate_ledger_reference_are_separate_review_states():
    source = [row("payment.collected", "synced", {
        "order_no": "O1", "payment": {"tender_type": "cash", "reference_no": "ref-1"}})]
    receiving = {
        "money": [("ref-1", "posted", True), ("ref-1", "posted", False),
                  ("unrelated-dedicated-pos-ref", "posted", False)],
        "transfer": [], "receivable": [],
    }
    report = audit.compare(source, receiving)
    assert report["duplicate_accounting_external_identity"] == 1
    assert report["direct_cash_or_transfer_reversed"] == 1
    assert report["accounting_direct_targets_not_referenced_by_scanned_source"] == 1
    assert report["direct_target_present"] == 1


def test_skipped_nonfinancial_payments_refunds_and_negative_room_reversals_not_false_missing():
    source = [
        row("payment.collected", "synced", {"payment": {"tender_type": "room_charge"}}),
        row("payment.refunded", "synced", {"payment": {"tender_type": "room_charge", "id": 1}}),
        row("payment.refunded", "synced", {"payment": {"tender_type": "cash"}}),
        row("room_charge.request_created", "synced", {"room_charge_posting": {
            "posting_uuid": "negative-room", "charge_amount": -22}}),
    ]
    report = audit.compare(source, {"money": [], "transfer": [], "receivable": []})
    assert report["direct_target_expected"] == 0
    assert report["excluded_legitimate_no_cash_target"] == 2
    assert report["excluded_distinct_negative_room_charge_reversal"] == 1
    assert report["excluded_unverifiable_identity"] == 1


def test_no_pos_activity_exposes_zeros_instead_of_claiming_success():
    report = audit.compare([], {"money": [], "transfer": [], "receivable": []})
    assert report["pos_scoped_events"] == 0
    assert report["direct_target_expected"] == 0
    assert report["direct_target_present"] == 0
    assert report["accounting_direct_targets_not_referenced_by_scanned_source"] == 0


@pytest.mark.parametrize("bad", [
    ("payment.collected", "synced", "{private-malformed-json"),
    ("payment.collected", "synced", '["bad"]'),
    ("cash_movement.created", "synced", '{"integration_identity_version":"nonsense"}'),
    ("inventory.pos_order_finalized", "synced", "{}"),
])
def test_out_of_contract_source_event_fails_closed(bad):
    with pytest.raises(ValueError):
        audit.compare([bad], {"money": [], "transfer": [], "receivable": []})


def test_sql_and_workflow_use_read_only_credentials_and_no_transport_posting():
    source = SCRIPT.read_text()
    wf = WORKFLOW.read_text()
    assert audit.POS_SQL.lstrip().upper().startswith("SELECT")
    for sql in audit.RECEIPT_QUERIES.values():
        assert sql.lstrip().upper().startswith("SELECT")
    assert "SET TRANSACTION READ ONLY" in source
    assert "connection.rollback()" not in source  # fixed conn object uses conn.rollback()
    assert "conn.rollback()" in source
    assert "NOT_CERTIFIED (" in source
    assert "pos-backend.env" in wf and "accounting-backend.env" in wf
    assert 'git -C "$SOURCE" show "$AUDIT_SHA:scripts/dr/pos-direct-erp-evidence.py"' in wf
    assert "workflow_dispatch:" in wf and "push:" in wf
    assert "pg_restore" not in wf
    assert "deploy-release" not in wf
