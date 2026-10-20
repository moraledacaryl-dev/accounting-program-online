#!/usr/bin/env python3
"""Group 6: privacy-minimized, read-only production financial integrity baseline.

No individual booking, guest, record, account ID, or monetary values are logged.
Observed legacy discrepancies are review work, not silently 'reconciled' here.
PostgreSQL transaction mode is read-only and the connection always rolls back.
"""
from __future__ import annotations

import os
import sys
from time import perf_counter

from sqlalchemy import create_engine, text


AUDIT_QUERIES = {
    "posted_journals": """
        SELECT count(*) AS entries,
               coalesce(sum(CASE WHEN nonzero_lines < 2 THEN 1 ELSE 0 END),0) AS incomplete_entries,
               coalesce(sum(CASE WHEN abs(debit_total - credit_total) > 0.0001 THEN 1 ELSE 0 END),0) AS unbalanced_entries,
               coalesce(sum(invalid_lines),0) AS invalid_lines,
               coalesce(sum(zero_lines),0) AS legacy_zero_lines
        FROM (
            SELECT entry.id,
                   count(CASE WHEN line.id IS NOT NULL
                        AND (coalesce(line.debit,0) != 0 OR coalesce(line.credit,0) != 0)
                        THEN 1 END) AS nonzero_lines,
                   coalesce(sum(line.debit),0) AS debit_total,
                   coalesce(sum(line.credit),0) AS credit_total,
                   coalesce(sum(CASE WHEN line.id IS NOT NULL AND (
                        line.debit IS NULL OR line.credit IS NULL
                        OR line.debit < 0 OR line.credit < 0
                        OR (line.debit > 0 AND line.credit > 0)
                   ) THEN 1 ELSE 0 END),0) AS invalid_lines,
                   coalesce(sum(CASE WHEN line.id IS NOT NULL AND
                        coalesce(line.debit,0) = 0 AND coalesce(line.credit,0) = 0
                        THEN 1 ELSE 0 END),0) AS zero_lines
            FROM journal_entries AS entry
            LEFT JOIN journal_lines AS line ON line.journal_entry_id = entry.id
            WHERE entry.status = 'posted'
            GROUP BY entry.id
        ) AS posted
    """,
    "settlement_evidence": """
        SELECT count(*) AS approved_credit_records,
               coalesce(sum(CASE WHEN paid > amount + 0.01 THEN 1 ELSE 0 END),0) AS over_settled_records,
               coalesce(sum(CASE WHEN paid < -0.01 THEN 1 ELSE 0 END),0) AS negative_paid_records
        FROM (
            SELECT record.id,
                   coalesce(record.amount,0) AS amount,
                   coalesce(sum(settlement.amount),0) AS paid
            FROM records AS record
            LEFT JOIN record_settlements AS settlement ON settlement.record_id = record.id
            WHERE record.workflow_status = 'approved'
              AND lower(trim(coalesce(record.payment_method,''))) IN ('credit','on_account')
            GROUP BY record.id, record.amount
        ) AS credit_records
    """,
    "receivables": """
        SELECT count(*) AS rows,
               coalesce(sum(CASE WHEN abs(coalesce(gross_amount,0)
                    - coalesce(amount_collected,0) - coalesce(balance_due,0)) > 0.01
                    THEN 1 ELSE 0 END),0) AS balance_discrepancies,
               coalesce(sum(CASE WHEN coalesce(amount_collected,0) < -0.01
                    THEN 1 ELSE 0 END),0) AS negative_collections
        FROM receivables
    """,
    "payables": """
        SELECT count(*) AS rows,
               coalesce(sum(CASE WHEN abs(coalesce(gross_amount,0)
                    - coalesce(amount_paid,0) - coalesce(balance_due,0)) > 0.01
                    THEN 1 ELSE 0 END),0) AS balance_discrepancies,
               coalesce(sum(CASE WHEN coalesce(amount_paid,0) < -0.01
                    THEN 1 ELSE 0 END),0) AS negative_payments
        FROM payables
    """,
    "cash_coverage": """
        SELECT count(*) AS money_transactions,
               coalesce(sum(CASE WHEN status = 'posted' AND journal_entry_id IS NULL
                    THEN 1 ELSE 0 END),0) AS legacy_posted_without_journal,
               coalesce(sum(CASE WHEN status = 'posted' AND amount < 0
                    THEN 1 ELSE 0 END),0) AS negative_posted_amounts
        FROM money_transactions
    """,
    "beds24_links": """
        SELECT count(*) AS duplicate_external_booking_id_groups
        FROM (
            SELECT trim(external_booking_id) AS external_id
            FROM bookings
            WHERE lower(coalesce(external_source,'')) = 'beds24'
              AND trim(coalesce(external_booking_id,'')) <> ''
            GROUP BY trim(external_booking_id)
            HAVING count(*) > 1
        ) AS duplicated
    """,
}

# Balance mismatches in old subledgers, undated settlements, and journal coverage
# gaps may have legitimate history. They REQUIRE REVIEW, not automatic correction.
CRITICAL_KEYS = {
    "posted_journals": ("unbalanced_entries", "invalid_lines"),
    "cash_coverage": ("negative_posted_amounts",),
}
REVIEW_KEYS = {
    "posted_journals": ("incomplete_entries", "legacy_zero_lines"),
    "settlement_evidence": ("over_settled_records", "negative_paid_records"),
    "receivables": ("balance_discrepancies", "negative_collections"),
    "payables": ("balance_discrepancies", "negative_payments"),
    "cash_coverage": ("legacy_posted_without_journal",),
    "beds24_links": ("duplicate_external_booking_id_groups",),
}


def collect(connection):
    """Execute only fixed aggregate SELECT statements; no identifiers/PII returned."""
    metrics = {}
    runtimes_ms = {}
    for check, sql in AUDIT_QUERIES.items():
        started = perf_counter()
        row = connection.execute(text(sql)).mappings().one()
        runtimes_ms[check] = int((perf_counter() - started) * 1000)
        metrics[check] = {key: int(value or 0) for key, value in row.items()}
    return metrics, runtimes_ms


def assessment(metrics):
    """Return failed integrity checks and review-only issues independently."""
    critical = [(group, key, metrics[group][key])
                for group, keys in CRITICAL_KEYS.items()
                for key in keys if metrics[group][key] > 0]
    review = [(group, key, metrics[group][key])
              for group, keys in REVIEW_KEYS.items()
              for key in keys if metrics[group][key] > 0]
    return critical, review


def render(metrics, runtimes_ms):
    critical, review = assessment(metrics)
    # Only bounded integer aggregates and duration metrics leave the server.
    print("CERTIFICATION: MODE=READ_ONLY")
    for group, fields in metrics.items():
        for field, value in fields.items():
            print(f"CERTIFICATION: {group}.{field}={value}")
        print(f"CERTIFICATION_TIMING: {group}.milliseconds={runtimes_ms[group]}")
    print(f"CERTIFICATION: critical_check_categories={len(critical)}")
    print(f"CERTIFICATION: review_check_categories={len(review)}")
    print("CERTIFICATION: status=" +
          ("INTEGRITY_FAILURE" if critical else "REVIEW_REQUIRED" if review else "NO_FINDINGS"))
    print("CERTIFICATION: cash_balance_to_bank_statement=NOT_TESTED")
    print("CERTIFICATION: source_documents_to_postings=NOT_TESTED")
    print("CERTIFICATION: reporting_query_timings_are_single_sample_not_SLA")
    return 2 if critical else 0


def main():
    url = os.environ.get("DATABASE_URL")
    if not url or not url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise SystemExit("Production PostgreSQL DATABASE_URL is required.")
    engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            # First statement within this transaction. SELECT queries below
            # cannot write even through an accidental future refactor.
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            connection.exec_driver_sql("SET LOCAL statement_timeout = '30000ms'")
            metrics, durations = collect(connection)
            connection.rollback()
        return render(metrics, durations)
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
