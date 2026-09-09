from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.business_clock import business_today


class SupplierCreditApplyPayload(BaseModel):
    payable_id: int
    amount: float
    application_date: str | None = None
    notes: str | None = None

    def resolved_application_date(self) -> str:
        return (self.application_date or '').strip() or business_today()


class SupplierCreditReversePayload(BaseModel):
    reversal_date: str | None = None
    reason: str = Field(min_length=3, max_length=1000)

    def resolved_reversal_date(self) -> str:
        return (self.reversal_date or '').strip() or business_today()
