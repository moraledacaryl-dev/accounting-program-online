"""Synthetic isolated tests for the privacy-minimized live source parity probe."""
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/dr/live-source-parity.py"
WORKFLOW = ROOT / ".github/workflows/accounting-live-source-parity.yml"
spec = importlib.util.spec_from_file_location("accounting_live_source_parity", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def staff_row(identifier, *, revision=1, status="Completed", kind="payroll.run.paid"):
    payload = json.dumps({
        "external_id": identifier,
        "source_revision": revision,
        "payload": {"net_pay": 999999, "name": "PRIVATE STAFF NAME"},
    })
    return identifier, status, kind, payload


def test_real_source_id_mapping_and_no_false_equation_between_delivery_and_posting(capsys):
    accounting = [
        ("staff", "payroll:1", 2, "ready_for_review"),
        ("inventory", "inv-uuid", 1, "ready_for_review"),
    ]
    inventory = [("inv-uuid", "completed"), ("inv-failed", "failed")]
    staff = [
        staff_row("payroll:1", revision=2),
        staff_row("payroll:2", status="Retry"),
        staff_row("employee:3", kind="employee.sync"),
    ]
    report = audit.compare_live_rows(accounting, inventory, staff)
    assert report["staff"]["source_financial_events"] == 2
    assert report["staff"]["present_in_accounting"] == 1
    assert report["staff"]["source_marked_delivered"] == 1
    assert report["staff"]["pending_and_receipt_not_found"] == 1
    assert report["inventory"]["source_financial_events"] == 2
    assert report["inventory"].get("delivered_but_receipt_not_found", 0) == 0
    assert report["inventory"]["source_status_failed"] == 1
    audit.render(report)
    output = capsys.readouterr().out
    assert "payroll:1" not in output and "inv-uuid" not in output
    assert "PRIVATE" not in output and "999999" not in output
    assert "SOURCE_COMPLETED_MEANS_ACCOUNTING_ACCEPTED=NO" in output
    assert "CROSS_DATABASE_ATOMIC_SNAPSHOT=NO" in output


def test_inventory_source_domain_counts_are_aggregated_without_source_ids(capsys):
    from sqlalchemy import text
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE purchase_orders (id TEXT, approved_at TEXT)"
        )
        connection.exec_driver_sql("CREATE TABLE goods_receipts (id TEXT)")
        connection.exec_driver_sql("CREATE TABLE purchase_returns (id TEXT)")
        connection.exec_driver_sql(
            "CREATE TABLE stock_documents (id TEXT, status TEXT)"
        )
        connection.exec_driver_sql(
            "INSERT INTO purchase_orders VALUES ('PRIVATE-PO-1', NULL),"
            " ('PRIVATE-PO-2', '2026-10-21')"
        )
        connection.exec_driver_sql(
            "INSERT INTO goods_receipts VALUES ('PRIVATE-GRN-1')"
        )
        connection.exec_driver_sql(
            "INSERT INTO stock_documents VALUES ('PRIVATE-STOCK-1', 'posted'),"
            " ('PRIVATE-STOCK-2','draft')"
        )
        rows = connection.execute(text(audit.INVENTORY_DOMAIN_SQL)).all()
    engine.dispose()
    assert len(rows) == 1
    names = ("purchase_orders", "approved_purchase_orders",
             "goods_receipts", "purchase_returns", "posted_stock_documents")
    activity = dict(zip(names, (int(v) for v in rows[0])))
    assert activity == {
        "purchase_orders": 2,
        "approved_purchase_orders": 1,
        "goods_receipts": 1,
        "purchase_returns": 0,
        "posted_stock_documents": 1,
    }
    audit.render(audit.compare_live_rows([], [], []), inventory_domain=activity)
    out = capsys.readouterr().out
    assert "LIVE SOURCE DOMAIN: inventory.goods_receipts=1" in out
    assert "ACTIVITY_AND_OUTBOX_SNAPSHOTS_ATOMIC=NO" in out
    assert "HISTORICAL_ROWS_MAY_PRECEDE_INTEGRATION=YES" in out
    assert "PRIVATE-" not in out


def test_inventory_domain_report_rejects_bad_or_private_fields():
    baseline = {
        "purchase_orders": 0, "approved_purchase_orders": 0,
        "goods_receipts": 0, "purchase_returns": 0,
        "posted_stock_documents": 0,
    }
    for broken in (
        {**baseline, "supplier_name": "secret"},
        {**baseline, "goods_receipts": -1},
        {**baseline, "goods_receipts": "1"},
    ):
        with pytest.raises(ValueError, match="Unexpected Inventory"):
            audit.render(audit.compare_live_rows([], [], []), inventory_domain=broken)


def test_zero_inventory_and_staff_events_are_explicit_not_missing_from_report(capsys):
    report = audit.compare_live_rows([], [], [])
    for name in ("inventory", "staff"):
        assert report[name]["source_financial_events"] == 0
        assert report[name]["accounting_received"] == 0
        assert report[name]["present_in_accounting"] == 0
    audit.render(report)
    output = capsys.readouterr().out
    assert "inventory.source_financial_events=0" in output
    assert "staff.source_financial_events=0" in output


def test_delivered_without_accounting_record_requires_review_not_automatic_replay():
    report = audit.compare_live_rows([], [("inv-only", "completed")],
                                     [staff_row("staff-only", status="Completed")])
    assert report["inventory"]["delivered_but_receipt_not_found"] == 1
    assert report["staff"]["delivered_but_receipt_not_found"] == 1
    assert report["inventory"]["source_marked_delivered"] == 1
    assert report["staff"]["source_marked_delivered"] == 1


def test_accounting_only_identity_and_duplicate_receiver_are_aggregated():
    report = audit.compare_live_rows(
        [("staff", "only-in-accounting", 1, "ready_for_review"),
         ("staff", "only-in-accounting", 1, "ready_for_review"),
         ("inventory", "inv-id", 1, "accepted")],
        [],
        [],
    )
    assert report["staff"]["duplicate_receiver_identity"] == 1
    assert report["staff"]["receiver_id_absent_from_source_scan"] == 1
    assert report["inventory"]["receiver_id_absent_from_source_scan"] == 1


def test_staff_revision_validation_is_fail_closed_and_employee_sync_is_excluded():
    bad = ("payroll:1", "Completed", "payroll.run.paid",
           json.dumps({"external_id": "wrong", "source_revision": 1}))
    with pytest.raises(ValueError, match="Inconsistent"):
        audit.compare_live_rows([], [], [bad])
    report = audit.compare_live_rows([], [], [("employee:2", "Completed", "employee.sync", "{bad")])
    assert report["staff"].get("source_financial_events", 0) == 0


def test_staff_sqlite_readonly_scan_and_non_mutation(tmp_path):
    file = tmp_path / "staff.sqlite"
    with sqlite3.connect(file) as db:
        db.execute("""CREATE TABLE integration_outbox (
            external_id TEXT, status TEXT, event_type TEXT, payload_json TEXT,
            destination TEXT, external_source TEXT
        )""")
        db.execute(
            "INSERT INTO integration_outbox VALUES(?,?,?,?,?,?)",
            ("staff-in", "Pending", "cash_advance.repaid",
             json.dumps({"external_id": "staff-in", "source_revision": 1}),
             "accounting", "hidden_oasis_staff_payroll"),
        )
        db.execute(
            "INSERT INTO integration_outbox VALUES(?,?,?,?,?,?)",
            ("staff-other", "Completed", "employee.sync",
             json.dumps({"external_id": "staff-other", "source_revision": 1}),
             "accounting", "hidden_oasis_staff_payroll"),
        )
        db.commit()
    rows = audit.read_staff_sqlite(str(file))
    assert len(rows) == 1
    assert audit.compare_live_rows([], [], rows)["staff"]["source_financial_events"] == 1
    with sqlite3.connect(file) as db:
        assert db.execute("SELECT count(*) FROM integration_outbox").fetchone()[0] == 2


def test_sql_selects_only_and_workflow_does_not_enable_automatic_posts():
    assert audit.INVENTORY_SQL.lstrip().upper().startswith("SELECT")
    assert audit.ACCOUNTING_SQL.lstrip().upper().startswith("SELECT")
    body = SCRIPT.read_text()
    workflow = WORKFLOW.read_text()
    assert "SET TRANSACTION READ ONLY" in body
    assert "connection.rollback()" in body
    assert "PRAGMA query_only=ON" in body
    assert "mode=ro" in body
    assert "print(f\"LIVE SOURCE PARITY: NOT_CERTIFIED" in body
    assert "workflow_dispatch:" in workflow and "push:" in workflow
    assert 'git -C "$SOURCE" show "$AUDIT_SHA:scripts/dr/live-source-parity.py"' in workflow
    assert "restore-rehearsal" not in workflow
    assert "pg_restore" not in workflow


@pytest.mark.parametrize("value", ["sqlite:///other", "postgresql+asyncpg://server/db", ""])
def test_postgres_url_rejects_unsafe_or_unsupported_sources(value):
    with pytest.raises(ValueError):
        audit._pg_url(value)
