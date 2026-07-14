from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class IntegrationReviewCreate(BaseModel):
    source_app: str
    source_event_id: str
    source_entity_type: str
    source_entity_id: str | None = None
    source_revision: int = 1
    financial_effect: str
    amount: float = 0
    currency: str = 'PHP'
    proposed_account_id: int | None = None
    proposed_journal: dict[str, Any] | None = None
    proposed_links: dict[str, Any] | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None
    idempotency_key: str | None = None


class IntegrationReviewDecision(BaseModel):
    account_id: int | None = None
    transaction_date: str | None = None
    payment_method: str | None = None
    category: str | None = None
    notes: str | None = None
    reason: str | None = None


class IntegrationReviewRetry(BaseModel):
    reason: str | None = None
