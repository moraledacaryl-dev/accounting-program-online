"""Append-only, non-financial review evidence for missing journal links."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class JournalLinkageReview(Base):
    __tablename__ = 'journal_linkage_reviews'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    money_transaction_id: Mapped[int] = mapped_column(
        ForeignKey('money_transactions.id'), nullable=False, index=True,
    )
    # All statuses are evidence triage, never automatic accounting resolution.
    decision: Mapped[str] = mapped_column(String(45), nullable=False)
    supporting_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_journal_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey('journal_entries.id'), nullable=True,
    )
    reviewed_by: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index('ix_journal_linkage_reviews_transaction_time', 'money_transaction_id', 'id'),
    )
