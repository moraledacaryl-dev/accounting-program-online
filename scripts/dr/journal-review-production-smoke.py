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
    code = unauthenticated_route_status(
        "http://127.0.0.1:8000/api/reports/journal-linkage-review"
    )
    if code not in (401, 403):
        raise RuntimeError("Review endpoint not confirmed restricted; status=" + str(code))
    print("REVIEW_CERTIFICATION: mode=READ_ONLY")
    print("REVIEW_CERTIFICATION: schema_version=" + snapshot["schema_version"])
    for field in ("missing_journal_links", "reviewed_transaction_count", "review_history_events"):
        print(f"REVIEW_CERTIFICATION: {field}={snapshot[field]}")
    print("REVIEW_CERTIFICATION: orphan_review_references=0")
    print(f"REVIEW_CERTIFICATION: unauthenticated_GET_http_status={code}")
    print("REVIEW_CERTIFICATION: financial_postings=NOT_MODIFIED")
    print("REVIEW_CERTIFICATION: PASSED")


if __name__ == "__main__":
    sys.exit(main())
