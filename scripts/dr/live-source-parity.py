#!/usr/bin/env python3
"""Privacy-minimized live source-to-Accounting intake parity probe.

Read-only PostgreSQL/SQLite queries. Only aggregates go to stdout.
No matching ID, payload, bank/payroll value, credentials, or path is logged.
Three separate DB snapshots are NOT an atomic cross-application snapshot.
"""
from __future__ import annotations

import json
import os
import sqlite3
from collections import Counter

from sqlalchemy import create_engine, text

STAFF_FINANCIAL_TYPES = frozenset({
    "payroll.run.approved", "payroll.run.paid", "payroll.13th_month.paid",
    "cash_advance.released", "cash_advance.repaid",
})
SOURCE_NAMES = ("inventory", "staff")
FINAL_STAFF_STATUS = frozenset({"completed", "sent"})
FINAL_INVENTORY_STATUS = frozenset({"completed"})


def _pg_url(value):
    if not value:
        raise ValueError("Missing protected PostgreSQL connection configuration.")
    if value.startswith("postgresql://"):
        return "postgresql+psycopg://" + value[len("postgresql://"):]
    if value.startswith("postgresql+psycopg://"):
        return value
    raise ValueError("Expected a supported PostgreSQL URL.")


def read_postgres(url, query):
    engine = create_engine(_pg_url(url), connect_args={"connect_timeout": 5},
                           pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            connection.exec_driver_sql("SET LOCAL statement_timeout = '30000ms'")
            try:
                return connection.execute(text(query)).all()
            finally:
                connection.rollback()
    finally:
        engine.dispose()


INVENTORY_SQL = """
    SELECT id, status FROM integration_events
    WHERE direction='outbound' AND destination_system='accounting'
"""
ACCOUNTING_SQL = """
    SELECT source_app, source_event_id, source_revision, status
    FROM integration_review_items
    WHERE source_app IN ('inventory','staff')
"""

# Count source-domain activity without exposing purchase/supplier/item/stock
# identities, transaction values or private payloads. Some historical records
# legitimately predate integrations, so this is descriptive, not an assertion
# that every domain row should have an Accounting event.
INVENTORY_DOMAIN_SQL = """
    SELECT
      (SELECT count(*) FROM purchase_orders) AS purchase_orders,
      (SELECT count(*) FROM purchase_orders WHERE approved_at IS NOT NULL)
          AS approved_purchase_orders,
      (SELECT count(*) FROM goods_receipts) AS goods_receipts,
      (SELECT count(*) FROM purchase_returns) AS purchase_returns,
      (SELECT count(*) FROM stock_documents WHERE status='posted')
          AS posted_stock_documents
"""



def read_staff_sqlite(db_path):
    if not db_path or not os.path.isabs(db_path) or not os.path.isfile(db_path):
        raise ValueError("Staff production database path is not available.")
    # Immutable=1 is NOT safe for a live WAL database: use standard mode=ro.
    from pathlib import Path
    with sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        event_types = tuple(sorted(STAFF_FINANCIAL_TYPES))
        placeholders = ",".join("?" for _ in event_types)
        return db.execute(
            "SELECT external_id, status, event_type, payload_json "
            "FROM integration_outbox "
            "WHERE destination='accounting' "
            "AND external_source='hidden_oasis_staff_payroll' "
            f"AND event_type IN ({placeholders})",
            event_types,
        ).fetchall()


def _staff_revision(payload_json, ext_id):
    payload = json.loads(payload_json)
    if not isinstance(payload, dict) or str(payload.get("external_id") or "").strip() != ext_id:
        raise ValueError("Inconsistent private Staff Accounting event envelope.")
    body = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
    revision = int(payload.get("source_revision") or body.get("source_revision") or 1)
    if revision < 1:
        raise ValueError("Invalid Staff source revision.")
    return revision


def compare_live_rows(accounting_rows, inventory_rows, staff_rows):
    """Use source IDs in memory only; return privacy-safe aggregated counts."""
    received = {}
    # Zero source events are a meaningful diagnostic, especially when the
    # Accounting intake also has zero retained Inventory events. Print zeros
    # explicitly instead of hiding missing categories in a sparse Counter.
    baseline = (
        "source_financial_events", "source_marked_delivered",
        "source_not_marked_delivered", "accounting_received",
        "present_in_accounting", "delivered_but_receipt_not_found",
        "pending_and_receipt_not_found", "receiver_id_absent_from_source_scan",
        "duplicate_source_identity", "duplicate_receiver_identity",
        "receipt_exists_but_sender_unacknowledged",
    )
    counts = {name: Counter({field: 0 for field in baseline}) for name in SOURCE_NAMES}
    for app, identifier, revision, status in accounting_rows:
        if app not in SOURCE_NAMES:
            continue
        key = (app, str(identifier).strip(), int(revision))
        if not key[1] or key[2] < 1:
            raise ValueError("Invalid retained Accounting review identity.")
        if key in received:
            counts[app]["duplicate_receiver_identity"] += 1
        else:
            received[key] = str(status or "").lower()
            counts[app]["accounting_received"] += 1
    for name, source_rows in (
        ("inventory", ((identifier, 1, status) for identifier, status in inventory_rows)),
        ("staff", ((_id, _staff_revision(payload, str(_id).strip()), status)
                   for _id, status, kind, payload in staff_rows
                   if kind in STAFF_FINANCIAL_TYPES)),
    ):
        source_ids = set()
        final_states = FINAL_STAFF_STATUS if name == "staff" else FINAL_INVENTORY_STATUS
        for identifier, revision, status in source_rows:
            if not isinstance(identifier, str) or not identifier.strip():
                raise ValueError("Empty upstream financial event ID.")
            if type(revision) is not int or revision < 1:
                raise ValueError("Invalid upstream financial source revision.")
            key = (name, identifier.strip(), revision)
            counts[name]["source_financial_events"] += 1
            if key in source_ids:
                counts[name]["duplicate_source_identity"] += 1
                continue
            source_ids.add(key)
            finished = str(status or "").lower() in final_states
            if finished:
                counts[name]["source_marked_delivered"] += 1
            else:
                counts[name]["source_not_marked_delivered"] += 1
                # Subdivide purely diagnostic states without leaking contents.
                state = str(status or "").strip().lower().replace(" ", "_")
                counts[name]["source_status_" + state if state in (
                    "pending", "processing", "retry", "failed", "dead_letter"
                ) else "source_status_other"] += 1
            if key in received:
                counts[name]["present_in_accounting"] += 1
                if not finished:
                    counts[name]["receipt_exists_but_sender_unacknowledged"] += 1
            elif finished:
                counts[name]["delivered_but_receipt_not_found"] += 1
            else:
                counts[name]["pending_and_receipt_not_found"] += 1
        counts[name]["receiver_id_absent_from_source_scan"] = sum(
            1 for key in received if key[0] == name and key not in source_ids
        )
    return {name: dict(sorted(counter.items())) for name, counter in counts.items()}


def render(report, *, inventory_domain=None):
    print("LIVE SOURCE PARITY: MODE=READ_ONLY; IDENTITIES=REDACTED")
    print("LIVE SOURCE PARITY: SOURCE_DATABASES=SEQUENTIALLY_READ")
    for name, values in report.items():
        for key, value in values.items():
            print(f"LIVE SOURCE PARITY: {name}.{key}={value}")
    if inventory_domain is not None:
        if not isinstance(inventory_domain, dict):
            raise ValueError("Inventory activity summary must be an object.")
        expected = {
            "purchase_orders", "approved_purchase_orders",
            "goods_receipts", "purchase_returns", "posted_stock_documents",
        }
        if set(inventory_domain) != expected or any(
            type(value) is not int or value < 0 for value in inventory_domain.values()
        ):
            raise ValueError("Unexpected Inventory source activity schema.")
        for key, value in sorted(inventory_domain.items()):
            print(f"LIVE SOURCE DOMAIN: inventory.{key}={value}")
        print("LIVE SOURCE DOMAIN: HISTORICAL_ROWS_MAY_PRECEDE_INTEGRATION=YES")
        print("LIVE SOURCE DOMAIN: ACTIVITY_AND_OUTBOX_SNAPSHOTS_ATOMIC=NO")
    print("LIVE SOURCE PARITY: CROSS_DATABASE_ATOMIC_SNAPSHOT=NO")
    print("LIVE SOURCE PARITY: DIFFERENCES_REQUIRE_HUMAN_REVIEW=YES")
    print("LIVE SOURCE PARITY: SOURCE_COMPLETED_MEANS_ACCOUNTING_ACCEPTED=NO")
    print("LIVE SOURCE PARITY: BANK_SETTLEMENT_AND_JOURNAL_POSTING=NOT_TESTED")
    print("LIVE SOURCE PARITY: RESTORE_REHEARSAL=NOT_REQUESTED")


def main():
    try:
        accounting_rows = read_postgres(os.environ.get("ACCOUNTING_AUDIT_DATABASE_URL"),
                                        ACCOUNTING_SQL)
        inventory_rows = read_postgres(os.environ.get("INVENTORY_AUDIT_DATABASE_URL"),
                                       INVENTORY_SQL)
        staff_rows = read_staff_sqlite(os.environ.get("STAFF_PAYROLL_DB_PATH"))
        inventory_domain_rows = read_postgres(
            os.environ.get("INVENTORY_AUDIT_DATABASE_URL"),
            INVENTORY_DOMAIN_SQL,
        )
        if len(inventory_domain_rows) != 1 or len(inventory_domain_rows[0]) != 5:
            raise ValueError("Inventory activity summary has an invalid shape.")
        inventory_domain = dict(zip(
            ("purchase_orders", "approved_purchase_orders", "goods_receipts",
             "purchase_returns", "posted_stock_documents"),
            (int(v) for v in inventory_domain_rows[0]),
        ))
        render(compare_live_rows(accounting_rows, inventory_rows, staff_rows),
               inventory_domain=inventory_domain)
        print("LIVE SOURCE PARITY: EXECUTION PASS")
        return 0
    except Exception as exc:
        # Never echo SQLAlchemy exceptions: they may include DB credentials or
        # private source event IDs. Fail closed and emit only exception category.
        print(f"LIVE SOURCE PARITY: NOT_CERTIFIED ({type(exc).__name__})")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
