"""Group 6: production baseline must remain read-only and redact financial data."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from sqlalchemy import create_engine

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/dr/production-certification.py'
spec = spec_from_file_location("accounting_production_certification", SCRIPT)
audit = module_from_spec(spec)
spec.loader.exec_module(audit)


@pytest.fixture
def connection():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as db:
        db.exec_driver_sql("""CREATE TABLE journal_entries (
            id INTEGER PRIMARY KEY, status TEXT)""")
        db.exec_driver_sql("""CREATE TABLE journal_lines (
            id INTEGER PRIMARY KEY, journal_entry_id INTEGER,
            debit NUMERIC, credit NUMERIC)""")
        db.exec_driver_sql("""CREATE TABLE records (
            id INTEGER PRIMARY KEY, amount NUMERIC, workflow_status TEXT,
            payment_method TEXT)""")
        db.exec_driver_sql("""CREATE TABLE record_settlements (
            id INTEGER PRIMARY KEY, record_id INTEGER, amount NUMERIC)""")
        db.exec_driver_sql("""CREATE TABLE receivables (
            id INTEGER PRIMARY KEY, gross_amount NUMERIC,
            amount_collected NUMERIC, balance_due NUMERIC)""")
        db.exec_driver_sql("""CREATE TABLE payables (
            id INTEGER PRIMARY KEY, gross_amount NUMERIC,
            amount_paid NUMERIC, balance_due NUMERIC)""")
        db.exec_driver_sql("""CREATE TABLE money_transactions (
            id INTEGER PRIMARY KEY, status TEXT, amount NUMERIC,
            journal_entry_id INTEGER)""")
        db.exec_driver_sql("""CREATE TABLE integration_review_items (
            id INTEGER PRIMARY KEY, source_app TEXT, source_event_id TEXT,
            status TEXT, financial_effect TEXT,
            accepted_transaction_id INTEGER, accepted_journal_entry_id INTEGER,
            accepted_receivable_id INTEGER, accepted_payable_id INTEGER)""")
        db.exec_driver_sql("""CREATE TABLE bookings (
            id INTEGER PRIMARY KEY, external_source TEXT,
            external_booking_id TEXT)""")
        db.exec_driver_sql("INSERT INTO journal_entries VALUES (1, 'posted')")
        db.exec_driver_sql("INSERT INTO journal_lines VALUES (1, 1, 100.0000, 0.0), (2, 1, 0.0, 100.0000)")
        db.exec_driver_sql("INSERT INTO records VALUES (10, 100.0, 'approved', 'on_account')")
        db.exec_driver_sql("INSERT INTO record_settlements VALUES (3, 10, 50.0)")
        db.exec_driver_sql("INSERT INTO receivables VALUES (10, 100, 50, 50)")
        db.exec_driver_sql("INSERT INTO payables VALUES (10, 250, 100, 150)")
        db.exec_driver_sql("INSERT INTO money_transactions VALUES (10, 'posted', 50, 1)")
        db.exec_driver_sql("INSERT INTO bookings VALUES (10, 'beds24', 'B1'), (11, 'beds24', 'B2')")
    with engine.connect() as db:
        yield db
    engine.dispose()


def test_clean_read_only_baseline_returns_only_aggregates(connection, capsys):
    metrics, runtimes = audit.collect(connection)
    assert metrics["posted_journals"]["entries"] == 1
    assert metrics["posted_journals"]["unbalanced_entries"] == 0
    assert metrics["posted_journals"]["invalid_lines"] == 0
    assert metrics["payables"]["balance_discrepancies"] == 0
    assert metrics["receivables"]["balance_discrepancies"] == 0
    assert all(duration >= 0 for duration in runtimes.values())
    assert audit.render(metrics, runtimes) == 0
    report = capsys.readouterr().out
    assert "status=NO_FINDINGS" in report
    assert "cash_balance_to_bank_statement=NOT_TESTED" in report
    assert "B1" not in report
    assert "100.0000" not in report
    assert "CERTIFICATION: posted_journals.entries=1" in report


def test_historical_coverage_and_overpayment_are_review_only(connection, capsys):
    connection.exec_driver_sql("INSERT INTO record_settlements VALUES (4, 10, 70)")
    connection.exec_driver_sql("INSERT INTO money_transactions VALUES (11, 'posted', 7, NULL)")
    connection.exec_driver_sql("INSERT INTO bookings VALUES (12, 'beds24', 'B1')")
    connection.exec_driver_sql("INSERT INTO receivables VALUES (11, 100, 30, 60)")
    metrics, runtime = audit.collect(connection)
    critical, review = audit.assessment(metrics)
    assert not critical
    assert metrics["settlement_evidence"]["over_settled_records"] == 1
    assert metrics["cash_coverage"]["legacy_posted_without_journal"] == 1
    assert metrics["beds24_links"]["duplicate_external_booking_id_groups"] == 1
    assert metrics["receivables"]["balance_discrepancies"] == 1
    assert audit.render(metrics, runtime) == 0
    assert "status=REVIEW_REQUIRED" in capsys.readouterr().out


def test_invalid_posted_journal_fails_without_modifying_data(connection, capsys):
    connection.exec_driver_sql("UPDATE journal_lines SET debit = 101 WHERE id = 1")
    connection.exec_driver_sql("INSERT INTO journal_lines VALUES (3, 1, -1, 3)")
    metrics, runtimes = audit.collect(connection)
    assert metrics["posted_journals"]["unbalanced_entries"] == 1
    assert metrics["posted_journals"]["invalid_lines"] == 1
    assert audit.render(metrics, runtimes) == 2
    assert "status=INTEGRITY_FAILURE" in capsys.readouterr().out
    assert connection.exec_driver_sql("SELECT count(*) FROM journal_lines").scalar_one() == 3


def test_sql_only_selects_and_production_transaction_forces_read_only():
    for sql in audit.AUDIT_QUERIES.values():
        assert sql.lstrip().upper().startswith("SELECT")
        assert not any(word in sql.upper() for word in (
            "DELETE FROM", "UPDATE ", "INSERT INTO", "DROP TABLE", "ALTER TABLE",
        ))
    source = SCRIPT.read_text()
    assert 'SET TRANSACTION READ ONLY' in source
    assert "connection.rollback()" in source
    assert "connection.commit()" not in source
    workflow = (ROOT / '.github/workflows/accounting-production-certification.yml').read_text()
    assert 'RESTORE-REHEARSAL' in workflow
    assert 'MODE: ${{ inputs.mode || ' + "'read_only'" + ' }}' in workflow
    assert 'push:' in workflow and 'branches: [main]' in workflow
    assert 'git -C "$SOURCE" show "$AUDIT_SHA:scripts/dr/production-certification.py"' in workflow


def test_integration_intake_summary_never_claims_sender_completeness(connection, capsys):
    connection.exec_driver_sql("""
        INSERT INTO integration_review_items
        (id,source_app,source_event_id,status,financial_effect,
         accepted_transaction_id,accepted_journal_entry_id,accepted_receivable_id,accepted_payable_id)
        VALUES
        (1,'inventory','opaque-inventory-event','ready_for_review','payable',NULL,NULL,NULL,NULL),
        (2,'staff','opaque-payroll','accepted','cash_out',10,NULL,NULL,NULL),
        (3,'pos','opaque-pos-review','accepted','journal_only',NULL,1,NULL,NULL)
    """)
    # Fixture money target 10 is posted, but it is a fixture that intentionally
    # does not demonstrate any upstream Staff sender outbox completeness.
    metrics, runtimes = audit.collect(connection)
    intake = metrics['integration_intake']
    assert intake['retained_events'] == 3
    assert intake['inventory_events'] == 1
    assert intake['staff_events'] == 1
    assert intake['pos_review_events'] == 1
    assert intake['waiting_for_review'] == 1
    assert intake['accepted_events'] == 2
    assert intake['missing_cash_target_ids'] == 0
    assert intake['missing_journal_target_ids'] == 0
    assert audit.render(metrics, runtimes) == 0
    printed = capsys.readouterr().out
    assert 'integration_upstream_producer_completeness=NOT_TESTED' in printed
    assert 'integration_pos_direct_sync=NOT_TESTED' in printed
    assert 'integration_secondary_journal_and_rounding_proof=NOT_TESTED' in printed
    assert 'opaque-inventory-event' not in printed
    assert 'opaque-payroll' not in printed


def test_accepted_intake_missing_and_dangling_targets_are_review_only(connection, capsys):
    connection.exec_driver_sql("""
        INSERT INTO integration_review_items
        (id,source_app,source_event_id,status,financial_effect,
         accepted_transaction_id,accepted_journal_entry_id,accepted_receivable_id,accepted_payable_id)
        VALUES
        (11,'staff','private-1','accepted','cash_out',NULL,NULL,NULL,NULL),
        (12,'inventory','private-2','accepted','payable',NULL,NULL,NULL,99999),
        (13,'inventory','private-3','accepted','reference_only',NULL,NULL,NULL,NULL),
        (14,'staff','private-4','accepted','receivable',NULL,NULL,NULL,NULL),
        (15,'pos','private-5','rejected','cash_in',NULL,NULL,NULL,NULL),
        (16,'pos','private-6','accepted','journal_only',NULL,99999,NULL,NULL)
    """)
    metrics, runtimes = audit.collect(connection)
    intake = metrics['integration_intake']
    assert intake['accepted_events'] == 5
    assert intake['missing_cash_target_ids'] == 1
    assert intake['missing_receivable_target_ids'] == 1
    assert intake['dangling_journal_target_ids'] == 1
    assert intake['dangling_payable_target_ids'] == 1
    assert intake['missing_payable_target_ids'] == 0
    assert intake['missing_journal_target_ids'] == 0
    critical, review = audit.assessment(metrics)
    assert not critical
    assert {(group, key) for group, key, _ in review if group == 'integration_intake'} == {
        ('integration_intake', 'missing_cash_target_ids'),
        ('integration_intake', 'missing_receivable_target_ids'),
        ('integration_intake', 'dangling_journal_target_ids'),
        ('integration_intake', 'dangling_payable_target_ids'),
    }
    assert audit.render(metrics, runtimes) == 0
    printed = capsys.readouterr().out
    assert 'status=REVIEW_REQUIRED' in printed
    assert 'private-' not in printed


def test_integration_intake_counts_posted_state_without_mutating_db(connection):
    connection.exec_driver_sql("INSERT INTO money_transactions VALUES (99, 'draft', 25, NULL)")
    connection.exec_driver_sql("""
        INSERT INTO integration_review_items
        (id,source_app,source_event_id,status,financial_effect,accepted_transaction_id)
        VALUES (21,'staff','opaque-status','accepted','cash_in',99)
    """)
    metrics, _ = audit.collect(connection)
    assert metrics['integration_intake']['accepted_cash_target_not_posted'] == 1
    assert connection.exec_driver_sql("SELECT status FROM money_transactions WHERE id=99").scalar_one() == 'draft'
