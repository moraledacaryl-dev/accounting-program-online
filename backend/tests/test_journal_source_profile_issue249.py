"""Prove source profiling publishes only counts and never auto-links journals."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/dr/journal-exception-source-profile.py"
spec = spec_from_file_location("journal_exception_source_profile", SCRIPT)
profile = module_from_spec(spec)
spec.loader.exec_module(profile)

def _database():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as db:
        db.exec_driver_sql("""CREATE TABLE money_transactions (
          id INTEGER PRIMARY KEY, status TEXT, journal_entry_id INTEGER,
          external_source TEXT, module TEXT, category TEXT, created_by TEXT,
          financial_account_id INTEGER, direction TEXT, external_id TEXT,
          receivable_id INTEGER, payable_id INTEGER, bir_include BOOLEAN,
          transaction_date TEXT, amount NUMERIC)""")
        db.exec_driver_sql("""CREATE TABLE journal_entries (
          id INTEGER PRIMARY KEY, status TEXT, entry_date TEXT)""")
        db.exec_driver_sql("""CREATE TABLE journal_lines (
          id INTEGER PRIMARY KEY, journal_entry_id INTEGER,
          debit NUMERIC, credit NUMERIC)""")
    return engine

def test_counts_unknown_sources_and_ledger_candidate_ambiguity_without_exposing_names(capsys):
    engine = _database()
    try:
        with engine.begin() as db:
            db.exec_driver_sql("""INSERT INTO money_transactions VALUES
              (1,'posted',NULL,'legacy','cash_book','Sensitive Category','private creator',1,'in','payor-1',NULL,NULL,0,'2025-02-01',100),
              (2,'posted',NULL,'legacy','cash_book','Sensitive Category','private creator',1,'out','payor-2',NULL,NULL,1,'2025-02-01',50),
              (3,'posted',NULL,'other_source','one-off','another category',NULL,2,'in','payor-3',NULL,NULL,0,'2026-01-01',25),
              (4,'posted',1,'legacy','cash_book','Sensitive Category','private creator',1,'in','payor-4',NULL,NULL,0,'2025-02-01',80),
              (5,'draft',NULL,'legacy','cash_book','Sensitive Category','private creator',1,'out','payor-5',NULL,NULL,0,'2025-02-01',50)""")
            db.exec_driver_sql("""INSERT INTO journal_entries VALUES
              (1,'posted','2025-02-01'), (2,'posted','2025-02-01'),
              (3,'posted','2025-02-01'), (4,'draft','2026-01-01')""")
            db.exec_driver_sql("""INSERT INTO journal_lines VALUES
              (1,1,100,0),(2,1,0,100),
              (3,2,100,0),(4,2,0,100),
              (5,3,50,0),(6,3,0,50),
              (7,4,25,0),(8,4,0,25)""")
        with engine.connect() as db:
            results, timing = profile.gather(db)
        assert results["profile"]["unlinked"] == 3
        assert results["profile"]["affected_accounts"] == 2
        assert results["profile"]["distinct_sources"] == 2
        assert results["profile"]["distinct_modules"] == 2
        assert results["profile"]["money_in_count"] == 2
        assert results["profile"]["money_out_count"] == 1
        assert results["profile"]["included_in_bir"] == 1
        assert results["same_stream"]["same_stream_all_statuses"] == 5
        assert results["same_stream"]["same_stream_posted"] == 4
        assert results["same_stream"]["same_stream_posted_with_journal"] == 1
        assert results["same_stream"]["same_stream_posted_without_journal"] == 3
        assert results["journal_candidates"]["no_same_date_amount_candidates"] == 1
        assert results["journal_candidates"]["one_same_date_amount_candidate"] == 1
        assert results["journal_candidates"]["ambiguous_same_date_amount_candidates"] == 1
        assert results["distribution"]["distinct_source_module_groups"] == 2
        assert results["distribution"]["largest_group_count"] == 2
        profile.render(results,timing)
        output=capsys.readouterr().out
        for secret in ["Sensitive Category","private creator","payor-1","legacy","one-off","cash_book","100"]:
            if secret=="100":
                continue
            assert secret not in output
        assert "same_date_amount_candidates_are_NOT_VERIFIED_LINKS" in output
    finally:
        engine.dispose()

def test_empty_population_and_fixed_read_only_guards():
    engine=_database()
    try:
        with engine.connect() as db:
            counts,_=profile.gather(db)
        assert counts["profile"]["unlinked"] == 0
        assert counts["journal_candidates"]["unlinked"] == 0
    finally:
        engine.dispose()
    for sql in profile.QUERIES.values():
        assert sql.strip().upper().startswith(("SELECT ", "WITH "))
        for operation in ("DELETE FROM","UPDATE ","INSERT INTO","DROP TABLE","ALTER TABLE"):
            assert operation not in sql.upper()
    source=SCRIPT.read_text()
    assert "SET TRANSACTION READ ONLY" in source
    assert "connection.rollback()" in source
    assert "connection.commit()" not in source
    workflow=(ROOT/".github/workflows/accounting-journal-exception-source-profile.yml").read_text()
    assert "branches: [main]" in workflow
    assert "workflow_dispatch:" in workflow
    assert "upload-artifact" not in workflow
    assert 'git -C "$SOURCE" show "$AUDIT_SHA:scripts/dr/journal-exception-source-profile.py"' in workflow
