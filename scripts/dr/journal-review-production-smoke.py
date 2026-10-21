#!/usr/bin/env python3
"""Read-only deployed Journal Review verification. No personal data in logs.

Run on Accounting server with its existing venv and DATABASE_URL. Audit must
never submit review decisions, modify financial rows or export transaction data.
"""
from __future__ import annotations

import os
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from sqlalchemy import create_engine, text


QUERIES = {
    "missing_journal_links": """
        SELECT count(*) FROM money_transactions
        WHERE status = 'posted' AND journal_entry_id IS NULL
    """,
    "reviewed_transaction_count": """
        SELECT count(DISTINCT money_transaction_id) FROM journal_linkage_reviews
    """,
    "review_history_events": """
        SELECT count(*) FROM journal_linkage_reviews
    """,
    "reviewed_unlinked_transaction_count": """
        SELECT count(DISTINCT r.money_transaction_id)
        FROM journal_linkage_reviews r
        JOIN money_transactions t ON t.id = r.money_transaction_id
        WHERE t.status = 'posted' AND t.journal_entry_id IS NULL
    """,
    "orphan_review_references": """
        SELECT count(*) FROM journal_linkage_reviews r
        LEFT JOIN money_transactions t ON t.id = r.money_transaction_id
        WHERE t.id IS NULL
    """,
    "recorded_review_journal_links": """
        SELECT count(*) FROM money_transactions t
        JOIN journal_linkage_reviews r ON r.money_transaction_id = t.id
        WHERE t.journal_entry_id IS NOT NULL
    """,
    "schema_version": "SELECT version_num FROM alembic_version",
}


def database_snapshot(database_url):
    engine = create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as db:
            db.exec_driver_sql("SET TRANSACTION READ ONLY")
            db.exec_driver_sql("SET LOCAL statement_timeout = '30000ms'")
            result = {key: db.execute(text(sql)).scalar_one() for key, sql in QUERIES.items()}
            db.rollback()
        return result
    finally:
        engine.dispose()


def check_snapshot(result):
    """Checks schema/structural integrity, never assumes an old exception count."""
    if result["schema_version"] != "0017_journal_linkage_review":
        raise RuntimeError("Unexpected deployed review schema revision.")
    if result["orphan_review_references"] != 0:
        raise RuntimeError("Orphan evidence review transaction reference.")
    if not (0 <= result["reviewed_transaction_count"] <= result["review_history_events"]):
        raise RuntimeError("Review event history count inconsistent.")
    if not (
        0 <= result["reviewed_unlinked_transaction_count"]
        <= min(result["reviewed_transaction_count"], result["missing_journal_links"])
    ):
        raise RuntimeError("Current unlinked review coverage inconsistent.")
    if result["recorded_review_journal_links"] > 0:
        # This may be legitimate later if a separate approved repair occurs.
        # Flag for human verification, not automatic cleanup.
        print("REVIEW_CERTIFICATION: historical_reviews_with_linked_journals=REVIEW_REQUIRED")
    return True


def unauthenticated_route_status(url):
    req = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=10) as reply:
            return reply.status
    except HTTPError as exc:
        return exc.code


def main():
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise SystemExit("Production PostgreSQL URL required.")
    snapshot = database_snapshot(db_url)
    check_snapshot(snapshot)
    endpoints = {
        "review": "http://127.0.0.1:8000/api/reports/journal-linkage-review",
        "private_csv_export": (
            "http://127.0.0.1:8000/api/reports/"
            "journal-linkage-review/export.csv?queue=unreviewed"
        ),
    }
    protected_statuses = {
        name: unauthenticated_route_status(url) for name, url in endpoints.items()
    }
    for endpoint, status in protected_statuses.items():
        if status not in (401, 403):
            raise RuntimeError(
                "Private Journal Review endpoint not confirmed restricted: "
                + endpoint + ", status=" + str(status)
            )
    print("REVIEW_CERTIFICATION: mode=READ_ONLY")
    print("REVIEW_CERTIFICATION: schema_version=" + snapshot["schema_version"])
    for field in (
        "missing_journal_links",
        "reviewed_transaction_count",
        "reviewed_unlinked_transaction_count",
        "review_history_events",
    ):
        print(f"REVIEW_CERTIFICATION: {field}={snapshot[field]}")
    print(
        "REVIEW_CERTIFICATION: awaiting_first_review="
        + str(snapshot["missing_journal_links"] - snapshot["reviewed_unlinked_transaction_count"])
    )
    print("REVIEW_CERTIFICATION: orphan_review_references=0")
    for endpoint, status in protected_statuses.items():
        print(f"REVIEW_CERTIFICATION: unauthenticated_{endpoint}_GET_http_status={status}")
    print("REVIEW_CERTIFICATION: financial_postings=NOT_MODIFIED")
    print("REVIEW_CERTIFICATION: PASSED")


if __name__ == "__main__":
    sys.exit(main())
