#!/usr/bin/env python3
"""Read-only Staff repayment versus Accounting source-identity reconciliation.

No matching-by-amount automatically proves the same financial transaction.
Run from backend/ with DATABASE_URL configured for the actual Accounting DB.
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
import sqlite3

from sqlalchemy import text


STAFF_SOURCE = "hidden_oasis_staff_payroll"


def cents(value: object) -> int:
    amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if not amount.is_finite():
        raise ValueError("Nonfinite monetary value in reconciliation input")
    return int(amount * 100)


def _staff_rows(db: sqlite3.Connection) -> list[sqlite3.Row]:
    db.row_factory = sqlite3.Row
    required = {
        "cash_advance_repayments": {
            "id", "cash_advance_id", "repayment_date", "amount", "source",
            "active", "payment_method", "method", "reference",
        },
        "integration_outbox": {
            "destination", "external_source", "external_id", "event_type",
        },
    }
    for table, columns in required.items():
        present = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
        if missing := columns - present:
            raise RuntimeError(f"Staff table {table} missing columns: {sorted(missing)}")
    return db.execute("""
        SELECT r.id, r.cash_advance_id, r.repayment_date, r.amount,
               COALESCE(NULLIF(TRIM(r.payment_method), ''),
                        NULLIF(TRIM(r.method), ''), '') AS method,
               CASE WHEN NULLIF(TRIM(r.reference), '') IS NULL
                    THEN 0 ELSE 1 END AS has_reference
        FROM cash_advance_repayments r
        WHERE LOWER(TRIM(COALESCE(r.source, ''))) = 'manual'
          AND COALESCE(r.active, 1) = 1
          AND NOT EXISTS (
            SELECT 1 FROM integration_outbox o
            WHERE o.destination = 'accounting'
              AND o.external_source = 'hidden_oasis_staff_payroll'
              AND o.event_type = 'cash_advance.repaid'
              AND o.external_id = 'cash-advance-repayment:' || r.id
          )
        ORDER BY r.id
    """).fetchall()


def reconcile(staff_db: sqlite3.Connection, accounting_db, *, sample_limit: int = 100) -> dict:
    """Returns an evidence worklist; neither database is modified."""
    if sample_limit < 0:
        raise ValueError("sample_limit must be >= 0")
    cases = _staff_rows(staff_db)
    output = []
    reused_candidates = Counter()
    total_cents = 0

    for staff in cases:
        key = f"cash-advance-repayment:{staff['id']}"
        amount_cents = cents(staff["amount"])
        total_cents += amount_cents
        params = {"key": key}
        review_rows = accounting_db.execute(text("""
            SELECT id, status, financial_effect, accepted_transaction_id
            FROM integration_review_items
            WHERE source_app = 'staff' AND source_event_id = :key
            ORDER BY id
        """), params).mappings().all()
        receipt_rows = accounting_db.execute(text("""
            SELECT id, status FROM integration_receipts
            WHERE external_source = 'hidden_oasis_staff_payroll'
              AND external_id = :key AND event_type = 'cash_advance.repaid'
            ORDER BY id
        """), params).mappings().all()
        linked_money = accounting_db.execute(text("""
            SELECT id, status, is_reversed FROM money_transactions
            WHERE external_source IN ('staff', 'hidden_oasis_staff_payroll')
              AND external_id = :key
            ORDER BY id
        """), params).mappings().all()
        # Date-and-amount are an investigative lead, NOT a safe identity key.
        money_candidates = accounting_db.execute(text("""
            SELECT id, status, is_reversed, amount FROM money_transactions
            WHERE direction = 'in' AND transaction_date = :day
              AND amount >= :lower_bound AND amount < :upper_bound
            ORDER BY id
        """), {
            "day": str(staff["repayment_date"]),
            "lower_bound": float(Decimal(amount_cents) / 100 - Decimal("0.005")),
            "upper_bound": float(Decimal(amount_cents) / 100 + Decimal("0.005")),
        }).mappings().all()
        # Recheck exact centavo identity because database storage is REAL.
        candidates = [
            {"id": int(row["id"]), "status": str(row["status"] or ""),
             "is_reversed": bool(row["is_reversed"])}
            for row in money_candidates if cents(row["amount"]) == amount_cents
        ]
        for candidate in candidates:
            reused_candidates[candidate["id"]] += 1
        output.append({
            "repayment_id": int(staff["id"]),
            "cash_advance_id": int(staff["cash_advance_id"]),
            "repayment_date": str(staff["repayment_date"]),
            "amount_php": amount_cents / 100,
            "payment_method": str(staff["method"]),
            "has_receipt_reference": bool(staff["has_reference"]),
            "expected_source_event_id": key,
            "exact_review_items": [
                {"id": int(row["id"]), "status": str(row["status"]),
                 "financial_effect": str(row["financial_effect"]),
                 "accepted_transaction_id": row["accepted_transaction_id"]}
                for row in review_rows
            ],
            "exact_legacy_receipts": [
                {"id": int(row["id"]), "status": str(row["status"])}
                for row in receipt_rows
            ],
            "exact_money_transactions": [
                {"id": int(row["id"]), "status": str(row["status"]),
                 "is_reversed": bool(row["is_reversed"])} for row in linked_money
            ],
            "same_date_amount_cash_candidates": candidates,
            "source_identity_found": bool(review_rows or receipt_rows or linked_money),
            "needs_manual_reconciliation": True,
        })

    return {
        "read_only": True,
        "scope": "active manual Staff repayments missing a Staff Accounting outbox event",
        "accounting_identity_matches_do_not_prove_final_posting": True,
        "repayment_count": len(output),
        "amount_php": total_cents / 100,
        "exact_source_identity_count": sum(x["source_identity_found"] for x in output),
        "without_exact_source_identity_count": sum(not x["source_identity_found"] for x in output),
        "shared_amount_date_candidate_ids": sorted(
            key for key, count in reused_candidates.items() if count > 1
        ),
        "worklist_sample": output[:sample_limit],
        "sample_truncated": len(output) > sample_limit,
        "instruction": (
            "Do not auto-replay, post or reconcile by date and amount. "
            "Independently check the receiving account, source references, "
            "employee cash-advance ledger, Accounting review status and bank/cash "
            "statements. Exact Accounting intake still does not prove posting."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staff-db", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    if not args.staff_db.is_absolute() or not args.staff_db.is_file():
        parser.error("--staff-db must be an existing absolute file")
    if args.limit < 0:
        parser.error("--limit must be >= 0")
    from app.db.database import engine  # load configured Accounting DB
    if engine.dialect.name not in {"postgresql", "sqlite"}:
        raise RuntimeError("Unsupported Accounting DB dialect for read-only audit")
    with sqlite3.connect(args.staff_db.resolve().as_uri() + "?mode=ro", uri=True) as staff:
        staff.execute("PRAGMA query_only=ON")
        with engine.connect() as accounting:
            if accounting.dialect.name == "postgresql":
                accounting.exec_driver_sql("SET TRANSACTION READ ONLY")
            else:
                accounting.exec_driver_sql("PRAGMA query_only=ON")
            result = reconcile(staff, accounting, sample_limit=args.limit)
            accounting.rollback()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
