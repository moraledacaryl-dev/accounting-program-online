from __future__ import annotations

import json
from typing import Any
from pydantic import BaseModel, Field, field_validator


class IntegrationReviewCreate(BaseModel):
    source_app: str
    source_event_id: str
    source_entity_type: str
    source_entity_id: str | None = None
    source_revision: int = 1
    financial_effect: str
    amount: float = Field(default=0, allow_inf_nan=False)
    currency: str = 'PHP'
    proposed_account_id: int | None = None
    proposed_journal: dict[str, Any] | None = None
    proposed_links: dict[str, Any] | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None
    idempotency_key: str | None = None

    @field_validator('proposed_journal', 'proposed_links', 'payload')
    @classmethod
    def valid_json_values(cls, value):
        # JSON permits neither NaN nor Infinity. Reject those transport values
        # before storing them or attempting to emit an invalid JSON response.
        try:
            json.dumps(value, allow_nan=False)
        except (ValueError, TypeError):
            raise ValueError('Integration data must contain valid JSON values.') from None
        return value


class IntegrationReviewDecision(BaseModel):
    account_id: int | None = None
    actual_amount_paid: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    transaction_date: str | None = None
    payment_method: str | None = None
    category: str | None = None
    notes: str | None = None
    reason: str | None = None


class IntegrationReviewRetry(BaseModel):
    reason: str | None = None
