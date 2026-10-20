#!/usr/bin/env python3
"""Privacy-safe, read-only root-cause profiling for cash entries without journal IDs.

Only aggregate counts are printed to CI. Exact references, sources, account IDs,
customer data and amounts remain on the production database/private worklist.
Same-date/amount journal overlaps are CANDIDATES, not reconciliation evidence.
"""
from __future__ import annotations

import os
import sys
from time import perf_counter

from sqlalchemy import create_engine, text

UNLINKED = "t.status = 'posted' AND t.journal_entry_id IS NULL"

PROFILE_SQL = f"""
SELECT count(*) AS unlinked,
       count(DISTINCT COALESCE(NULLIF(trim(t.external_source),''),'(missing)')) AS distinct_sources,
       count(DISTINCT COALESCE(NULLIF(trim(t.module),''),'(missing)')) AS distinct_modules,
       count(DISTINCT COALESCE(NULLIF(trim(t.category),''),'(missing)')) AS distinct_categories,
       count(DISTINCT COALESCE(NULLIF(trim(t.created_by),''),'(missing)')) AS distinct_creators,
       count(DISTINCT t.financial_account_id) AS affected_accounts,
       coalesce(sum(CASE WHEN t.direction = 'in' THEN 1 ELSE 0 END),0) AS money_in_count,
       coalesce(sum(CASE WHEN t.direction = 'out' THEN 1 ELSE 0 END),0) AS money_out_count,
       coalesce(sum(CASE WHEN trim(coalesce(t.external_source,'')) <> '' THEN 1 ELSE 0 END),0) AS with_source,
       coalesce(sum(CASE WHEN trim(coalesce(t.external_id,'')) <> '' THEN 1 ELSE 0 END),0) AS with_external_id,
       coalesce(sum(CASE WHEN t.receivable_id IS NOT NULL OR t.payable_id IS NOT NULL
                    THEN 1 ELSE 0 END),0) AS linked_subledger,
       coalesce(sum(CASE WHEN t.bir_include THEN 1 ELSE 0 END),0) AS included_in_bir
FROM money_transactions t
WHERE {UNLINKED}
"""

STREAM_SQL = f"""
WITH streams AS (
  SELECT DISTINCT t.financial_account_id,
       coalesce(trim(t.external_source),'') AS source_key,
       coalesce(trim(t.module),'') AS module_key
  FROM money_transactions t
  WHERE {UNLINKED}
), related AS (
  SELECT t.id, t.status, t.journal_entry_id
  FROM money_transactions t
  WHERE EXISTS (
    SELECT 1 FROM streams s
    WHERE s.financial_account_id = t.financial_account_id
      AND s.source_key = coalesce(trim(t.external_source),'')
      AND s.module_key = coalesce(trim(t.module),'')
  )
)
SELECT count(*) AS same_stream_all_statuses,
       coalesce(sum(CASE WHEN status = 'posted' THEN 1 ELSE 0 END),0) AS same_stream_posted,
       coalesce(sum(CASE WHEN status = 'posted' AND journal_entry_id IS NOT NULL
                    THEN 1 ELSE 0 END),0) AS same_stream_posted_with_journal,
       coalesce(sum(CASE WHEN status = 'posted' AND journal_entry_id IS NULL
                    THEN 1 ELSE 0 END),0) AS same_stream_posted_without_journal
FROM related
"""

CANDIDATES_SQL = f"""
SELECT count(*) AS unlinked,
       coalesce(sum(CASE WHEN candidates = 0 THEN 1 ELSE 0 END),0) AS no_same_date_amount_candidates,
       coalesce(sum(CASE WHEN candidates = 1 THEN 1 ELSE 0 END),0) AS one_same_date_amount_candidate,
       coalesce(sum(CASE WHEN candidates > 1 THEN 1 ELSE 0 END),0) AS ambiguous_same_date_amount_candidates
FROM (
  SELECT t.id, count(DISTINCT j.id) AS candidates
  FROM money_transactions t
  LEFT JOIN journal_entries j
    ON j.status = 'posted'
   AND j.entry_date = t.transaction_date
   AND EXISTS (
      SELECT 1 FROM journal_lines l
      WHERE l.journal_entry_id = j.id
        AND (abs(coalesce(l.debit,0) - t.amount) <= 0.01
          OR abs(coalesce(l.credit,0) - t.amount) <= 0.01)
   )
  WHERE {UNLINKED}
  GROUP BY t.id
) matched
"""

DISTRIBUTION_SQL = f"""
WITH groups AS (
  SELECT coalesce(nullif(trim(t.external_source),''),'(missing)') AS source_key,
         coalesce(nullif(trim(t.module),''),'(missing)') AS module_key,
         count(*) AS n
  FROM money_transactions t
  WHERE {UNLINKED}
  GROUP BY source_key, module_key
)
SELECT count(*) AS distinct_source_module_groups,
       coalesce(max(n),0) AS largest_group_count,
       coalesce(sum(CASE WHEN n = 1 THEN 1 ELSE 0 END),0) AS single_transaction_groups
FROM groups
"""

QUERIES = {
    "profile": PROFILE_SQL,
    "same_stream": STREAM_SQL,
    "journal_candidates": CANDIDATES_SQL,
    "distribution": DISTRIBUTION_SQL,
}

def gather(db):
    totals = {}
    timings = {}
    for key, sql in QUERIES.items():
        start = perf_counter()
        totals[key] = {k: int(value or 0) for k, value in
                       db.execute(text(sql)).mappings().one().items()}
        timings[key] = int((perf_counter() - start) * 1000)
    n = totals["profile"]["unlinked"]
    if totals["journal_candidates"]["unlinked"] != n:
        raise ValueError("Journal candidate coverage does not match population")
    if totals["same_stream"]["same_stream_posted_without_journal"] != n:
        raise ValueError("Origin stream coverage does not match unlinked population")
    if sum(totals["journal_candidates"][key] for key in (
        "no_same_date_amount_candidates", "one_same_date_amount_candidate",
        "ambiguous_same_date_amount_candidates",
    )) != n:
        raise ValueError("Journal candidate classification is incomplete")
    return totals, timings

def render(totals, timings):
    print("JOURNAL_ORIGIN_PROFILE: mode=READ_ONLY_AGGREGATES")
    for group, row in totals.items():
        for key, value in row.items():
            print(f"JOURNAL_ORIGIN_PROFILE: {group}.{key}={value}")
        print(f"JOURNAL_ORIGIN_PROFILE: duration_ms.{group}={timings[group]}")
    print("JOURNAL_ORIGIN_PROFILE: source_names_account_identifiers_amounts=NOT_EXPORTED")
    print("JOURNAL_ORIGIN_PROFILE: same_date_amount_candidates_are_NOT_VERIFIED_LINKS")
    print("JOURNAL_ORIGIN_PROFILE: no_accounting_data_writes=true")

def main():
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise SystemExit("Production PostgreSQL DATABASE_URL is required")
    engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            connection.exec_driver_sql("SET LOCAL statement_timeout = '30000ms'")
            totals, timings = gather(connection)
            connection.rollback()
        render(totals, timings)
    finally:
        engine.dispose()

if __name__ == "__main__":
    sys.exit(main())
