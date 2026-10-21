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
            ALTER TABLE money_transactions ADD COLUMN reference_no TEXT;
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


def test_reference_and_nearby_date_leads_are_unverified_and_do_not_expose_references():
    with TemporaryDirectory() as folder:
        staff, accounting = _fixture(Path(folder))
        with sqlite3.connect(accounting) as db:
            db.executemany(
                """INSERT INTO money_transactions(
                    id, external_source, external_id, direction, transaction_date,
                    amount, status, is_reversed, reference_no
                ) VALUES (?,?,?,?,?,?,?,?,?)""",
                [
                    (601,None,None,"in","2026-07-04",1000,"posted",0," SECRET-REFERENCE "),
                    (602,None,None,"in","2026-08-18",3000,"posted",0,"private-bank-ref"),
                    (603,None,None,"in","2026-09-20",3000,"posted",0,None),
                    (604,None,None,"out","2026-08-04",500,"posted",0,None),
                    (605,None,None,"in","2026-08-13",500,"posted",0,None),
                    (606,None,None,"in","2026-07-03",999,"posted",0,"secret-reference"),
                ],
            )
        before_staff, before_accounting = staff.read_bytes(), accounting.read_bytes()
        result = _run(staff, accounting)
        records = {r["repayment_id"]: r for r in result["worklist_sample"]}
        # Text reference equality and date/amount nearby leads are never
        # promoted to proven Accounting source identity.
        assert result["exact_source_identity_count"] == 3
        assert result["without_exact_source_identity_count"] == 2
        assert result["nearby_search_days"] == 7
        assert result["receipt_reference_matching_is_not_proof_of_cash_receipt"]
        assert records[15]["receipt_reference_match_eligible"] is True
        reference_candidates = records[15]["receipt_reference_cash_candidates"]
        assert {r["id"] for r in reference_candidates} == {601, 606}
        assert next(r for r in reference_candidates if r["id"] == 601)["amount_matches"]
        assert not next(r for r in reference_candidates if r["id"] == 606)["amount_matches"]
        assert {r["id"] for r in records[15]["nearby_date_amount_cash_candidates"]} == {601}
        assert records[15]["nearby_date_amount_cash_candidates"][0]["days_from_repayment"] == 2
        assert {r["id"] for r in records[30]["receipt_reference_cash_candidates"]} == {602}
        assert {r["id"] for r in records[30]["nearby_date_amount_cash_candidates"]} == {602}
        # Two different Staff receipts must NEVER consume one Money In as a
        # confirmed match just because dates and amounts agree.
        assert 603 in result["shared_nearby_date_candidate_ids"]
        assert {r["id"] for r in records[42]["nearby_date_amount_cash_candidates"]} == {603}
        assert {r["id"] for r in records[43]["nearby_date_amount_cash_candidates"]} == {603}
        # Outflow and outside-window entries are not repayment candidates.
        assert {r["id"] for r in records[29]["nearby_date_amount_cash_candidates"]} == set()
        assert "secret-reference" not in str(result).lower()
        assert "private-bank-ref" not in str(result).lower()
        assert staff.read_bytes() == before_staff
        assert accounting.read_bytes() == before_accounting


def test_date_window_is_bounded_and_can_be_disabled():
    with TemporaryDirectory() as folder:
        staff, accounting = _fixture(Path(folder))
        engine = create_engine(f"sqlite:///{accounting}")
        with sqlite3.connect(staff.resolve().as_uri() + "?mode=ro", uri=True) as staff_db:
            with engine.connect() as account_db:
                with pytest.raises(ValueError, match="between 0 and 31"):
                    reconcile(staff_db, account_db, lookaround_days=32)
                with pytest.raises(ValueError, match="between 0 and 31"):
                    reconcile(staff_db, account_db, lookaround_days=-1)
        engine.dispose()
        summary = _run(staff, accounting, limit=0)
        assert summary["nearby_search_days"] == 7
        assert summary["worklist_sample"] == []
        assert summary["sample_truncated"] is True
