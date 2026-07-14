from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class FinancialAccountCreate(BaseModel):
    name: str
    code: str | None = None
    account_type: str
    subtype: str | None = None
    currency: str = 'PHP'
    is_active: bool = True
    requires_daily_reconciliation: bool = True
    reconciliation_mode: str = 'daily'
    requires_physical_count: bool = False
    reconciliation_day_of_week: int | None = None
    reconciliation_day_of_month: int | None = None
    variance_tolerance: float = 0
    approval_required_on_variance: bool = True
    opening_balance: float = 0
    current_balance: float | None = None
    department: str | None = None
    notes: str | None = None


class FinancialAccountUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    account_type: str | None = None
    subtype: str | None = None
    currency: str | None = None
    is_active: bool | None = None
    requires_daily_reconciliation: bool | None = None
    reconciliation_mode: str | None = None
    requires_physical_count: bool | None = None
    reconciliation_day_of_week: int | None = None
    reconciliation_day_of_month: int | None = None
    variance_tolerance: float | None = None
    approval_required_on_variance: bool | None = None
    opening_balance: float | None = None
    current_balance: float | None = None
    department: str | None = None
    notes: str | None = None


class MoneyTransactionCreate(BaseModel):
    transaction_date: str | None = None
    direction: str
    financial_account_id: int
    module: str = 'finance'
    category: str | None = None
    subcategory: str | None = None
    level3_item: str | None = None
    amount: float
    payment_method: str | None = 'cash'
    reference_no: str | None = None
    counterparty_name: str | None = None
    notes: str | None = None
    linked_record_type: str | None = None
    linked_record_id: int | None = None
    receivable_id: int | None = None
    payable_id: int | None = None
    bir_include: bool = False
    status: str = 'posted'
    auto_post_accounting: bool = False
    allow_overdraw: bool = False
    external_source: str | None = None
    external_id: str | None = None


class MoneyTransactionUpdate(BaseModel):
    transaction_date: str | None = None
    direction: str | None = None
    financial_account_id: int | None = None
    module: str | None = None
    category: str | None = None
    subcategory: str | None = None
    level3_item: str | None = None
    amount: float | None = None
    payment_method: str | None = None
    reference_no: str | None = None
    counterparty_name: str | None = None
    notes: str | None = None
    linked_record_type: str | None = None
    linked_record_id: int | None = None
    receivable_id: int | None = None
    payable_id: int | None = None
    bir_include: bool | None = None
    status: str | None = None
    auto_post_accounting: bool = False
    allow_overdraw: bool = False


class AccountTransferCreate(BaseModel):
    transfer_date: str | None = None
    from_account_id: int
    to_account_id: int
    amount: float
    reference_no: str | None = None
    notes: str | None = None
    status: str = 'posted'
    auto_post_accounting: bool = False
    allow_overdraw: bool = False
    external_source: str | None = None
    external_id: str | None = None


class AccountTransferUpdate(BaseModel):
    transfer_date: str | None = None
    from_account_id: int | None = None
    to_account_id: int | None = None
    amount: float | None = None
    reference_no: str | None = None
    notes: str | None = None
    status: str | None = None
    auto_post_accounting: bool = False
    allow_overdraw: bool = False


class CashflowActionPayload(BaseModel):
    action_date: str | None = None
    reason: str | None = None


class CashCountLineInput(BaseModel):
    line_label: str
    amount: float
    notes: str | None = None
    sort_order: int = 0


class CashReconciliationCreate(BaseModel):
    financial_account_id: int
    reconciliation_date: str
    shift_name: str | None = None
    actual_counted: float
    status: str = 'counted'
    counted_by: str | None = None
    notes: str | None = None
    lines: list[CashCountLineInput] = Field(default_factory=list)


class ReceivableCreate(BaseModel):
    source_type: str | None = None
    source_id: int | None = None
    counterparty_name: str
    receivable_type: str = 'guest_balance'
    transaction_date: str | None = None
    due_date: str | None = None
    gross_amount: float
    amount_collected: float = 0
    status: str = 'open'
    notes: str | None = None
    bir_include: bool = False
    external_source: str | None = None
    external_id: str | None = None
    reverses_source_type: str | None = None
    reverses_source_id: int | None = None


class ReceivableCollectPayload(BaseModel):
    amount: float
    collection_date: str | None = None
    financial_account_id: int
    payment_method: str | None = 'cash'
    reference_no: str | None = None
    notes: str | None = None
    module: str = 'finance'
    category: str = 'Receivables'
    subcategory: str = 'Guest Receivables'
    level3_item: str = 'Guest Balance'
    auto_post_accounting: bool = False


class PayableCreate(BaseModel):
    source_type: str | None = None
    source_id: int | None = None
    supplier_name: str
    payable_type: str = 'supplier_bill'
    bill_date: str | None = None
    due_date: str | None = None
    gross_amount: float
    amount_paid: float = 0
    status: str = 'open'
    notes: str | None = None
    bir_include: bool = False


class PayablePayPayload(BaseModel):
    amount: float
    payment_date: str | None = None
    financial_account_id: int
    payment_method: str | None = 'cash'
    reference_no: str | None = None
    notes: str | None = None
    module: str = 'finance'
    category: str = 'Payables'
    subcategory: str = 'Supplier Payables'
    level3_item: str = 'Inventory Suppliers'
    auto_post_accounting: bool = False


class CashflowTemplateCreate(BaseModel):
    name: str
    direction: str
    default_module: str = 'finance'
    default_category: str | None = None
    default_subcategory: str | None = None
    default_level3_item: str | None = None
    default_account_id: int | None = None
    default_payment_method: str | None = None
    default_bir_include: bool = False
    default_notes: str | None = None
    is_active: bool = True


class CashflowTemplateUpdate(BaseModel):
    name: str | None = None
    direction: str | None = None
    default_module: str | None = None
    default_category: str | None = None
    default_subcategory: str | None = None
    default_level3_item: str | None = None
    default_account_id: int | None = None
    default_payment_method: str | None = None
    default_bir_include: bool | None = None
    default_notes: str | None = None
    is_active: bool | None = None


class CashflowSummaryQuery(BaseModel):
    date: str | None = None


class CashflowFilterQuery(BaseModel):
    account_id: int | None = None
    start_date: str | None = None
    end_date: str | None = None
    direction: str | None = None
    module: str | None = None
    status: str | None = None
    q: str | None = None
    limit: int = 200


class AccountLedgerQuery(BaseModel):
    account_id: int
    start_date: str | None = None
    end_date: str | None = None
    include_reconciliations: bool = True
    limit: int = 500


class CashflowTemplateLaunchPayload(BaseModel):
    template_id: int
    overrides: dict[str, Any] = Field(default_factory=dict)
