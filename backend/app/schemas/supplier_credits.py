from __future__ import annotations

from pydantic import BaseModel

from app.core.business_clock import business_today


class SupplierCreditApplyPayload(BaseModel):
    payable_id: int
    amount: float
    application_date: str | None = None
    notes: str | None = None

    def resolved_application_date(self) -> str:
        return (self.application_date or '').strip() or business_today()
