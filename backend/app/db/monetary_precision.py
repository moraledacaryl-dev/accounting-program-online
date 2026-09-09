from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import Column, Float, Numeric, event

MONEY_PRECISION = 20
MONEY_SCALE = 4
MONEY_TYPE = Numeric(MONEY_PRECISION, MONEY_SCALE, asdecimal=True)
CENT = Decimal('0.01')

# Canonical persisted monetary fields. Quantities, hours, percentages, and other
# measurements intentionally remain floating-point unless they represent money.
MONEY_COLUMNS: frozenset[tuple[str, str]] = frozenset({
    ('records', 'amount'),
    ('record_settlements', 'amount'),
    ('event_bookings', 'deposit_required'),
    ('event_bookings', 'subtotal_amount'),
    ('event_bookings', 'discount_amount'),
    ('event_bookings', 'tax_amount'),
    ('event_bookings', 'total_amount'),
    ('event_bookings', 'deposit_paid'),
    ('event_bookings', 'balance_due'),
    ('event_booking_lines', 'unit_price'),
    ('event_booking_lines', 'total_amount'),
    ('event_payments', 'amount'),
    ('employees', 'rate'),
    ('employees', 'daily_rate'),
    ('employees', 'hourly_rate'),
    ('employees', 'meal_allowance'),
    ('employees', 'transport_allowance'),
    ('treasury_accounts', 'opening_balance'),
    ('treasury_movements', 'amount'),
    ('treasury_reconciliations', 'statement_balance'),
    ('treasury_reconciliations', 'system_balance'),
    ('treasury_reconciliations', 'variance'),
    ('financial_accounts', 'variance_tolerance'),
    ('financial_accounts', 'opening_balance'),
    ('financial_accounts', 'current_balance'),
    ('money_transactions', 'amount'),
    ('account_transfers', 'amount'),
    ('cash_reconciliations', 'opening_balance'),
    ('cash_reconciliations', 'expected_in'),
    ('cash_reconciliations', 'expected_out'),
    ('cash_reconciliations', 'expected_closing'),
    ('cash_reconciliations', 'actual_counted'),
    ('cash_reconciliations', 'variance'),
    ('cash_reconciliation_lines', 'amount'),
    ('receivables', 'gross_amount'),
    ('receivables', 'amount_collected'),
    ('receivables', 'balance_due'),
    ('receivable_adjustments', 'amount'),
    ('payables', 'gross_amount'),
    ('payables', 'amount_paid'),
    ('payables', 'balance_due'),
    ('menu_items', 'price'),
    ('inventory_items', 'average_cost'),
    ('inventory_batches', 'unit_cost'),
    ('stock_movements', 'unit_cost'),
    ('stock_movements', 'total_cost'),
    ('batch_allocations', 'unit_cost'),
    ('batch_allocations', 'total_cost'),
    ('menu_skus', 'price'),
    ('menu_skus', 'packaging_cost'),
    ('menu_skus', 'labor_cost'),
    ('menu_skus', 'overhead_cost'),
    ('sale_orders', 'gross_amount'),
    ('sale_orders', 'discount_amount'),
    ('sale_orders', 'net_amount'),
    ('sale_orders', 'cogs_amount'),
    ('sale_order_lines', 'unit_price'),
    ('sale_order_lines', 'discount_amount'),
    ('sale_order_lines', 'line_total'),
    ('assets', 'acquisition_cost'),
    ('assets', 'salvage_value'),
    ('rate_plans', 'base_rate'),
    ('room_package_rules', 'extra_pax_rate'),
    ('bookings', 'gross_amount'),
    ('bookings', 'deposit_amount'),
    ('booking_folio_lines', 'unit_price'),
    ('booking_folio_lines', 'amount'),
    ('beds24_booking_maps', 'beds24_price'),
    ('beds24_booking_maps', 'beds24_tax'),
    ('beds24_booking_maps', 'beds24_deposit'),
    ('beds24_booking_maps', 'beds24_commission'),
    ('beds24_booking_maps', 'beds24_total_charges'),
    ('beds24_booking_maps', 'beds24_total_payments'),
    ('beds24_booking_maps', 'beds24_total_balance'),
    ('room_breakfast_logs', 'charged_amount'),
    ('room_breakfast_logs', 'cogs_amount'),
    ('staff_meal_logs', 'cogs_amount'),
    ('channel_payouts', 'gross_amount'),
    ('channel_payouts', 'commission_amount'),
    ('channel_payouts', 'net_amount'),
    ('purchase_request_lines', 'estimated_unit_cost'),
    ('purchase_orders', 'total_amount'),
    ('purchase_order_lines', 'unit_cost'),
    ('purchase_order_lines', 'line_total'),
    ('receiving_records', 'total_amount'),
    ('receiving_lines', 'unit_cost'),
    ('receiving_lines', 'line_total'),
    ('payroll_period_lines', 'regular_amount'),
    ('payroll_period_lines', 'overtime_amount'),
    ('payroll_period_lines', 'holiday_amount'),
    ('payroll_period_lines', 'night_diff_amount'),
    ('payroll_period_lines', 'allowances'),
    ('payroll_period_lines', 'deductions'),
    ('payroll_period_lines', 'employer_contribution'),
    ('payroll_period_lines', 'gross_pay'),
    ('payroll_period_lines', 'net_pay'),
    ('payroll_lines', 'basic_pay'),
    ('payroll_lines', 'overtime_pay'),
    ('payroll_lines', 'night_diff_pay'),
    ('payroll_lines', 'holiday_pay'),
    ('payroll_lines', 'allowances'),
    ('payroll_lines', 'gross_pay'),
    ('payroll_lines', 'sss_employee'),
    ('payroll_lines', 'philhealth_employee'),
    ('payroll_lines', 'pagibig_employee'),
    ('payroll_lines', 'other_deductions'),
    ('payroll_lines', 'total_deductions'),
    ('payroll_lines', 'net_pay'),
    ('payroll_lines', 'sss_employer'),
    ('payroll_lines', 'philhealth_employer'),
    ('payroll_lines', 'pagibig_employer'),
    ('bir_book_entries', 'amount'),
    ('asset_depreciation_logs', 'amount'),
    ('asset_maintenance_logs', 'amount'),
    ('asset_disposal_logs', 'proceeds_amount'),
    ('asset_disposal_logs', 'writeoff_amount'),
    ('integration_review_items', 'amount'),
    ('payable_adjustments', 'amount'),
    ('supplier_credits', 'amount'),
    ('supplier_credits', 'applied_amount'),
    ('supplier_credits', 'balance_available'),
    ('supplier_credit_applications', 'amount'),
    ('supplier_credit_application_reversals', 'amount'),
})


def decimal_money(value: object | None) -> Decimal:
    if value in (None, ''):
        return Decimal('0')
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def centavos(value: object | None) -> Decimal:
    return decimal_money(value).quantize(CENT, rounding=ROUND_HALF_UP)


def _coerce_registered_money_column(column: Column, table) -> None:
    if (table.name, column.name) not in MONEY_COLUMNS:
        return
    if isinstance(column.type, Numeric):
        return
    if isinstance(column.type, Float):
        column.type = Numeric(MONEY_PRECISION, MONEY_SCALE, asdecimal=True)


# Register before model modules attach their Column objects to tables. Every model
# imports Base from app.db.database, and database imports this module first.
event.listen(Column, 'after_parent_attach', _coerce_registered_money_column, propagate=True)
