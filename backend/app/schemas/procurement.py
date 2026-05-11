from __future__ import annotations

from pydantic import BaseModel, Field


class PurchaseRequestLineInput(BaseModel):
    inventory_item_id: int | None = None
    description: str | None = None
    quantity: float = 0
    unit: str | None = None
    estimated_unit_cost: float = 0
    notes: str | None = None
    sort_order: int = 0


class PurchaseRequestCreate(BaseModel):
    request_no: str | None = None
    request_date: str | None = None
    needed_by_date: str | None = None
    department: str | None = None
    supplier_id: int | None = None
    status: str = 'draft'
    notes: str | None = None
    lines: list[PurchaseRequestLineInput] = Field(default_factory=list)


class PurchaseRequestUpdate(BaseModel):
    request_date: str | None = None
    needed_by_date: str | None = None
    department: str | None = None
    supplier_id: int | None = None
    status: str | None = None
    notes: str | None = None
    lines: list[PurchaseRequestLineInput] | None = None


class PurchaseOrderLineInput(BaseModel):
    purchase_request_line_id: int | None = None
    inventory_item_id: int | None = None
    description: str | None = None
    quantity_ordered: float = 0
    unit: str | None = None
    unit_cost: float = 0
    notes: str | None = None
    sort_order: int = 0


class PurchaseOrderCreate(BaseModel):
    po_no: str | None = None
    po_date: str | None = None
    supplier_id: int | None = None
    purchase_request_id: int | None = None
    status: str = 'draft'
    payment_terms: str | None = None
    expected_delivery_date: str | None = None
    notes: str | None = None
    lines: list[PurchaseOrderLineInput] = Field(default_factory=list)


class PurchaseOrderUpdate(BaseModel):
    po_date: str | None = None
    supplier_id: int | None = None
    purchase_request_id: int | None = None
    status: str | None = None
    payment_terms: str | None = None
    expected_delivery_date: str | None = None
    notes: str | None = None
    lines: list[PurchaseOrderLineInput] | None = None


class ReceivingLineInput(BaseModel):
    purchase_order_line_id: int | None = None
    inventory_item_id: int | None = None
    description: str | None = None
    quantity_received: float = 0
    unit: str | None = None
    unit_cost: float = 0
    notes: str | None = None
    sort_order: int = 0


class ReceivingCreate(BaseModel):
    receiving_no: str | None = None
    receiving_date: str | None = None
    supplier_id: int | None = None
    purchase_order_id: int | None = None
    status: str = 'draft'
    reference_no: str | None = None
    notes: str | None = None
    lines: list[ReceivingLineInput] = Field(default_factory=list)
    post_to_stock: bool = True
    auto_create_payable: bool = True


class ReceivingUpdate(BaseModel):
    receiving_date: str | None = None
    supplier_id: int | None = None
    purchase_order_id: int | None = None
    status: str | None = None
    reference_no: str | None = None
    notes: str | None = None
    lines: list[ReceivingLineInput] | None = None
    post_to_stock: bool = True
    auto_create_payable: bool = True


class ProcurementStatusAction(BaseModel):
    status: str
    notes: str | None = None
    auto_create_payable: bool = True
