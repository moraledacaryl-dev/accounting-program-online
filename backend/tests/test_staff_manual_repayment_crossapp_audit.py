"""Regression coverage for cross-app read-only historical repayment reconciliation."""
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from sqlalchemy import create_engine

from scripts.audit_staff_manual_repayment_crossapp import reconcile


def _fixture(root: Path):
    staff_path = root / "staff.sqlite"
    accounting_path = root / "accounting.sqlite"
    with sqlite3.connect(staff_path) as staff:
        staff.executescript("""
            CREATE TABLE cash_advance_repayments (
                id INTEGER PRIMARY KEY, cash_advance_id INTEGER,
                repayment_date TEXT, amount REAL, source TEXT, active INTEGER,
                payment_method TEXT, method TEXT, reference TEXT
            );
            CREATE TABLE integration_outbox (
                id INTEGER PRIMARY KEY, destination TEXT,
                external_source TEXT, external_id TEXT, event_type TEXT
            );
            INSERT INTO cash_advance_repayments VALUES
                (15,12,'2026-07-02',1000,'Manual',1,'Cash','Cash','secret-reference'),
                (29,21,'2026-08-03',500,'Manual',1,'Cash','Cash',NULL),
                (30,26,'2026-08-15',3000,'Manual',1,'Other','Other','private-bank-ref'),
                (42,22,'2026-09-18',3000,'Manual',1,'Cash','Cash',NULL),
                (43,11,'2026-09-18',3000,'Manual',1,'Cash','Cash',NULL),
                (50,31,'2026-09-18',400,'Payroll',1,'Payroll deduction','Payroll deduction',NULL),
                (51,32,'2026-09-18',300,'Manual',1,'Cash','Cash',NULL);
            INSERT INTO integration_outbox VALUES
                (1,'accounting','hidden_oasis_staff_payroll',
                    'cash-advance-repayment:51','cash_advance.repaid');
        """)
    with sqlite3.connect(accounting_path) as accounting:
        accounting.executescript("""
            CREATE TABLE integration_review_items (
                id INTEGER PRIMARY KEY, source_app TEXT, source_event_id TEXT,
                status TEXT, financial_effect TEXT, accepted_transaction_id INTEGER
            );
            CREATE TABLE integration_receipts (
                id INTEGER PRIMARY KEY, external_source TEXT,
                external_id TEXT, event_type TEXT, status TEXT
            );
            CREATE TABLE money_transactions (
                id INTEGER PRIMARY KEY, external_source TEXT, external_id TEXT,
                direction TEXT, transaction_date TEXT, amount REAL,
                status TEXT, is_reversed INTEGER
            );
            INSERT INTO integration_review_items VALUES
                (101,'staff','cash-advance-repayment:15','accepted','cash_in',200),
                (102,'pos','cash-advance-repayment:29','accepted','cash_in',201);
            INSERT INTO integration_receipts VALUES
                (201,'hidden_oasis_staff_payroll','cash-advance-repayment:30',
                    'cash_advance.repaid','For Review'),
                (202,'another_app','cash-advance-repayment:29',
                    'cash_advance.repaid','Posted');
            INSERT INTO money_transactions VALUES
                (200,'staff','cash-advance-repayment:42','in','2026-09-18',
                    3000,'posted',0),
                (501,NULL,NULL,'in','2026-09-18',3000,'posted',0),
                (502,NULL,NULL,'in','2026-08-03',500,'posted',0),
                (503,NULL,NULL,'out','2026-08-15',3000,'posted',0);
        """)
    return staff_path, accounting_path


def _run(staff_path, accounting_path, *, limit=100):
    engine = create_engine(f"sqlite:///{accounting_path}")
    with sqlite3.connect(staff_path.resolve().as_uri() + "?mode=ro", uri=True) as staff:
        staff.execute("PRAGMA query_only=ON")
        with engine.connect() as accounting:
            accounting.exec_driver_sql("PRAGMA query_only=ON")
            report = reconcile(staff, accounting, sample_limit=limit)
            accounting.rollback()
    engine.dispose()
    return report


def test_cross_app_reconciliation_matches_exact_source_and_never_allocates_amount_candidates():
    with TemporaryDirectory() as folder:
        staff, accounting = _fixture(Path(folder))
        before_staff, before_accounting = staff.read_bytes(), accounting.read_bytes()
        report = _run(staff, accounting)
        assert report["read_only"] is True
        assert report["repayment_count"] == 5
        assert report["amount_php"] == 10500.0
        assert report["exact_source_identity_count"] == 3
        assert report["without_exact_source_identity_count"] == 2
        rows = {r["repayment_id"]: r for r in report["worklist_sample"]}
        assert [x["id"] for x in rows[15]["exact_review_items"]] == [101]
        assert rows[15]["exact_review_items"][0]["accepted_transaction_id"] == 200
        assert rows[29]["source_identity_found"] is False
        assert [x["id"] for x in rows[29]["same_date_amount_cash_candidates"]] == [502]
        assert [x["id"] for x in rows[30]["exact_legacy_receipts"]] == [201]
        assert [x["id"] for x in rows[42]["exact_money_transactions"]] == [200]
        assert rows[43]["source_identity_found"] is False
        assert report["shared_amount_date_candidate_ids"] == [200, 501]
        assert all(x["needs_manual_reconciliation"] for x in rows.values())
        assert all(x["has_receipt_reference"] for x in (rows[15], rows[30]))
        assert "private-bank-ref" not in str(report)
        assert "secret-reference" not in str(report)
        assert staff.read_bytes() == before_staff
        assert accounting.read_bytes() == before_accounting


def test_summary_only_keeps_counts_and_does_not_expose_cases():
    with TemporaryDirectory() as folder:
        staff, accounting = _fixture(Path(folder))
        report = _run(staff, accounting, limit=0)
        assert report["repayment_count"] == 5
        assert report["exact_source_identity_count"] == 3
        assert report["worklist_sample"] == []
        assert report["sample_truncated"] is True


def test_missing_accounting_schema_fails_closed():
    with TemporaryDirectory() as folder:
        staff, accounting = _fixture(Path(folder))
        with sqlite3.connect(accounting) as db:
            db.execute("DROP TABLE integration_receipts")
        with pytest.raises(Exception, match="integration_receipts"):
            _run(staff, accounting)
