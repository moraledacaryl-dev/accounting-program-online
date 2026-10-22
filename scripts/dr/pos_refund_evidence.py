"""Aggregate-only comparison of POS refunds to Accounting cash/review receipts.

No payment identifier, account ID, amount, guest or tender is emitted.
A matched Review Inbox receipt is not a posted refund or a bank settlement.
"""
from __future__ import annotations

import json
from collections import Counter
from decimal import Decimal, InvalidOperation

REFUND_SQL = """
SELECT external_id, status, direction, amount, financial_account_id,
       category, payment_method, is_reversed
FROM money_transactions
WHERE external_source='dedicated_pos_cloud'
  AND external_id LIKE 'refund-payment:%'
"""
REVIEW_ID_PREFIX = "pos:cash:"


def _money(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite():
            raise ValueError("Nonfinite refund amount.")
        return number.quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Invalid refund monetary amount.") from None


def compare_refunds(pos_rows, receipt_rows, review_rows=()):
    stats = Counter()
    receipts: dict[str, tuple] = {}
    for ident, status, direction, amount, account_id, category, payment_method, reversed_flag in receipt_rows:
        stats["receiver_refund_rows"] += 1
        if not isinstance(ident, str) or not ident.startswith("refund-payment:"):
            stats["receiver_refund_invalid_identity"] += 1
            continue
        if ident in receipts:
            stats["duplicate_receiver_refund_identity"] += 1
        else:
            receipts[ident] = (
                str(status or "").lower(), str(direction or "").lower(),
                amount, account_id, str(category or "").strip(),
                str(payment_method or "").strip().lower(), bool(reversed_flag),
            )
    reviews: dict[str, str] = {}
    for event_id, status in review_rows:
        if not isinstance(event_id, str) or not event_id.startswith(REVIEW_ID_PREFIX + "refund-payment:"):
            continue
        if event_id in reviews:
            stats["duplicate_refund_review_identity"] += 1
        reviews[event_id] = str(status or "").lower()

    seen = set()
    for event_type, status, raw in pos_rows:
        if event_type != "payment.refunded":
            continue
        stats["source_refunded_events"] += 1
        try:
            envelope = json.loads(raw)
            if not isinstance(envelope, dict):
                raise ValueError("Invalid POS refund envelope.")
            payment = envelope.get("payment")
            if not isinstance(payment, dict):
                raise ValueError("Refund payment details missing.")
        except (ValueError, TypeError):
            raise ValueError("Malformed POS refund event.") from None
        tender = str(payment.get("tender_type") or "").strip().lower()
        if tender == "room_charge":
            stats["room_charge_refund_owned_by_separate_reversal"] += 1
            continue
        if not tender:
            stats["source_refund_missing_tender"] += 1
            continue
        payment_id = payment.get("id")
        if payment_id is None or not str(payment_id).strip():
            stats["source_refund_missing_payment_identity"] += 1
            continue
        ident = "refund-payment:" + str(payment_id)
        if ident in seen:
            stats["duplicate_source_refund_identity"] += 1
        seen.add(ident)
        try:
            amount = _money(payment.get("amount"))
        except ValueError:
            stats["source_refund_invalid_amount"] += 1
            continue
        if amount <= 0:
            stats["source_refund_nonpositive_amount"] += 1
            continue
        receipt = receipts.get(ident)
        review = reviews.get(REVIEW_ID_PREFIX + ident)
        if review is not None:
            stats["refund_review_receipt_matched"] += 1
            if review in {"ready_for_review", "awaiting_approval", "pending"}:
                stats["refund_review_pending_acceptance"] += 1
            elif review == "accepted":
                stats["refund_review_accepted_not_independent_bank_proof"] += 1
            else:
                stats["refund_review_other_status"] += 1
        if receipt is None:
            if review is None:
                stats["source_refund_without_cash_or_review_receipt"] += 1
                if str(status or "").lower() == "synced":
                    stats["synced_refund_without_receipt"] += 1
            continue
        stats["refund_direct_cash_receipt_matched"] += 1
        if review is not None:
            stats["refund_direct_cash_and_review_both_present"] += 1
        state, direction, ledger_amount, account, category, method, reversed_flag = receipt
        if state != "posted":
            stats["refund_receiver_not_posted"] += 1
        if direction != "out":
            stats["refund_receiver_wrong_direction"] += 1
        if reversed_flag:
            stats["refund_receiver_reversed"] += 1
        if category != "POS Refund":
            stats["refund_receiver_wrong_category"] += 1
        try:
            if _money(ledger_amount) != amount:
                stats["refund_receiver_amount_mismatch"] += 1
        except ValueError:
            stats["refund_receiver_invalid_amount"] += 1
        declared_account = payment.get("accounting_financial_account_id")
        if declared_account not in (None, ""):
            if str(account) != str(declared_account):
                stats["refund_receiver_account_mismatch"] += 1
        else:
            stats["source_refund_account_unverified"] += 1
        if method != tender:
            stats["refund_receiver_tender_mismatch"] += 1
    stats["accounting_refund_rows_not_in_scanned_source"] = sum(ident not in seen for ident in receipts)
    mandatory = (
        "source_refunded_events", "room_charge_refund_owned_by_separate_reversal",
        "refund_direct_cash_receipt_matched", "refund_review_receipt_matched",
        "refund_review_pending_acceptance", "source_refund_without_cash_or_review_receipt",
        "synced_refund_without_receipt", "refund_receiver_wrong_direction",
        "refund_receiver_amount_mismatch", "refund_receiver_account_mismatch",
        "refund_receiver_tender_mismatch", "refund_receiver_not_posted",
        "refund_receiver_reversed", "duplicate_source_refund_identity",
        "duplicate_receiver_refund_identity", "refund_direct_cash_and_review_both_present",
    )
    return {name: int(stats[name]) for name in sorted(set(stats) | set(mandatory))}
