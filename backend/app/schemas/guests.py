from __future__ import annotations

from pydantic import BaseModel, Field


class GuestPreferenceInput(BaseModel):
    preference_key: str
    preference_value: str | None = None


class GuestCreate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    city: str | None = None
    nationality: str | None = None
    birthday: str | None = None
    company: str | None = None
    vip_flag: bool = False
    status_tags: str | None = None
    notes: str | None = None
    is_active: bool = True
    tags: list[str] = Field(default_factory=list)
    preferences: list[GuestPreferenceInput] = Field(default_factory=list)


class GuestUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    city: str | None = None
    nationality: str | None = None
    birthday: str | None = None
    company: str | None = None
    vip_flag: bool | None = None
    status_tags: str | None = None
    notes: str | None = None
    is_active: bool | None = None
    tags: list[str] | None = None
    preferences: list[GuestPreferenceInput] | None = None


class GuestMergePayload(BaseModel):
    source_guest_id: int | None = None
    source_guest_ids: list[int] = Field(default_factory=list)
    target_guest_id: int
    reason: str | None = None


class BookingFolioCreate(BaseModel):
    booking_id: int
    guest_id: int | None = None
    folio_no: str | None = None
    notes: str | None = None


class BookingFolioUpdate(BaseModel):
    guest_id: int | None = None
    status: str | None = None
    notes: str | None = None


class BookingFolioLineCreate(BaseModel):
    line_type: str
    description: str
    quantity: float = 1
    unit_price: float = 0
    amount: float | None = None
    transaction_date: str | None = None
    reference_no: str | None = None
    linked_money_transaction_id: int | None = None
    linked_receivable_id: int | None = None
    linked_payable_id: int | None = None
    linked_record_id: int | None = None
    notes: str | None = None


class BookingFolioLineUpdate(BaseModel):
    line_type: str | None = None
    description: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    amount: float | None = None
    transaction_date: str | None = None
    reference_no: str | None = None
    linked_money_transaction_id: int | None = None
    linked_receivable_id: int | None = None
    linked_payable_id: int | None = None
    linked_record_id: int | None = None
    notes: str | None = None


class BookingFolioAction(BaseModel):
    status: str
    notes: str | None = None
