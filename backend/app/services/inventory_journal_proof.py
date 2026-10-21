"""Read-only proof of Accounting-owned posting for an Inventory event.

Transport delivery and reviewer acceptance do not imply a posted journal.
The only positive proof is an accepted review linked to a non-reversed,
posted, balanced journal entry in the authoritative Accounting database.
"""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import IntegrationReviewItem, JournalEntry, JournalLine


def inventory_journal_proof(db: Session, source_event_id: str) -> dict | None:
    row = db.scalar(
        select(IntegrationReviewItem)
        .where(
            IntegrationReviewItem.source_app == "inventory",
            IntegrationReviewItem.source_event_id == source_event_id,
        )
        .order_by(IntegrationReviewItem.source_revision.desc(), IntegrationReviewItem.id.desc())
        .limit(1)
    )
    if row is None:
        return None

    journal = db.get(JournalEntry, row.accepted_journal_entry_id) if row.accepted_journal_entry_id else None
    debit = credit = Decimal("0")
    line_count = 0
    if journal:
        lines = db.scalars(select(JournalLine).where(JournalLine.journal_entry_id == journal.id)).all()
        line_count = len(lines)
        debit = sum((Decimal(str(line.debit or 0)) for line in lines), Decimal("0"))
        credit = sum((Decimal(str(line.credit or 0)) for line in lines), Decimal("0"))
    confirmed = bool(
        row.status == "accepted"
        and journal
        and journal.status == "posted"
        and not journal.is_reversed
        and line_count >= 2
        and debit > 0
        and debit == credit
    )
    return {
        "source_app": "inventory",
        "source_event_id": row.source_event_id,
        "source_revision": row.source_revision,
        "review_id": row.id,
        "review_status": row.status,
        "financial_effect": row.financial_effect,
        "accepted_journal_entry_id": row.accepted_journal_entry_id,
        "accepted_payable_id": row.accepted_payable_id,
        "accepted_receivable_id": row.accepted_receivable_id,
        "accepted_transaction_id": row.accepted_transaction_id,
        "journal_status": journal.status if journal else None,
        "journal_is_reversed": bool(journal.is_reversed) if journal else None,
        "journal_line_count": line_count,
        "journal_debit": str(debit) if journal else None,
        "journal_credit": str(credit) if journal else None,
        "ledger_posting_confirmed": confirmed,
    }
