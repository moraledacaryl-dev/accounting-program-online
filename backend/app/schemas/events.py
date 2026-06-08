from __future__ import annotations

from pydantic import BaseModel, Field


class EventLinePayload(BaseModel):
    id: int | None = None
    line_type: str = 'package'
    description: str
    quantity: float = 1
    unit_price: float = 0
    total_amount: float | None = None
    notes: str | None = None
    sort_order: int = 0


class EventBookingPayload(BaseModel):
    event_no: str | None = None
    event_name: str
    client_name: str
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    event_type: str | None = None
    event_date: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    venue: str | None = None
    guest_count: int = 0
    package_name: str | None = None
    status: str = 'draft'
    quote_sent_at: str | None = None
    deposit_required: float = 0
    deposit_due_date: str | None = None
    discount_amount: float = 0
    tax_amount: float = 0
    notes: str | None = None
    lines: list[EventLinePayload] = Field(default_factory=list)


class EventBookingUpdate(BaseModel):
    event_no: str | None = None
    event_name: str | None = None
    client_name: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    event_type: str | None = None
    event_date: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    venue: str | None = None
    guest_count: int | None = None
    package_name: str | None = None
    status: str | None = None
    quote_sent_at: str | None = None
    deposit_required: float | None = None
    deposit_due_date: str | None = None
    discount_amount: float | None = None
    tax_amount: float | None = None
    notes: str | None = None
    lines: list[EventLinePayload] | None = None


class EventActionPayload(BaseModel):
    action_date: str | None = None
    note: str | None = None


class EventPaymentPayload(BaseModel):
    payment_date: str | None = None
    amount: float
    financial_account_id: int
    payment_method: str | None = 'cash'
    reference_no: str | None = None
    notes: str | None = None
