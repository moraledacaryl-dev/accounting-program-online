from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field

class RecordCreate(BaseModel):
    category: str
    bucket: str
    item: str
    name: str = ''
    amount: float | None = None
    quantity: float | None = None
    unit: str | None = None
    direction: str = 'neutral'
    payment_method: str | None = None
    counterparty: str | None = None
    channel: str | None = None
    bir_status: str = 'internal_only'
    workflow_status: str = 'draft'
    transaction_date: str | None = None
    due_date: str | None = None
    document_ref: str | None = None
    notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class RecordUpdate(BaseModel):
    category: str | None = None
    bucket: str | None = None
    item: str | None = None
    name: str | None = None
    amount: float | None = None
    quantity: float | None = None
    unit: str | None = None
    direction: str | None = None
    payment_method: str | None = None
    counterparty: str | None = None
    channel: str | None = None
    bir_status: str | None = None
    workflow_status: str | None = None
    transaction_date: str | None = None
    due_date: str | None = None
    document_ref: str | None = None
    notes: str | None = None
    metadata: dict[str, Any] | None = None

class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str | None = None
    role: str = 'admin'
    role_ids: list[int] = Field(default_factory=list)
    is_active: bool = True

class UserUpdate(BaseModel):
    full_name: str | None = None
    role: str | None = None
    role_ids: list[int] | None = None
    is_active: bool | None = None
    password: str | None = None

class TokenOut(BaseModel):
    access_token: str
    token_type: str = 'bearer'

class LoginPayload(BaseModel):
    username: str
    password: str

class IntegrationTokenPayload(BaseModel):
    secret: str

class EmployeeCreate(BaseModel):
    full_name: str
    department: str = ''
    job_title: str = ''
    employment_profile: str = 'Regular'
    compensation_type: str = 'Monthly'
    rate: float = 0
    daily_rate: float = 0
    hourly_rate: float = 0
    meal_allowance: float = 0
    transport_allowance: float = 0
    tin: str | None = None
    sss_number: str | None = None
    philhealth_number: str | None = None
    pagibig_number: str | None = None
    is_active: bool = True

class EmployeeUpdate(BaseModel):
    full_name: str | None = None
    department: str | None = None
    job_title: str | None = None
    employment_profile: str | None = None
    compensation_type: str | None = None
    rate: float | None = None
    daily_rate: float | None = None
    hourly_rate: float | None = None
    meal_allowance: float | None = None
    transport_allowance: float | None = None
    tin: str | None = None
    sss_number: str | None = None
    philhealth_number: str | None = None
    pagibig_number: str | None = None
    is_active: bool | None = None

class AttendanceCreate(BaseModel):
    employee_id: int
    work_date: str
    time_in: str | None = None
    time_out: str | None = None
    late_minutes: float = 0
    undertime_minutes: float = 0
    overtime_hours: float = 0
    night_diff_hours: float = 0
    day_type: str = 'regular_day'
    is_absent: bool = False
    leave_type: str | None = None
    notes: str | None = None

class InventoryItemCreate(BaseModel):
    name: str
    module_name: str = 'Inventory'
    category_name: str = ''
    subcategory_name: str = ''
    unit: str = ''
    quantity_on_hand: float = 0
    reorder_level: float = 0
    average_cost: float = 0
    notes: str | None = None

class InventoryItemUpdate(BaseModel):
    name: str | None = None
    module_name: str | None = None
    category_name: str | None = None
    subcategory_name: str | None = None
    unit: str | None = None
    reorder_level: float | None = None
    notes: str | None = None

class StockMovementCreate(BaseModel):
    item_id: int
    movement_type: str
    quantity: float
    unit_cost: float = 0
    total_item_cost: float | None = None
    delivery_cost: float = 0
    other_cost: float = 0
    reason: str | None = None
    module_slug: str | None = None
    reference_no: str | None = None
    notes: str | None = None
    movement_date: str | None = None
    supplier: str | None = None
    log_expense: bool = False
    expense_module_slug: str = 'procurement'
    expense_payment_method: str | None = 'cash'
    expense_counterparty: str | None = None
    expense_notes: str | None = None

class AssetCreate(BaseModel):
    name: str
    asset_class: str = ''
    location: str | None = None
    acquisition_cost: float = 0
    acquisition_date: str | None = None
    payment_method: str | None = 'cash'
    counterparty: str | None = None
    auto_post_accounting: bool = False
    useful_life_months: int = 60
    salvage_value: float = 0
    condition_status: str = 'Good'
    operational_status: str = 'Active'
    notes: str | None = None

class AssetUpdate(BaseModel):
    name: str | None = None
    asset_class: str | None = None
    location: str | None = None
    acquisition_cost: float | None = None
    useful_life_months: int | None = None
    salvage_value: float | None = None
    condition_status: str | None = None
    operational_status: str | None = None
    notes: str | None = None

class MasterValueCreate(BaseModel):
    group_name: str
    value: str
    code: str | None = None
    is_active: bool = True

class MasterValueUpdate(BaseModel):
    group_name: str | None = None
    value: str | None = None
    code: str | None = None
    is_active: bool | None = None

class BookingCreate(BaseModel):
    guest_id: int | None = None
    guest_name: str
    room_id: int | None = None
    room_type_id: int | None = None
    rate_plan_id: int | None = None
    channel_id: int | None = None
    room_name: str = ''
    room_type: str | None = None
    channel: str = 'Walk-in'
    status: str = 'confirmed'
    check_in: str | None = None
    check_out: str | None = None
    gross_amount: float = 0
    deposit_amount: float = 0
    breakfast_included: int = 0
    payment_method: str | None = 'cash'
    auto_post_accounting: bool = False
    notes: str | None = None


class BookingUpdate(BaseModel):
    guest_id: int | None = None
    guest_name: str | None = None
    room_id: int | None = None
    room_type_id: int | None = None
    rate_plan_id: int | None = None
    channel_id: int | None = None
    room_name: str | None = None
    room_type: str | None = None
    channel: str | None = None
    status: str | None = None
    check_in: str | None = None
    check_out: str | None = None
    gross_amount: float | None = None
    deposit_amount: float | None = None
    breakfast_included: int | None = None
    payment_method: str | None = 'cash'
    auto_post_accounting: bool = False
    auto_reverse_on_cancel: bool = True
    effective_date: str | None = None
    notes: str | None = None


class ChannelPayoutCreate(BaseModel):
    channel_id: int | None = None
    channel: str | None = None
    booking_ref: str | None = None
    gross_amount: float = 0
    commission_amount: float = 0
    net_amount: float = 0
    payment_method: str | None = 'ota_payout'
    auto_post_accounting: bool = False
    expected_payout_date: str | None = None
    actual_payout_date: str | None = None
    status: str = 'pending'
    notes: str | None = None


class ChannelPayoutUpdate(BaseModel):
    channel_id: int | None = None
    channel: str | None = None
    booking_ref: str | None = None
    gross_amount: float | None = None
    commission_amount: float | None = None
    net_amount: float | None = None
    payment_method: str | None = None
    auto_post_accounting: bool = False
    expected_payout_date: str | None = None
    actual_payout_date: str | None = None
    status: str | None = None
    notes: str | None = None


class ChannelPayoutSettle(BaseModel):
    actual_payout_date: str | None = None
    payment_method: str | None = 'bank_transfer'
    settlement_module_slug: str = 'finance'
    auto_post_accounting: bool = False
    notes: str | None = None

class PayrollLineCreate(BaseModel):
    employee_id: int | None = None
    employee_name: str
    department: str | None = None
    hours_worked: float = 0
    basic_pay: float = 0
    overtime_pay: float = 0
    night_diff_pay: float = 0
    holiday_pay: float = 0
    allowances: float = 0
    gross_pay: float = 0
    sss_employee: float = 0
    philhealth_employee: float = 0
    pagibig_employee: float = 0
    other_deductions: float = 0
    total_deductions: float = 0
    net_pay: float = 0
    sss_employer: float = 0
    philhealth_employer: float = 0
    pagibig_employer: float = 0

class PayrollRunCreate(BaseModel):
    name: str
    period_start: str | None = None
    period_end: str | None = None
    release_date: str | None = None
    status: str = 'draft'
    notes: str | None = None
    lines: list[PayrollLineCreate] = Field(default_factory=list)

class PayrollGeneratePayload(BaseModel):
    name: str
    period_start: str
    period_end: str
    release_date: str | None = None
    include_allowances: bool = True

class JournalLineCreate(BaseModel):
    account_code: str
    account_name: str
    debit: float = 0
    credit: float = 0
    memo: str | None = None

class JournalEntryCreate(BaseModel):
    entry_date: str | None = None
    reference_no: str | None = None
    description: str | None = None
    source_module: str | None = None
    status: str = 'draft'
    lines: list[JournalLineCreate] = Field(default_factory=list)

class TaxonomyNodeCreate(BaseModel):
    module_slug: str
    module_name: str
    category: str
    bucket: str
    item: str
    is_active: bool = True

class TaxonomyNodeUpdate(BaseModel):
    module_name: str | None = None
    category: str | None = None
    bucket: str | None = None
    item: str | None = None
    is_active: bool | None = None

class MenuItemCreate(BaseModel):
    name: str
    module_slug: str = 'restaurant'
    category: str = ''
    price: float = 0
    is_active: bool = True
    notes: str | None = None

class MenuItemUpdate(BaseModel):
    name: str | None = None
    module_slug: str | None = None
    category: str | None = None
    price: float | None = None
    is_active: bool | None = None
    notes: str | None = None

class RecipeLineCreate(BaseModel):
    inventory_item_id: int
    quantity: float
    unit: str = ''
    notes: str | None = None


class PrepComponentItemPayload(BaseModel):
    inventory_item_id: int
    quantity: float
    unit: str = ''
    wastage_percent: float = 0
    sort_order: int = 0
    notes: str | None = None


class PrepComponentCreate(BaseModel):
    name: str
    category_name: str = ''
    yield_quantity: float = 1
    yield_unit: str = ''
    is_active: bool = True
    notes: str | None = None
    items: list[PrepComponentItemPayload] = Field(default_factory=list)


class PrepComponentUpdate(BaseModel):
    name: str | None = None
    category_name: str | None = None
    yield_quantity: float | None = None
    yield_unit: str | None = None
    is_active: bool | None = None
    notes: str | None = None
    items: list[PrepComponentItemPayload] | None = None


class MenuSKURecipeItemPayload(BaseModel):
    line_type: str = 'inventory'
    inventory_item_id: int | None = None
    component_id: int | None = None
    quantity: float
    unit: str = ''
    wastage_percent: float = 0
    sort_order: int = 0
    notes: str | None = None


class MenuSKUCreate(BaseModel):
    menu_item_id: int
    sku_code: str | None = None
    variant_name: str = ''
    size_label: str | None = None
    price: float = 0
    packaging_cost: float = 0
    labor_cost: float = 0
    overhead_cost: float = 0
    is_active: bool = True
    notes: str | None = None
    recipe_items: list[MenuSKURecipeItemPayload] = Field(default_factory=list)


class MenuSKUUpdate(BaseModel):
    menu_item_id: int | None = None
    sku_code: str | None = None
    variant_name: str | None = None
    size_label: str | None = None
    price: float | None = None
    packaging_cost: float | None = None
    labor_cost: float | None = None
    overhead_cost: float | None = None
    is_active: bool | None = None
    notes: str | None = None
    recipe_items: list[MenuSKURecipeItemPayload] | None = None


class MenuPromotionCreate(BaseModel):
    name: str
    applies_to: str = 'sku'
    sku_id: int | None = None
    menu_item_id: int | None = None
    promo_type: str = 'percent_off'
    promo_value: float = 0
    min_qty: float | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_active: bool = True
    notes: str | None = None


class MenuPromotionUpdate(BaseModel):
    name: str | None = None
    applies_to: str | None = None
    sku_id: int | None = None
    menu_item_id: int | None = None
    promo_type: str | None = None
    promo_value: float | None = None
    min_qty: float | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_active: bool | None = None
    notes: str | None = None


class SaleOrderLineCreate(BaseModel):
    menu_item_id: int
    sku_id: int | None = None
    quantity: float = 1
    unit_price: float | None = None
    discount_amount: float | None = None
    notes: str | None = None


class SaleOrderCreate(BaseModel):
    order_no: str | None = None
    order_date: str | None = None
    payment_method: str | None = 'cash'
    channel: str | None = None
    counterparty: str | None = None
    booking_id: int | None = None
    folio_id: int | None = None
    notes: str | None = None
    strict_inventory: bool = True
    auto_post_accounting: bool = False
    external_source: str | None = None
    external_id: str | None = None
    manual_fallback_confirmed: bool = False
    lines: list[SaleOrderLineCreate] = Field(default_factory=list)


class SaleVoidPayload(BaseModel):
    reason: str
    void_date: str | None = None
    reverse_inventory: bool = True
    auto_post_accounting: bool = False


class StaffMealIngredientPayload(BaseModel):
    inventory_item_id: int
    quantity: float
    unit: str = ''
    notes: str | None = None


class StaffMealCreate(BaseModel):
    meal_no: str | None = None
    meal_date: str | None = None
    dish_name: str
    menu_item_id: int | None = None
    sku_id: int | None = None
    quantity: float = 1
    served_to: str | None = 'Kitchen Staff'
    strict_inventory: bool = True
    payment_method: str | None = 'inventory'
    auto_post_accounting: bool = False
    notes: str | None = None
    ingredients: list[StaffMealIngredientPayload] = Field(default_factory=list)


class RoomBreakfastCreate(BaseModel):
    breakfast_no: str | None = None
    booking_id: int | None = None
    meal_date: str | None = None
    guest_name: str | None = None
    menu_item_id: int
    sku_id: int | None = None
    quantity: float = 1
    charge_to_room: bool = True
    charged_amount: float | None = None
    strict_inventory: bool = True
    payment_method: str | None = 'cash'
    auto_post_accounting: bool = False
    notes: str | None = None

class BIRGeneratePayload(BaseModel):
    period_key: str


class BIRSelectionItem(BaseModel):
    source_type: str
    source_id: int
    include_in_bir: bool = True
    book_type: str | None = None
    tax_type: str | None = None
    notes: str | None = None


class BIRSelectionPayload(BaseModel):
    period_key: str
    selections: list[BIRSelectionItem] = Field(default_factory=list)


class AssetDepreciationCreate(BaseModel):
    period_key: str
    depreciation_date: str | None = None
    amount: float | None = None
    auto_post_accounting: bool = False
    notes: str | None = None


class AssetMaintenanceCreate(BaseModel):
    service_date: str | None = None
    vendor: str | None = None
    amount: float
    payment_method: str | None = 'cash'
    auto_post_accounting: bool = False
    notes: str | None = None


class AssetDisposalCreate(BaseModel):
    disposal_date: str | None = None
    proceeds_amount: float = 0
    writeoff_amount: float = 0
    payment_method: str | None = 'cash'
    auto_post_accounting: bool = False
    notes: str | None = None


class RecordSettlementCreate(BaseModel):
    record_id: int
    settlement_date: str | None = None
    amount: float
    payment_method: str | None = None
    reference_no: str | None = None
    notes: str | None = None

class PeriodLockPayload(BaseModel):
    period_key: str
    scope: str = 'bir'
    is_locked: bool = True
    notes: str | None = None

class ApprovalPayload(BaseModel):
    approved: bool = True
    note: str | None = None
