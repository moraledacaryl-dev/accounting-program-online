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
REVIEW_SQL = """
    SELECT source_event_id, status FROM integration_review_items
    WHERE source_app='pos'
"""
REGISTER_RECON_SQL = """
    SELECT financial_account_id, reconciliation_date, shift_name, status
    FROM cash_reconciliations
    WHERE counted_by='Dedicated POS'
"""
ROUTING_SQL = """
    SELECT value_json FROM system_settings
    WHERE key='accounting_sync'
"""
KIND_FOR_TARGET = {
    "money": "cashflow_transaction",
    "transfer": "cash_transfer",
    "receivable": "room_charge",
}
REVIEW_STATES = frozenset({
    "ready_for_review", "accepted", "rejected", "validation_failed",
    "awaiting_approval", "pending",
})

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


def configured_routes(rows):
    """Read only explicit POS endpoint classification, never a path or secret."""
    if not rows:
        config = {}
    elif len(rows) == 1 and isinstance(rows[0][0], str):
        try:
            config = json.loads(rows[0][0])
        except (ValueError, TypeError):
            raise ValueError("POS sync routing configuration is malformed.") from None
        if not isinstance(config, dict):
            raise ValueError("POS sync configuration must be an object.")
    else:
        raise ValueError("POS sync route configuration is ambiguous.")

    fields = {
        "cashflow": "current_erp_cashflow_path",
        "transfer": "current_erp_transfers_path",
        "room_charge": "current_erp_pos_room_charge_path",
    }
    routes = {}
    for name, key in fields.items():
        raw = config.get(key)
        if raw is not None and not isinstance(raw, str):
            raise ValueError("POS sync route field has an invalid type.")
        if not raw:
            # The POS application defaults to /cashflow/transactions,
            # /transfers or /integrations/pos/room-charge as appropriate.
            routes[name] = "default_direct"
        else:
            routes[name] = ("review_inbox" if "/integrations/pos-review/" in raw
                            else "custom_direct_or_other")
    return routes


def compare(pos_rows, target_rows, *, review_rows=(), routing=None):
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
    review_items = {}
    for source_event_id, status in review_rows:
        stats["pos_review_items"] += 1
        if not isinstance(source_event_id, str) or not source_event_id:
            stats["pos_review_missing_source_id"] += 1
            continue
        status_name = str(status or "").strip().lower()
        safe_status = status_name if status_name in REVIEW_STATES else "other"
        stats["pos_review_status_" + safe_status] += 1
        if source_event_id in review_items:
            stats["duplicate_pos_review_event_identity"] += 1
        else:
            review_items[source_event_id] = status_name

    expected = set()
    examined_review = set()
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
        review_id = "pos:" + KIND_FOR_TARGET[identity[0]] + ":" + identity[1]
        review_status = review_items.get(review_id)
        if review_status is not None:
            examined_review.add(review_id)
            stats["matching_pos_review_intake"] += 1
            if review_status == "accepted":
                stats["matching_pos_review_accepted"] += 1
            elif review_status in {"ready_for_review", "awaiting_approval", "pending"}:
                stats["matching_pos_review_awaiting_acceptance"] += 1
            else:
                stats["matching_pos_review_other_status"] += 1
        if existing:
            stats["direct_target_present"] += 1
            if review_status is not None:
                stats["direct_target_and_review_both_present"] += 1
            if s != "synced":
                stats["receiver_exists_sender_not_synced"] += 1
            if identity[0] in POSTED_KINDS:
                if existing[0] != "posted":
                    stats["direct_cash_or_transfer_not_posted"] += 1
                if existing[1]:
                    stats["direct_cash_or_transfer_reversed"] += 1
        elif s == "synced":
            stats["synced_source_without_direct_target"] += 1
            if review_status is None:
                stats["synced_source_without_direct_or_review_evidence"] += 1
            else:
                stats["synced_source_missing_direct_but_review_received"] += 1
        else:
            stats["unsynced_source_without_direct_target"] += 1
            if review_status is not None:
                stats["unsynced_source_with_review_receipt"] += 1
    stats["accounting_direct_targets_not_referenced_by_scanned_source"] = sum(
        key not in expected for key in targets
    )
    # This is a limited comparison: sale/void/register close have other
    # source identity conventions. Do not call unmatched review items lost.
    stats["pos_review_items_not_assessed_under_direct_target_contract"] = (
        len(review_items) - len(examined_review)
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
        "pos_review_items", "matching_pos_review_intake",
        "matching_pos_review_accepted", "matching_pos_review_awaiting_acceptance",
        "matching_pos_review_other_status", "duplicate_pos_review_event_identity",
        "synced_source_without_direct_or_review_evidence",
        "synced_source_missing_direct_but_review_received",
        "unsynced_source_with_review_receipt",
        "direct_target_and_review_both_present",
        "pos_review_items_not_assessed_under_direct_target_contract",
    )
    result = {key: int(stats.get(key, 0)) for key in sorted(set(stats) | set(baseline))}
    if routing is not None:
        if set(routing) != {"cashflow", "transfer", "room_charge"}:
            raise ValueError("POS routing scope is incomplete.")
        safe_routes = {"default_direct", "review_inbox", "custom_direct_or_other"}
        if any(v not in safe_routes for v in routing.values()):
            raise ValueError("POS routing classification is invalid.")
        # Route classes are rendered using a fixed allowlist; never actual
        # configured endpoint URLs, auth headers, integration secrets.
        result.update({"route_" + key + "_" + routing[key]: 1 for key in sorted(routing)})
    return result


def compare_sessions(pos_rows, register_rows, review_rows=(), *, routing_rows=()):
    """Audit POS register closes against their separate reconciliations.

    A counted reconciliation receipt is NOT a bank deposit or verified
    shortage settlement. Numeric account ID + date + shift is the exact
    direct Accounting cash_reconciliations unique business key.
    """
    direct = {}
    stats = Counter()
    for account_id, date, shift, status in register_rows:
        stats["register_accounting_direct_records"] += 1
        key = (str(account_id), str(date or ""), str(shift or ""))
        if key in direct:
            stats["register_duplicate_direct_key"] += 1
        else:
            direct[key] = str(status or "").lower()
    review = {}
    for event_id, status in review_rows:
        if not isinstance(event_id, str) or not event_id.startswith(
            "pos:register_reconciliation:"
        ):
            continue
        if event_id in review:
            stats["register_duplicate_review_key"] += 1
        review[event_id] = str(status or "").lower()

    scoped = set()
    matched_review = set()
    for event_type, status, raw_payload in pos_rows:
        if event_type != "session.closed":
            continue
        stats["register_pos_closed_events"] += 1
        is_synced = str(status or "").strip().lower() == "synced"
        if is_synced:
            stats["register_pos_synced_events"] += 1
        else:
            stats["register_pos_not_synced_events"] += 1
        try:
            payload = _json(raw_payload)
        except (TypeError, ValueError):
            raise ValueError("Invalid POS register close envelope.") from None
        acct = payload.get("register_accounting_financial_account_id")
        shift = payload.get("session_code")
        date = payload.get("business_date")
        if type(acct) is not int or acct <= 0 or not isinstance(shift, str) or not shift.strip() or not isinstance(date, str) or not date.strip():
            stats["register_unverifiable_account_date_or_shift"] += 1
            continue
        key = (str(acct), date.strip(), shift.strip())
        if key in scoped:
            stats["register_duplicate_source_business_key"] += 1
        scoped.add(key)
        review_id = "pos:register_reconciliation:" + shift
        found_direct = key in direct
        found_review = review_id in review
        if found_direct:
            stats["register_direct_receipt_matched"] += 1
            direct_status = direct[key]
            if direct_status != "counted":
                stats["register_direct_receipt_other_status"] += 1
        if found_review:
            stats["register_review_receipt_matched"] += 1
            matched_review.add(review_id)
            if review[review_id] in {"ready_for_review", "awaiting_approval", "pending"}:
                stats["register_review_awaiting_acceptance"] += 1
            elif review[review_id] == "accepted":
                stats["register_review_accepted"] += 1
            else:
                stats["register_review_other_status"] += 1
        if found_direct and found_review:
            stats["register_direct_and_review_both_present"] += 1
        if not found_direct and not found_review:
            stats["register_without_direct_or_review_receipt"] += 1
            if is_synced:
                stats["register_synced_without_either_receipt"] += 1
    stats["register_accounting_direct_not_in_scanned_source"] = sum(k not in scoped for k in direct)
    stats["register_review_not_in_scanned_source"] = len(set(review) - matched_review)

    if routing_rows:
        if len(routing_rows) != 1 or not isinstance(routing_rows[0][0], str):
            raise ValueError("Ambiguous POS reconciliation routing config.")
        try:
            routing = json.loads(routing_rows[0][0])
        except (TypeError, ValueError):
            raise ValueError("Invalid POS reconciliation routing config.") from None
        if not isinstance(routing, dict):
            raise ValueError("Invalid POS reconciliation routing config.")
        path = routing.get("current_erp_reconciliation_path")
        if path is not None and not isinstance(path, str):
            raise ValueError("Invalid POS reconciliation route type.")
        route_class = ("default_direct" if not path else
                       "review_inbox" if "/integrations/pos-review/" in path else
                       "custom_direct_or_other")
    else:
        route_class = "default_direct"
    stats["register_route_" + route_class] = 1
    baseline = (
        "register_pos_closed_events", "register_pos_synced_events",
        "register_direct_receipt_matched", "register_review_receipt_matched",
        "register_review_awaiting_acceptance", "register_review_accepted",
        "register_without_direct_or_review_receipt",
        "register_synced_without_either_receipt",
        "register_unverifiable_account_date_or_shift",
        "register_direct_and_review_both_present",
        "register_duplicate_source_business_key", "register_duplicate_direct_key",
        "register_accounting_direct_not_in_scanned_source",
        "register_review_not_in_scanned_source",
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
    print("POS DIRECT PARITY: REVIEW_RECEIPT_DOES_NOT_MEAN_ACCOUNTING_POSTED=YES")
    print("POS DIRECT PARITY: PAYMENT_BANK_RECONCILIATION=NOT_TESTED")
    print("POS DIRECT PARITY: REGISTER_COUNT_RECEIPT_IS_NOT_APPROVED_CASH_RECONCILIATION=YES")
    print("POS DIRECT PARITY: ACCOUNTING_REVIEW_INBOX_IS_NOT_GENERIC_POS_RECEIVER=YES")


def main():
    try:
        pos = read_pg(os.environ.get("POS_AUDIT_DATABASE_URL"),
                      {"events": POS_SQL, "routing": ROUTING_SQL})
        accounting = read_pg(os.environ.get("ACCOUNTING_AUDIT_DATABASE_URL"),
                             {**RECEIPT_QUERIES, "review": REVIEW_SQL,
                              "register": REGISTER_RECON_SQL})
        reviews = accounting.pop("review")
        registers = accounting.pop("register")
        result = compare(pos["events"], accounting, review_rows=reviews,
                         routing=configured_routes(pos["routing"]))
        result.update(compare_sessions(pos["events"], registers, reviews,
                                       routing_rows=pos["routing"]))
        render(result)
        print("POS DIRECT PARITY: EXECUTION PASS")
        return 0
    except Exception as exc:
        # Never echo an exception's message: it may contain credentials,
        # private outbox payloads or customer identifiers.
        print("POS DIRECT PARITY: NOT_CERTIFIED (" + type(exc).__name__ + ")")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
