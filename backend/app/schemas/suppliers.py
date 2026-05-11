from __future__ import annotations

from pydantic import BaseModel


class SupplierCreate(BaseModel):
    name: str
    code: str | None = None
    supplier_type: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    tin: str | None = None
    tax_id: str | None = None
    payment_terms: str | None = None
    category: str | None = None
    is_active: bool = True
    notes: str | None = None


class SupplierUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    supplier_type: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    tin: str | None = None
    tax_id: str | None = None
    payment_terms: str | None = None
    category: str | None = None
    is_active: bool | None = None
    notes: str | None = None
