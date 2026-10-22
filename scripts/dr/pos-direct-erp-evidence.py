#!/usr/bin/env python3
"""Read-only POS direct ERP outbox -> Accounting cash/transfer/receivable evidence.

No financial amounts, source identifiers, guest names, tender references,
payloads or credentials are logged or written. Audit evidence is aggregate only.
POS sales, voids, register reconciliation and negative room-charge reversals
have distinct contracts and are deliberately NOT inferred from generic Review.
"""
from __future__ import annotations

import json
import os
from collections import Counter

from sqlalchemy import create_engine, text

POS_EVENTS = (
    "cash_movement.created", "transfer.created", "payment.collected",
    "payment.folio_pending", "payment.refunded", "room_charge.request_created",
    "order.finalized", "order.voided", "session.closed",
)
DIRECT_EVENTS = frozenset(POS_EVENTS[:6])
ACCOUNTING_SOURCE = "dedicated_pos_cloud"
POSTED_KINDS = frozenset({"money", "transfer"})

POS_SQL = """
SELECT event_type, status, payload_json
FROM sync_outbox_events
WHERE event_type IN (
 'cash_movement.created','transfer.created','payment.collected',
 'payment.folio_pending','payment.refunded','room_charge.request_created',
 'order.finalized','order.voided','session.closed'
)
"""
RECEIPT_QUERIES = {
    "money": """
        SELECT external_id, status, is_reversed
        FROM money_transactions
        WHERE external_source='dedicated_pos_cloud'
    """,
    "transfer": """
        SELECT external_id, status, is_reversed
        FROM account_transfers
        WHERE external_source='dedicated_pos_cloud'
    """,
    "receivable": """
        SELECT external_id, status, NULL AS is_reversed
        FROM receivables
        WHERE external_source='dedicated_pos_cloud'
    """,
}
KNOWN_STATUSES = frozenset({
    "synced", "pending", "failed", "blocked", "archived", "resolved",
    "cancelled", "processing", "retry",
})


def _pg_url(value):
    if not value:
        raise ValueError("Protected production database URL is missing.")
    if value.startswith("postgresql://"):
        return "postgresql+psycopg://" + value[len("postgresql://"):]
    if value.startswith("postgresql+psycopg://"):
        return value
    raise ValueError("Only supported PostgreSQL database URLs are permitted.")


def read_pg(url, queries):
    if not isinstance(queries, dict) or not queries:
        raise ValueError("A fixed query mapping is required.")
    engine = create_engine(_pg_url(url), connect_args={"connect_timeout": 5},
                           pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            conn.exec_driver_sql("SET LOCAL statement_timeout='30000ms'")
            try:
                return {name: conn.execute(text(sql)).all() for name, sql in queries.items()}
            finally:
                conn.rollback()
    finally:
        engine.dispose()


def _json(value):
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("POS outbox envelope must be an object.")
    return payload


def expected_target(event_type, payload):
    """One-to-one *direct* target identity, or an explicitly excluded route.

    These identities mirror POS backend/app/services/sync_service.py. Older
    cash movements/transfers retain the original reference-based identity.
    """
    if event_type == "cash_movement.created":
        uuid = payload.get("cash_event_uuid")
        ref = payload.get("reference_no") or uuid
        version = int(payload.get("integration_identity_version") or 1)
        if version >= 2 and uuid:
            return ("money", "cash-movement:" + str(uuid)), None
        return (("money", str(ref)), None) if ref else (None, "unverifiable_identity")
    if event_type == "transfer.created":
        uuid = payload.get("cash_event_uuid")
        ref = payload.get("reference_no") or uuid
        version = int(payload.get("integration_identity_version") or 1)
        if version >= 2 and uuid:
            return ("transfer", "cash-transfer:" + str(uuid)), None
        return (("transfer", str(ref)), None) if ref else (None, "unverifiable_identity")
    if event_type in {"payment.collected", "payment.folio_pending", "payment.refunded"}:
        payment = payload.get("payment") or {}
        if not isinstance(payment, dict):
            return None, "unverifiable_identity"
        tender = str(payment.get("tender_type") or "").strip().lower()
        if not tender or tender == "room_charge":
            return None, "legitimate_no_cash_target"
        if event_type == "payment.refunded":
            payid = payment.get("id")
            return (("money", "refund-payment:" + str(payid)), None) if payid is not None else (None, "unverifiable_identity")
        ref = payment.get("reference_no") or (
            f"{payload.get('order_no')}:{tender}" if payload.get("order_no") else None
        )
        return (("money", str(ref)), None) if ref else (None, "unverifiable_identity")
    if event_type == "room_charge.request_created":
        posting = payload.get("room_charge_posting") or {}
        if not isinstance(posting, dict) or not posting:
            return None, "legitimate_no_cash_target"
        try:
            negative = float(posting.get("charge_amount") or 0) < 0
        except (TypeError, ValueError):
            return None, "unverifiable_identity"
        if negative:
            return None, "distinct_negative_room_charge_reversal"
        ident = posting.get("posting_uuid") or posting.get("id")
        return (("receivable", "room-charge:" + str(ident)), None) if ident is not None else (None, "unverifiable_identity")
    if event_type in {"order.finalized", "order.voided", "session.closed"}:
        return None, "distinct_sale_void_or_register_reconciliation"
    raise ValueError("Unknown POS accounting event type.")


def compare(pos_rows, target_rows):
    """Only permitted classifications, never source or receiver identifiers."""
    stats = Counter()
    targets = {}
    for kind, rows in target_rows.items():
        if kind not in RECEIPT_QUERIES:
            raise ValueError("Unrecognized direct Accounting target table.")
        for ident, status, reversed_flag in rows:
            stats["accounting_" + kind + "_rows"] += 1
            if ident is None or str(ident) == "":
                stats["accounting_target_missing_external_id"] += 1
                continue
            key = (kind, str(ident))
            if key in targets:
                stats["duplicate_accounting_external_identity"] += 1
            else:
                targets[key] = (str(status or "").lower(), bool(reversed_flag))
    expected = set()
    for event, status, raw_payload in pos_rows:
        if event not in POS_EVENTS:
            # Callers should query the scoped set. Unexpected types fail closed.
            raise ValueError("Unknown event type in scoped POS Accounting scan.")
        stats["pos_scoped_events"] += 1
        stats["type_" + event.replace(".", "_")] += 1
        s = str(status or "").strip().lower()
        stats["sender_status_" + (s if s in KNOWN_STATUSES else "other")] += 1
        # Don't parse payloads for sale/void/reconciliation: they have separate
        # receivers, and payloads can contain private customer/item details.
        if event not in DIRECT_EVENTS:
            stats["not_compared_distinct_erp_endpoint"] += 1
            continue
        try:
            identity, exclusion = expected_target(event, _json(raw_payload))
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Malformed scoped POS event; audit must not silently skip it.") from None
        if exclusion:
            stats["excluded_" + exclusion] += 1
            continue
        stats["direct_target_expected"] += 1
        if identity in expected:
            stats["duplicate_pos_expected_target_identity"] += 1
        expected.add(identity)
        existing = targets.get(identity)
        if existing:
            stats["direct_target_present"] += 1
            if s != "synced":
                stats["receiver_exists_sender_not_synced"] += 1
            if identity[0] in POSTED_KINDS:
                if existing[0] != "posted":
                    stats["direct_cash_or_transfer_not_posted"] += 1
                if existing[1]:
                    stats["direct_cash_or_transfer_reversed"] += 1
        elif s == "synced":
            stats["synced_source_without_direct_target"] += 1
        else:
            stats["unsynced_source_without_direct_target"] += 1
    stats["accounting_direct_targets_not_referenced_by_scanned_source"] = sum(
        key not in expected for key in targets
    )
    # Explicit zeros are essential when POS has not gone live.
    baseline = (
        "pos_scoped_events", "direct_target_expected", "direct_target_present",
        "synced_source_without_direct_target", "unsynced_source_without_direct_target",
        "receiver_exists_sender_not_synced", "duplicate_pos_expected_target_identity",
        "duplicate_accounting_external_identity",
        "accounting_direct_targets_not_referenced_by_scanned_source",
        "direct_cash_or_transfer_not_posted", "direct_cash_or_transfer_reversed",
        "not_compared_distinct_erp_endpoint",
    )
    return {key: int(stats.get(key, 0)) for key in sorted(set(stats) | set(baseline))}


def render(report):
    print("POS DIRECT PARITY: SQL=READ_ONLY; OUTPUT=COUNTS_ONLY")
    for key, value in sorted(report.items()):
        if not isinstance(key, str) or type(value) is not int or value < 0:
            raise ValueError("Unexpected report contents.")
        print(f"POS DIRECT PARITY: {key}={value}")
    print("POS DIRECT PARITY: CROSS_DATABASE_ATOMIC_SNAPSHOT=NO")
    print("POS DIRECT PARITY: POS_SYNCED_DOES_NOT_PROVE_GENERAL_LEDGER_JOURNAL=YES")
    print("POS DIRECT PARITY: UNMATCHED_SOURCE_IS_REVIEW_NOT_PROOF_OF_LOST_DELIVERY=YES")
    print("POS DIRECT PARITY: SALES_VOIDS_REGISTER_CLOSES_AND_NEGATIVE_ROOM_CHARGES=NOT_COMPARABLE")
    print("POS DIRECT PARITY: PAYMENT_BANK_RECONCILIATION=NOT_TESTED")
    print("POS DIRECT PARITY: ACCOUNTING_REVIEW_INBOX_IS_NOT_GENERIC_POS_RECEIVER=YES")


def main():
    try:
        pos = read_pg(os.environ.get("POS_AUDIT_DATABASE_URL"), {"events": POS_SQL})
        accounting = read_pg(os.environ.get("ACCOUNTING_AUDIT_DATABASE_URL"),
                             RECEIPT_QUERIES)
        render(compare(pos["events"], accounting))
        print("POS DIRECT PARITY: EXECUTION PASS")
        return 0
    except Exception as exc:
        # Never echo an exception's message: it may contain credentials,
        # private outbox payloads or customer identifiers.
        print("POS DIRECT PARITY: NOT_CERTIFIED (" + type(exc).__name__ + ")")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
