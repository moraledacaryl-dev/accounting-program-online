from __future__ import annotations

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.database import Base


class OperationsOutboxEvent(Base):
    __tablename__ = 'operations_outbox_events'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(120), index=True)
    envelope_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default='pending', index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_attempt_at = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    updated_at = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
