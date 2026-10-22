"""Read-only, aggregate POS finalized-sale and void receiver parity.

Sale UUID and void order-number are different destination contracts. Never
equate a sale receipt to a posted GL journal, revenue, COGS or bank settlement.
"""
from __future__ import annotations

import json
from collections import Counter

SALES_SQL = """
SELECT sale.external_id, sale.order_no, sale.status,
       sale.income_record_id, sale.cogs_record_id,
       (SELECT count(*) FROM sale_void_events AS void_event
        WHERE void_event.sale_order_id = sale.id) AS void_events
FROM sale_orders AS sale WHERE sale.external_source='dedicated_pos_cloud'
"""


def compare_sales(source_rows, destination_rows):
    stats = Counter()
    by_uuid, by_number = {}, {}
    for uuid, order_no, status, income_record, cogs_record, void_count in destination_rows:
        stats["accounting_pos_sales"] += 1
        if uuid:
            if str(uuid) in by_uuid:
                stats["duplicate_accounting_sale_uuid"] += 1
            else:
                by_uuid[str(uuid)] = (str(order_no or ""), status, income_record, cogs_record)
        else:
            stats["accounting_sale_missing_uuid"] += 1
        if order_no:
            if str(order_no) in by_number:
                stats["duplicate_accounting_sale_order_no"] += 1
            else:
                by_number[str(order_no)] = (status, int(void_count or 0))
        else:
            stats["accounting_sale_missing_order_no"] += 1

    seen_sales, seen_voids = set(), set()
    for event_type, status, raw_payload in source_rows:
        if event_type not in {"order.finalized", "order.voided"}:
            continue
        try:
            payload = json.loads(raw_payload)
        except (ValueError, TypeError):
            raise ValueError("Scoped POS sale or void payload is not valid JSON.") from None
        if not isinstance(payload, dict):
            raise ValueError("Scoped POS sale/void envelope must be an object.")
        synced = str(status or "").lower() == "synced"
        if event_type == "order.finalized":
            stats["source_finalized"] += 1
            uuid, order_no = payload.get("order_uuid"), payload.get("order_no")
            if not isinstance(uuid, str) or not uuid.strip():
                stats["source_finalized_missing_uuid"] += 1
                continue
            if uuid in seen_sales:
                stats["duplicate_source_finalized_uuid"] += 1
            seen_sales.add(uuid)
            sale = by_uuid.get(uuid)
            if sale is not None:
                stats["matched_sale_uuid"] += 1
                if order_no and str(order_no) != sale[0]:
                    stats["sale_uuid_order_no_mismatch"] += 1
                if sale[2] is not None:
                    stats["sale_has_income_record_reference"] += 1
                if sale[3] is not None:
                    stats["sale_has_cogs_record_reference"] += 1
                if not synced:
                    stats["sale_received_sender_not_synced"] += 1
            elif order_no and str(order_no) in by_number:
                stats["sale_order_no_only_review_candidate"] += 1
            elif synced:
                stats["synced_sale_missing_receiver"] += 1
            else:
                stats["unsynced_sale_missing_receiver"] += 1
        else:
            stats["source_voided"] += 1
            order_no = payload.get("order_no")
            if not isinstance(order_no, str) or not order_no.strip():
                stats["source_void_missing_order_no"] += 1
                continue
            if order_no in seen_voids:
                stats["duplicate_source_void_order_no"] += 1
            seen_voids.add(order_no)
            receiver = by_number.get(order_no)
            if receiver is None:
                stats["void_no_receiver_sale_noop_candidate"] += 1
            elif str(receiver[0] or "").lower() == "voided" and receiver[1] > 0:
                stats["void_status_and_event_received"] += 1
            elif str(receiver[0] or "").lower() == "voided":
                stats["void_status_without_event"] += 1
            elif receiver[1] > 0:
                stats["void_event_without_status"] += 1
            elif synced:
                stats["synced_void_without_receiver_effect"] += 1
            else:
                stats["unsynced_void_without_receiver_effect"] += 1
    stats["accounting_sales_without_scanned_finalized_uuid"] = sum(
        uuid not in seen_sales for uuid in by_uuid
    )
    mandatory = (
        "source_finalized", "source_voided", "matched_sale_uuid",
        "synced_sale_missing_receiver", "synced_void_without_receiver_effect",
        "void_no_receiver_sale_noop_candidate", "sale_order_no_only_review_candidate",
        "duplicate_source_finalized_uuid", "duplicate_source_void_order_no",
        "duplicate_accounting_sale_uuid", "duplicate_accounting_sale_order_no",
        "void_status_and_event_received", "accounting_sales_without_scanned_finalized_uuid",
    )
    return {key: int(stats[key]) for key in sorted(set(mandatory) | set(stats))}
