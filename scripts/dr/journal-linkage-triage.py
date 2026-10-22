#!/usr/bin/env python3
"""Read-only aggregate triage of legacy posted cash movements without journal links.

The script reports counts only. Reference-number overlap is *not* evidence that
an existing journal belongs to the cash movement. Never auto-link or post.
"""
from __future__ import annotations

import os
import sys
from time import perf_counter

from sqlalchemy import create_engine, text


BASE_SQL = """
WITH pending AS (
  SELECT t.id, t.transaction_date, t.posted_at, t.module,
         t.reference_no, t.external_source, t.external_id,
         t.linked_record_id, t.reversed_from_id, t.is_reversed,
         t.financial_account_id,
         CASE WHEN trim(coalesce(t.reference_no,'')) = '' THEN 0
              ELSE (
                SELECT count(*)
                FROM journal_entries j
                WHERE j.status = 'posted'
                  AND j.reference_no IS NOT NULL
                  AND lower(trim(j.reference_no)) = lower(trim(t.reference_no))
              )
         END AS same_reference_journal_count,
         CASE WHEN trim(coalesce(t.reference_no,'')) = '' THEN 0
              ELSE (
                SELECT count(*) FROM money_transactions AS other
                WHERE other.status = 'posted' AND other.journal_entry_id IS NULL
                  AND lower(trim(coalesce(other.reference_no,''))) = lower(trim(t.reference_no))
              )
         END AS same_reference_unlinked_cash_count
  FROM money_transactions t
  WHERE t.status = 'posted' AND t.journal_entry_id IS NULL
)
"""
COUNT_SQL = BASE_SQL + """
SELECT count(*) AS unlinked_total,
       count(DISTINCT financial_account_id) AS affected_financial_accounts,
       sum(CASE WHEN trim(coalesce(reference_no,'')) = '' THEN 1 ELSE 0 END) AS reference_missing,
       sum(CASE WHEN same_reference_journal_count = 0 THEN 1 ELSE 0 END) AS without_reference_candidate,
       sum(CASE WHEN same_reference_journal_count = 1 THEN 1 ELSE 0 END) AS one_reference_candidate,
       sum(CASE WHEN same_reference_journal_count > 1 THEN 1 ELSE 0 END) AS ambiguous_reference_candidates,
       sum(CASE WHEN same_reference_unlinked_cash_count > 1 THEN 1 ELSE 0 END) AS cash_reference_shared_by_multiple_unlinked,
       sum(CASE WHEN same_reference_journal_count = 1
                    AND same_reference_unlinked_cash_count > 1 THEN 1 ELSE 0 END) AS unique_journal_candidate_shared_by_cash,
       sum(CASE WHEN same_reference_journal_count > 0
                    AND same_reference_unlinked_cash_count > 1 THEN 1 ELSE 0 END) AS ambiguous_cash_journal_reference_overlap,
       sum(CASE WHEN linked_record_id IS NOT NULL THEN 1 ELSE 0 END) AS with_record_id,
       sum(CASE WHEN trim(coalesce(external_source,'')) <> ''
                     AND trim(coalesce(external_id,'')) <> '' THEN 1 ELSE 0 END) AS with_external_event_identity,
       sum(CASE WHEN reversed_from_id IS NOT NULL OR is_reversed = true THEN 1 ELSE 0 END) AS reversal_marked,
       sum(CASE WHEN trim(coalesce(posted_at,'')) = '' THEN 1 ELSE 0 END) AS missing_posted_timestamp
FROM pending
"""
GROUP_SQL = BASE_SQL + """
SELECT CASE
         WHEN lower(trim(coalesce(module,''))) = 'rooms' THEN 'rooms'
         WHEN lower(trim(coalesce(module,''))) = 'events' THEN 'events'
         WHEN lower(trim(coalesce(module,''))) = 'cafe' THEN 'cafe'
         WHEN lower(trim(coalesce(module,''))) = 'finance' THEN 'finance'
         WHEN lower(trim(coalesce(module,''))) = 'payroll' THEN 'payroll'
         WHEN lower(trim(coalesce(module,''))) = 'pos' THEN 'pos'
         WHEN trim(coalesce(module,'')) = '' THEN 'unspecified'
         ELSE 'other'
       END AS module_bucket,
       count(*) AS records
FROM pending
GROUP BY module_bucket
"""
YEAR_SQL = BASE_SQL + """
SELECT CASE
         WHEN substr(coalesce(transaction_date,''),1,4) = '2024' THEN '2024'
         WHEN substr(coalesce(transaction_date,''),1,4) = '2025' THEN '2025'
         WHEN substr(coalesce(transaction_date,''),1,4) = '2026' THEN '2026'
         WHEN trim(coalesce(transaction_date,'')) = '' THEN 'undated'
         ELSE 'other'
       END AS transaction_year,
       count(*) AS records
FROM pending
GROUP BY transaction_year
"""

MODULES = ("rooms", "events", "cafe", "finance", "payroll", "pos", "unspecified", "other")
YEARS = ("2024", "2025", "2026", "undated", "other")


def gather(db):
    start = perf_counter()
    overall = {k: int(v or 0) for k, v in db.execute(text(COUNT_SQL)).mappings().one().items()}
    module_rows = {row["module_bucket"]: int(row["records"]) for row in db.execute(text(GROUP_SQL)).mappings()}
    year_rows = {row["transaction_year"]: int(row["records"]) for row in db.execute(text(YEAR_SQL)).mappings()}
    elapsed_ms = round((perf_counter() - start) * 1000)
    if sum(module_rows.values()) != overall["unlinked_total"]:
        raise ValueError("Module coverage does not agree with total.")
    if sum(year_rows.values()) != overall["unlinked_total"]:
        raise ValueError("Year coverage does not agree with total.")
    if (overall["without_reference_candidate"] + overall["one_reference_candidate"]
            + overall["ambiguous_reference_candidates"] != overall["unlinked_total"]):
        raise ValueError("Reference candidate coverage does not agree with total.")
    if set(module_rows).difference(MODULES) or set(year_rows).difference(YEARS):
        raise ValueError("Unexpected bucket detected.")
    return overall, module_rows, year_rows, elapsed_ms


def report(overall, modules, years, elapsed_ms):
    print("JOURNAL_LINKAGE_TRIAGE: MODE=READ_ONLY_AGGREGATES")
    for name, value in overall.items():
        print(f"JOURNAL_LINKAGE_TRIAGE: {name}={value}")
    for name in MODULES:
        print(f"JOURNAL_LINKAGE_TRIAGE: module.{name}={modules.get(name,0)}")
    for name in YEARS:
        print(f"JOURNAL_LINKAGE_TRIAGE: year.{name}={years.get(name,0)}")
    print(f"JOURNAL_LINKAGE_TRIAGE: elapsed_ms={elapsed_ms}")
    print("JOURNAL_LINKAGE_TRIAGE: candidate_reference_is_not_proof=true")
    print("JOURNAL_LINKAGE_TRIAGE: one_journal_to_many_cash_candidates_requires_human_review=true")
    print("JOURNAL_LINKAGE_TRIAGE: amount_and_identity_details=NOT_EXPORTED")
    print("JOURNAL_LINKAGE_TRIAGE: bank_statement_reconciliation=NOT_TESTED")


def main():
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise SystemExit("PostgreSQL DATABASE_URL required.")
    engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as db:
            db.exec_driver_sql("SET TRANSACTION READ ONLY")
            db.exec_driver_sql("SET LOCAL statement_timeout = '30000ms'")
            result = gather(db)
            db.rollback()
        report(*result)
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
