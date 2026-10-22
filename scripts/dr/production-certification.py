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
    "integration_intake": """
        SELECT count(*) AS retained_events,
               coalesce(sum(CASE WHEN review.source_app = 'inventory' THEN 1 ELSE 0 END),0) AS inventory_events,
               coalesce(sum(CASE WHEN review.source_app = 'staff' THEN 1 ELSE 0 END),0) AS staff_events,
               coalesce(sum(CASE WHEN review.source_app = 'pos' THEN 1 ELSE 0 END),0) AS pos_review_events,
               coalesce(sum(CASE WHEN review.status = 'ready_for_review' THEN 1 ELSE 0 END),0) AS waiting_for_review,
               coalesce(sum(CASE WHEN review.status = 'ready_for_review' AND review.source_app='staff' THEN 1 ELSE 0 END),0) AS staff_waiting_for_review,
               coalesce(sum(CASE WHEN review.status = 'ready_for_review' AND review.source_app='pos' THEN 1 ELSE 0 END),0) AS pos_waiting_for_review,
               coalesce(sum(CASE WHEN review.status = 'ready_for_review' AND review.source_app='inventory' THEN 1 ELSE 0 END),0) AS inventory_waiting_for_review,
               coalesce(sum(CASE WHEN review.status = 'ready_for_review' AND review.financial_effect = 'cash_in' THEN 1 ELSE 0 END),0) AS pending_cash_in,
               coalesce(sum(CASE WHEN review.status = 'ready_for_review' AND review.financial_effect = 'cash_out' THEN 1 ELSE 0 END),0) AS pending_cash_out,
               coalesce(sum(CASE WHEN review.status = 'ready_for_review' AND review.financial_effect = 'settlement' THEN 1 ELSE 0 END),0) AS pending_settlement,
               coalesce(sum(CASE WHEN review.status = 'ready_for_review' AND review.financial_effect = 'journal_only' THEN 1 ELSE 0 END),0) AS pending_journal_only,
               coalesce(sum(CASE WHEN review.status = 'ready_for_review' AND review.financial_effect = 'receivable' THEN 1 ELSE 0 END),0) AS pending_receivable,
               coalesce(sum(CASE WHEN review.status = 'ready_for_review' AND review.financial_effect = 'payable' THEN 1 ELSE 0 END),0) AS pending_payable,
               coalesce(sum(CASE WHEN review.status = 'ready_for_review' AND review.financial_effect = 'payable_adjustment' THEN 1 ELSE 0 END),0) AS pending_payable_adjustment,
               coalesce(sum(CASE WHEN review.status = 'ready_for_review' AND review.financial_effect = 'folio_charge' THEN 1 ELSE 0 END),0) AS pending_folio_charge,
               coalesce(sum(CASE WHEN review.status = 'ready_for_review' AND review.financial_effect = 'reference_only' THEN 1 ELSE 0 END),0) AS pending_reference_only,
               coalesce(sum(CASE WHEN review.status = 'ready_for_review'
                   AND (review.financial_effect IS NULL OR review.financial_effect NOT IN
                     ('cash_in','cash_out','settlement','journal_only','receivable','payable',
                      'payable_adjustment','folio_charge','reference_only'))
                   THEN 1 ELSE 0 END),0) AS pending_unclassified_effect,
               coalesce(sum(CASE WHEN review.status = 'ready_for_review'
                   AND review.financial_effect IN ('cash_in','cash_out','settlement')
                   AND review.proposed_account_id IS NULL
                   THEN 1 ELSE 0 END),0) AS pending_cash_without_proposed_account,
               coalesce(sum(CASE WHEN review.status = 'ready_for_review'
                   AND review.financial_effect IN ('cash_in','cash_out','settlement')
                   AND review.proposed_account_id IS NOT NULL AND proposed_account.id IS NULL
                   THEN 1 ELSE 0 END),0) AS pending_cash_proposed_account_missing,
               coalesce(sum(CASE WHEN review.status = 'ready_for_review'
                   AND review.financial_effect IN ('cash_in','cash_out','settlement')
                   AND proposed_account.id IS NOT NULL AND proposed_account.is_active = false
                   THEN 1 ELSE 0 END),0) AS pending_cash_proposed_account_inactive,
               coalesce(sum(CASE WHEN review.status = 'ready_for_review'
                   AND review.financial_effect IN ('cash_in','cash_out','settlement')
                   AND proposed_account.id IS NOT NULL
                   AND (proposed_account.account_type IS NULL OR proposed_account.account_type NOT IN
                     ('cash_drawer','petty_cash','safe','bank','ewallet'))
                   THEN 1 ELSE 0 END),0) AS pending_cash_proposed_account_nonmonetary,
               coalesce(sum(CASE WHEN review.status = 'ready_for_review'
                   AND review.financial_effect = 'journal_only'
                   AND (review.proposed_journal_json IS NULL OR trim(review.proposed_journal_json) = '')
                   THEN 1 ELSE 0 END),0) AS pending_journal_without_proposed_lines,
               coalesce(sum(CASE WHEN review.status = 'accepted' THEN 1 ELSE 0 END),0) AS accepted_events,
               coalesce(sum(CASE WHEN review.status = 'rejected' THEN 1 ELSE 0 END),0) AS rejected_events,
               coalesce(sum(CASE WHEN review.status = 'validation_failed' THEN 1 ELSE 0 END),0) AS validation_failed_events,
               coalesce(sum(CASE WHEN review.status = 'accepted'
                  AND review.financial_effect IN ('cash_in','cash_out','settlement')
                  AND review.accepted_transaction_id IS NULL
                  THEN 1 ELSE 0 END),0) AS missing_cash_target_ids,
               coalesce(sum(CASE WHEN review.status = 'accepted'
                  AND review.financial_effect = 'journal_only'
                  AND review.accepted_journal_entry_id IS NULL
                  THEN 1 ELSE 0 END),0) AS missing_journal_target_ids,
               coalesce(sum(CASE WHEN review.status = 'accepted'
                  AND review.financial_effect = 'receivable'
                  AND review.accepted_receivable_id IS NULL
                  THEN 1 ELSE 0 END),0) AS missing_receivable_target_ids,
               coalesce(sum(CASE WHEN review.status = 'accepted'
                  AND review.financial_effect = 'payable'
                  AND review.accepted_payable_id IS NULL
                  THEN 1 ELSE 0 END),0) AS missing_payable_target_ids,
               coalesce(sum(CASE WHEN review.status = 'accepted'
                  AND review.accepted_transaction_id IS NOT NULL
                  AND cash.id IS NULL THEN 1 ELSE 0 END),0) AS dangling_cash_target_ids,
               coalesce(sum(CASE WHEN review.status = 'accepted'
                  AND review.accepted_journal_entry_id IS NOT NULL
                  AND journal.id IS NULL THEN 1 ELSE 0 END),0) AS dangling_journal_target_ids,
               coalesce(sum(CASE WHEN review.status = 'accepted'
                  AND review.accepted_receivable_id IS NOT NULL
                  AND receivable.id IS NULL THEN 1 ELSE 0 END),0) AS dangling_receivable_target_ids,
               coalesce(sum(CASE WHEN review.status = 'accepted'
                  AND review.accepted_payable_id IS NOT NULL
                  AND payable.id IS NULL THEN 1 ELSE 0 END),0) AS dangling_payable_target_ids,
               coalesce(sum(CASE WHEN review.status = 'accepted'
                  AND review.financial_effect IN ('cash_in','cash_out','settlement')
                  AND cash.id IS NOT NULL AND cash.status <> 'posted'
                  THEN 1 ELSE 0 END),0) AS accepted_cash_target_not_posted,
               coalesce(sum(CASE WHEN review.status = 'accepted'
                  AND review.financial_effect = 'journal_only'
                  AND journal.id IS NOT NULL AND journal.status <> 'posted'
                  THEN 1 ELSE 0 END),0) AS accepted_journal_target_not_posted
        FROM integration_review_items AS review
        LEFT JOIN financial_accounts AS proposed_account ON proposed_account.id = review.proposed_account_id
        LEFT JOIN money_transactions AS cash ON cash.id = review.accepted_transaction_id
        LEFT JOIN journal_entries AS journal ON journal.id = review.accepted_journal_entry_id
        LEFT JOIN receivables AS receivable ON receivable.id = review.accepted_receivable_id
        LEFT JOIN payables AS payable ON payable.id = review.accepted_payable_id
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
    "integration_intake": (
        "staff_waiting_for_review", "pos_waiting_for_review",
        "inventory_waiting_for_review",
        "pending_unclassified_effect",
        "pending_cash_without_proposed_account",
        "pending_cash_proposed_account_missing",
        "pending_cash_proposed_account_inactive",
        "pending_cash_proposed_account_nonmonetary",
        "pending_journal_without_proposed_lines",
        "missing_cash_target_ids", "missing_journal_target_ids",
        "missing_receivable_target_ids", "missing_payable_target_ids",
        "dangling_cash_target_ids", "dangling_journal_target_ids",
        "dangling_receivable_target_ids", "dangling_payable_target_ids",
        "accepted_cash_target_not_posted", "accepted_journal_target_not_posted",
    ),
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
    print("CERTIFICATION: integration_upstream_producer_completeness=NOT_TESTED")
    print("CERTIFICATION: integration_pos_direct_sync=NOT_TESTED")
    print("CERTIFICATION: integration_secondary_journal_and_rounding_proof=NOT_TESTED")
    print("CERTIFICATION: pending_review_counts_are_not_approved_postings=YES")
    print("CERTIFICATION: proposed_account_absence_requires_review_not_auto_assignment=YES")
    print("CERTIFICATION: proposed_account_presence_does_not_prove_payment_method_or_approval=YES")
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
