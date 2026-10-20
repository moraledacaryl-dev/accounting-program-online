"""No data mutation or PII disclosure in historical journal-linkage triage."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from sqlalchemy import create_engine


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/dr/journal-linkage-triage.py"
spec = spec_from_file_location("journal_linkage_triage", SCRIPT)
triage = module_from_spec(spec)
spec.loader.exec_module(triage)


def test_zero_missing_linkage_does_not_invent_work():
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as db:
            db.exec_driver_sql("""CREATE TABLE journal_entries
                (id INTEGER PRIMARY KEY, status TEXT, reference_no TEXT)""")
            db.exec_driver_sql("""CREATE TABLE money_transactions (
                id INTEGER PRIMARY KEY, status TEXT, journal_entry_id INTEGER,
                transaction_date TEXT, posted_at TEXT, module TEXT,
                reference_no TEXT, external_source TEXT, external_id TEXT,
                linked_record_id INTEGER, reversed_from_id INTEGER,
                is_reversed BOOLEAN, financial_account_id INTEGER)""")
        with engine.connect() as db:
            overall, modules, years, elapsed = triage.gather(db)
            assert overall["unlinked_total"] == 0
            assert sum(modules.values()) == 0
            assert sum(years.values()) == 0
            assert elapsed >= 0
    finally:
        engine.dispose()


def test_triage_counts_ambiguous_reference_candidates_without_linking(capsys):
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as db:
            db.exec_driver_sql("""CREATE TABLE journal_entries
                (id INTEGER PRIMARY KEY, status TEXT, reference_no TEXT)""")
            db.exec_driver_sql("""CREATE TABLE money_transactions (
                id INTEGER PRIMARY KEY, status TEXT, journal_entry_id INTEGER,
                transaction_date TEXT, posted_at TEXT, module TEXT,
                reference_no TEXT, external_source TEXT, external_id TEXT,
                linked_record_id INTEGER, reversed_from_id INTEGER,
                is_reversed BOOLEAN, financial_account_id INTEGER)""")
            db.exec_driver_sql("""INSERT INTO journal_entries VALUES
                (1,'posted','ref-abc'), (2,'posted','REF-ABC'),
                (3,'draft','ref-draft'), (4,'posted','ref-one')""")
            db.exec_driver_sql("""INSERT INTO money_transactions VALUES
                (1,'posted',NULL,'2025-01-12','2025-01-12','rooms','ref-abc',NULL,NULL,11,NULL,0,1),
                (2,'posted',NULL,'2025-05-12','','finance','ref-one','beds24','remote-2',NULL,NULL,0,1),
                (3,'posted',NULL,'2026-09-12','2026-09-12','Unexpected Guest Name','ref-draft',NULL,NULL,NULL,NULL,0,2),
                (4,'posted',NULL,'2024-12-31','2024-12-31',NULL,NULL,NULL,NULL,NULL,1,1),
                (5,'posted',4,'2026-10-12','2026-10-12','events','ref-draft',NULL,NULL,NULL,NULL,0,2),
                (6,'reversed',NULL,'2026-10-12','2026-10-12','events','ref-abc',NULL,NULL,NULL,NULL,1,2)""")
        with engine.connect() as db:
            overall, modules, years, elapsed = triage.gather(db)
            assert overall["unlinked_total"] == 4
            assert overall["affected_financial_accounts"] == 2
            assert overall["reference_missing"] == 1
            assert overall["without_reference_candidate"] == 2
            assert overall["one_reference_candidate"] == 1
            assert overall["ambiguous_reference_candidates"] == 1
            assert overall["with_record_id"] == 1
            assert overall["with_external_event_identity"] == 1
            assert overall["reversal_marked"] == 1
            assert overall["missing_posted_timestamp"] == 1
            assert modules == {"rooms": 1, "finance": 1, "other": 1, "unspecified": 1}
            assert years == {"2024": 1, "2025": 2, "2026": 1}
            triage.report(overall, modules, years, elapsed)
            logs = capsys.readouterr().out
            assert "status=posted" not in logs
            assert "ref-abc" not in logs
            assert "Unexpected Guest Name" not in logs
            assert "remote-2" not in logs
            assert "module.other=1" in logs
            assert "candidate_reference_is_not_proof=true" in logs
    finally:
        engine.dispose()


def test_triage_source_is_read_only_and_workflow_never_logs_source_rows():
    script = SCRIPT.read_text()
    for sql in (triage.COUNT_SQL, triage.GROUP_SQL, triage.YEAR_SQL):
        assert sql.lstrip().upper().startswith("WITH")
        assert "WHERE t.status = 'posted' AND t.journal_entry_id IS NULL" in sql
        for token in ("DELETE FROM", "UPDATE ", "INSERT INTO", "DROP TABLE"):
            assert token not in sql.upper()
    assert "SET TRANSACTION READ ONLY" in script
    assert "db.rollback()" in script
    assert "db.commit()" not in script
    workflow = (ROOT / ".github/workflows/accounting-journal-linkage-triage.yml").read_text()
    assert "branches: [main]" in workflow
    assert "scripts/dr/journal-linkage-triage.py" in workflow
    assert "git -C \"$SOURCE\" show \"$AUDIT_SHA:scripts/dr/journal-linkage-triage.py\"" in workflow
