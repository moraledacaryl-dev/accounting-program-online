from __future__ import annotations
from sqlalchemy import Integer, String, Float, Text, DateTime, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.database import Base

class TimestampMixin:
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class User(Base, TimestampMixin):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default='admin', index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    user_roles: Mapped[list["UserRole"]] = relationship(back_populates='user', cascade='all, delete-orphan')
    permission_overrides: Mapped[list["UserPermissionOverride"]] = relationship(back_populates='user', cascade='all, delete-orphan')


class Role(Base, TimestampMixin):
    __tablename__ = 'roles'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    permissions: Mapped[list["RolePermission"]] = relationship(back_populates='role', cascade='all, delete-orphan')
    users: Mapped[list["UserRole"]] = relationship(back_populates='role', cascade='all, delete-orphan')


class Permission(Base, TimestampMixin):
    __tablename__ = 'permissions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(160), default='', index=True)
    group_name: Mapped[str] = mapped_column(String(120), default='General', index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    role_links: Mapped[list["RolePermission"]] = relationship(back_populates='permission', cascade='all, delete-orphan')
    user_overrides: Mapped[list["UserPermissionOverride"]] = relationship(back_populates='permission', cascade='all, delete-orphan')


class RolePermission(Base, TimestampMixin):
    __tablename__ = 'role_permissions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey('roles.id'), index=True)
    permission_id: Mapped[int] = mapped_column(ForeignKey('permissions.id'), index=True)
    allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped["Role"] = relationship(back_populates='permissions')
    permission: Mapped["Permission"] = relationship(back_populates='role_links')
    __table_args__ = (UniqueConstraint('role_id', 'permission_id', name='uq_role_permission'),)


class UserRole(Base, TimestampMixin):
    __tablename__ = 'user_roles'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey('roles.id'), index=True)
    user: Mapped["User"] = relationship(back_populates='user_roles')
    role: Mapped["Role"] = relationship(back_populates='users')
    __table_args__ = (UniqueConstraint('user_id', 'role_id', name='uq_user_role'),)


class UserPermissionOverride(Base, TimestampMixin):
    __tablename__ = 'user_permission_overrides'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    permission_id: Mapped[int] = mapped_column(ForeignKey('permissions.id'), index=True)
    is_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    user: Mapped["User"] = relationship(back_populates='permission_overrides')
    permission: Mapped["Permission"] = relationship(back_populates='user_overrides')
    __table_args__ = (UniqueConstraint('user_id', 'permission_id', name='uq_user_permission_override'),)


class SystemSetting(Base, TimestampMixin):
    __tablename__ = 'system_settings'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    value_json: Mapped[str] = mapped_column(Text, default='{}')
    updated_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

class Record(Base, TimestampMixin):
    __tablename__ = 'records'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    module_slug: Mapped[str] = mapped_column(String(100), index=True)
    module_name: Mapped[str] = mapped_column(String(200), index=True)
    category: Mapped[str] = mapped_column(String(200), index=True)
    bucket: Mapped[str] = mapped_column(String(200), index=True)
    item: Mapped[str] = mapped_column(String(200), index=True)
    name: Mapped[str] = mapped_column(String(255), default='')
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    direction: Mapped[str] = mapped_column(String(30), default='neutral', index=True)
    payment_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    counterparty: Mapped[str | None] = mapped_column(String(255), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bir_status: Mapped[str] = mapped_column(String(100), default='internal_only', index=True)
    workflow_status: Mapped[str] = mapped_column(String(100), default='draft', index=True)
    transaction_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    due_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    document_ref: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, default='{}')
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)


class RecordSettlement(Base, TimestampMixin):
    __tablename__ = 'record_settlements'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey('records.id'), index=True)
    settlement_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    amount: Mapped[float] = mapped_column(Float, default=0)
    payment_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reference_no: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    record: Mapped["Record"] = relationship()


class EventBooking(Base, TimestampMixin):
    __tablename__ = 'event_bookings'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_no: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    event_name: Mapped[str] = mapped_column(String(255), default='', index=True)
    client_name: Mapped[str] = mapped_column(String(255), default='', index=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    event_type: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    event_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    start_time: Mapped[str | None] = mapped_column(String(20), nullable=True)
    end_time: Mapped[str | None] = mapped_column(String(20), nullable=True)
    venue: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    guest_count: Mapped[int] = mapped_column(Integer, default=0)
    package_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default='draft', index=True)
    quote_sent_at: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    confirmed_at: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    completed_at: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    cancelled_at: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    deposit_required: Mapped[float] = mapped_column(Float, default=0)
    deposit_due_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    subtotal_amount: Mapped[float] = mapped_column(Float, default=0)
    discount_amount: Mapped[float] = mapped_column(Float, default=0)
    tax_amount: Mapped[float] = mapped_column(Float, default=0)
    total_amount: Mapped[float] = mapped_column(Float, default=0)
    deposit_paid: Mapped[float] = mapped_column(Float, default=0)
    balance_due: Mapped[float] = mapped_column(Float, default=0)
    receivable_id: Mapped[int | None] = mapped_column(ForeignKey('receivables.id'), nullable=True, index=True)
    record_id: Mapped[int | None] = mapped_column(ForeignKey('records.id'), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    receivable: Mapped["Receivable"] = relationship()
    record: Mapped["Record"] = relationship()
    lines: Mapped[list["EventBookingLine"]] = relationship(back_populates='event', cascade='all, delete-orphan')
    payments: Mapped[list["EventPayment"]] = relationship(back_populates='event', cascade='all, delete-orphan')


class EventBookingLine(Base):
    __tablename__ = 'event_booking_lines'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_booking_id: Mapped[int] = mapped_column(ForeignKey('event_bookings.id'), index=True)
    line_type: Mapped[str] = mapped_column(String(50), default='package', index=True)
    description: Mapped[str] = mapped_column(String(255), default='')
    quantity: Mapped[float] = mapped_column(Float, default=1)
    unit_price: Mapped[float] = mapped_column(Float, default=0)
    total_amount: Mapped[float] = mapped_column(Float, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    event: Mapped["EventBooking"] = relationship(back_populates='lines')


class EventPayment(Base, TimestampMixin):
    __tablename__ = 'event_payments'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_booking_id: Mapped[int] = mapped_column(ForeignKey('event_bookings.id'), index=True)
    payment_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    amount: Mapped[float] = mapped_column(Float, default=0)
    payment_method: Mapped[str | None] = mapped_column(String(120), nullable=True)
    financial_account_id: Mapped[int | None] = mapped_column(ForeignKey('financial_accounts.id'), nullable=True, index=True)
    reference_no: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    money_transaction_id: Mapped[int | None] = mapped_column(ForeignKey('money_transactions.id'), nullable=True, index=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    event: Mapped["EventBooking"] = relationship(back_populates='payments')
    financial_account: Mapped["FinancialAccount"] = relationship()
    money_transaction: Mapped["MoneyTransaction"] = relationship()


class Attachment(Base, TimestampMixin):
    __tablename__ = 'attachments'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    file_path: Mapped[str] = mapped_column(String(500))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

class Employee(Base, TimestampMixin):
    __tablename__ = 'employees'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), index=True)
    department: Mapped[str] = mapped_column(String(100), default='')
    job_title: Mapped[str] = mapped_column(String(100), default='')
    employment_profile: Mapped[str] = mapped_column(String(50), default='Regular')
    compensation_type: Mapped[str] = mapped_column(String(50), default='Monthly')
    rate: Mapped[float] = mapped_column(Float, default=0)
    daily_rate: Mapped[float] = mapped_column(Float, default=0)
    hourly_rate: Mapped[float] = mapped_column(Float, default=0)
    meal_allowance: Mapped[float] = mapped_column(Float, default=0)
    transport_allowance: Mapped[float] = mapped_column(Float, default=0)
    tin: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sss_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    philhealth_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pagibig_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    attendances: Mapped[list["AttendanceEntry"]] = relationship(back_populates='employee', cascade='all, delete-orphan')


class ExternalEmployeeReference(Base, TimestampMixin):
    __tablename__ = 'external_employee_references'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_source: Mapped[str] = mapped_column(String(80), index=True)
    source_staff_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    employee_code: Mapped[str] = mapped_column(String(120), index=True)
    display_name: Mapped[str] = mapped_column(String(255), default='')
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    position: Mapped[str | None] = mapped_column(String(120), nullable=True)
    role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    primary_department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    __table_args__ = (UniqueConstraint('external_source', 'employee_code', name='uq_external_employee_reference'),)


class IntegrationReceipt(Base, TimestampMixin):
    __tablename__ = 'integration_receipts'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_source: Mapped[str] = mapped_column(String(80), index=True)
    external_id: Mapped[str] = mapped_column(String(200), index=True)
    event_type: Mapped[str] = mapped_column(String(120), index=True)
    source_record_type: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    source_record_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    payload_json: Mapped[str] = mapped_column(Text, default='{}')
    status: Mapped[str] = mapped_column(String(40), default='For Review', index=True)
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    processed_at: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    created_review_record_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_review_record_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    posted_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    posted_at: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    __table_args__ = (UniqueConstraint('external_source', 'external_id', name='uq_integration_receipt_external_event'),)

class AttendanceEntry(Base, TimestampMixin):
    __tablename__ = 'attendance_entries'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey('employees.id'), index=True)
    work_date: Mapped[str] = mapped_column(String(50), index=True)
    time_in: Mapped[str | None] = mapped_column(String(20), nullable=True)
    time_out: Mapped[str | None] = mapped_column(String(20), nullable=True)
    late_minutes: Mapped[float] = mapped_column(Float, default=0)
    undertime_minutes: Mapped[float] = mapped_column(Float, default=0)
    overtime_hours: Mapped[float] = mapped_column(Float, default=0)
    night_diff_hours: Mapped[float] = mapped_column(Float, default=0)
    day_type: Mapped[str] = mapped_column(String(50), default='regular_day')
    is_absent: Mapped[bool] = mapped_column(Boolean, default=False)
    leave_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    employee: Mapped["Employee"] = relationship(back_populates='attendances')

class TaxonomyNode(Base, TimestampMixin):
    __tablename__ = 'taxonomy_nodes'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_slug: Mapped[str] = mapped_column(String(100), index=True)
    module_name: Mapped[str] = mapped_column(String(200), index=True)
    category: Mapped[str] = mapped_column(String(200), index=True)
    bucket: Mapped[str] = mapped_column(String(200), index=True)
    item: Mapped[str] = mapped_column(String(200), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class MasterValue(Base, TimestampMixin):
    __tablename__ = 'master_values'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_name: Mapped[str] = mapped_column(String(100), index=True)
    value: Mapped[str] = mapped_column(String(150), index=True)
    code: Mapped[str | None] = mapped_column(String(150), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# Legacy treasury tables are kept for backward data compatibility only.
# Active finance operations use cashflow models (financial_accounts, money_transactions, etc.).
class TreasuryAccount(Base, TimestampMixin):
    __tablename__ = 'treasury_accounts'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    account_type: Mapped[str] = mapped_column(String(20), index=True)  # drawer | bank
    opening_balance: Mapped[float] = mapped_column(Float, default=0)
    currency: Mapped[str] = mapped_column(String(10), default='PHP')
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class TreasuryMovement(Base, TimestampMixin):
    __tablename__ = 'treasury_movements'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    movement_no: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    movement_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    movement_type: Mapped[str] = mapped_column(String(20), index=True)  # in | out | transfer
    from_account_id: Mapped[int | None] = mapped_column(ForeignKey('treasury_accounts.id'), nullable=True, index=True)
    to_account_id: Mapped[int | None] = mapped_column(ForeignKey('treasury_accounts.id'), nullable=True, index=True)
    amount: Mapped[float] = mapped_column(Float, default=0)
    reference_no: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    counterparty: Mapped[str | None] = mapped_column(String(255), nullable=True)
    module_slug: Mapped[str | None] = mapped_column(String(100), nullable=True)
    linked_record_id: Mapped[int | None] = mapped_column(ForeignKey('records.id'), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    from_account: Mapped["TreasuryAccount"] = relationship(foreign_keys=[from_account_id])
    to_account: Mapped["TreasuryAccount"] = relationship(foreign_keys=[to_account_id])
    linked_record: Mapped["Record"] = relationship()


class TreasuryReconciliation(Base, TimestampMixin):
    __tablename__ = 'treasury_reconciliations'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey('treasury_accounts.id'), index=True)
    as_of_date: Mapped[str] = mapped_column(String(50), index=True)
    statement_balance: Mapped[float] = mapped_column(Float, default=0)
    system_balance: Mapped[float] = mapped_column(Float, default=0)
    variance: Mapped[float] = mapped_column(Float, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reconciled_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    account: Mapped["TreasuryAccount"] = relationship()
    __table_args__ = (UniqueConstraint('account_id', 'as_of_date', name='uq_treasury_recon_account_date'),)


class FinancialAccount(Base, TimestampMixin):
    __tablename__ = 'financial_accounts'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    account_type: Mapped[str] = mapped_column(String(30), index=True)  # cash_drawer | petty_cash | safe | bank | ewallet
    subtype: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    currency: Mapped[str] = mapped_column(String(10), default='PHP')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_daily_reconciliation: Mapped[bool] = mapped_column(Boolean, default=True)
    reconciliation_mode: Mapped[str] = mapped_column(String(30), default='daily', index=True)
    requires_physical_count: Mapped[bool] = mapped_column(Boolean, default=False)
    reconciliation_day_of_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reconciliation_day_of_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    variance_tolerance: Mapped[float] = mapped_column(Float, default=0)
    approval_required_on_variance: Mapped[bool] = mapped_column(Boolean, default=True)
    opening_balance: Mapped[float] = mapped_column(Float, default=0)
    current_balance: Mapped[float] = mapped_column(Float, default=0)
    department: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class MoneyTransaction(Base, TimestampMixin):
    __tablename__ = 'money_transactions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    direction: Mapped[str] = mapped_column(String(10), index=True)  # in | out
    financial_account_id: Mapped[int] = mapped_column(ForeignKey('financial_accounts.id'), index=True)
    module: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    category: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    subcategory: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    level3_item: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    amount: Mapped[float] = mapped_column(Float, default=0)
    payment_method: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reference_no: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    counterparty_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    linked_record_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    linked_record_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    receivable_id: Mapped[int | None] = mapped_column(ForeignKey('receivables.id'), nullable=True, index=True)
    payable_id: Mapped[int | None] = mapped_column(ForeignKey('payables.id'), nullable=True, index=True)
    bir_include: Mapped[bool] = mapped_column(Boolean, default=False)
    journal_entry_id: Mapped[int | None] = mapped_column(ForeignKey('journal_entries.id'), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default='posted', index=True)
    reversed_from_id: Mapped[int | None] = mapped_column(ForeignKey('money_transactions.id'), nullable=True, index=True)
    is_reversed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    posted_at: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    external_source: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    external_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    financial_account: Mapped["FinancialAccount"] = relationship()
    journal_entry: Mapped["JournalEntry"] = relationship()
    reversed_from: Mapped["MoneyTransaction"] = relationship(remote_side=[id])
    __table_args__ = (UniqueConstraint('external_source', 'external_id', name='uq_money_transactions_external_event'),)


class AccountTransfer(Base, TimestampMixin):
    __tablename__ = 'account_transfers'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transfer_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    from_account_id: Mapped[int] = mapped_column(ForeignKey('financial_accounts.id'), index=True)
    to_account_id: Mapped[int] = mapped_column(ForeignKey('financial_accounts.id'), index=True)
    amount: Mapped[float] = mapped_column(Float, default=0)
    reference_no: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    journal_entry_id: Mapped[int | None] = mapped_column(ForeignKey('journal_entries.id'), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default='posted', index=True)
    reversed_from_id: Mapped[int | None] = mapped_column(ForeignKey('account_transfers.id'), nullable=True, index=True)
    is_reversed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    posted_at: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    external_source: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    external_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    from_account: Mapped["FinancialAccount"] = relationship(foreign_keys=[from_account_id])
    to_account: Mapped["FinancialAccount"] = relationship(foreign_keys=[to_account_id])
    journal_entry: Mapped["JournalEntry"] = relationship()
    reversed_from: Mapped["AccountTransfer"] = relationship(remote_side=[id])
    __table_args__ = (UniqueConstraint('external_source', 'external_id', name='uq_account_transfers_external_event'),)


class CashReconciliation(Base, TimestampMixin):
    __tablename__ = 'cash_reconciliations'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    financial_account_id: Mapped[int] = mapped_column(ForeignKey('financial_accounts.id'), index=True)
    reconciliation_date: Mapped[str] = mapped_column(String(50), index=True)
    shift_name: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    opening_balance: Mapped[float] = mapped_column(Float, default=0)
    expected_in: Mapped[float] = mapped_column(Float, default=0)
    expected_out: Mapped[float] = mapped_column(Float, default=0)
    expected_closing: Mapped[float] = mapped_column(Float, default=0)
    actual_counted: Mapped[float] = mapped_column(Float, default=0)
    variance: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(50), default='counted', index=True)
    counted_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    posted_at: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    closed_at: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    locked_at: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    financial_account: Mapped["FinancialAccount"] = relationship()
    lines: Mapped[list["CashReconciliationLine"]] = relationship(back_populates='reconciliation', cascade='all, delete-orphan')
    __table_args__ = (UniqueConstraint('financial_account_id', 'reconciliation_date', 'shift_name', name='uq_cash_recon_account_date_shift'),)


class CashReconciliationLine(Base):
    __tablename__ = 'cash_reconciliation_lines'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cash_reconciliation_id: Mapped[int] = mapped_column(ForeignKey('cash_reconciliations.id'), index=True)
    line_label: Mapped[str] = mapped_column(String(120), default='')
    amount: Mapped[float] = mapped_column(Float, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    reconciliation: Mapped["CashReconciliation"] = relationship(back_populates='lines')


class Receivable(Base, TimestampMixin):
    __tablename__ = 'receivables'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    counterparty_name: Mapped[str] = mapped_column(String(255), default='', index=True)
    receivable_type: Mapped[str] = mapped_column(String(80), default='guest_balance', index=True)
    transaction_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    due_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    gross_amount: Mapped[float] = mapped_column(Float, default=0)
    amount_collected: Mapped[float] = mapped_column(Float, default=0)
    balance_due: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(50), default='open', index=True)
    posted_at: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    closed_at: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    bir_include: Mapped[bool] = mapped_column(Boolean, default=False)
    external_source: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    external_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    adjustments: Mapped[list["ReceivableAdjustment"]] = relationship(back_populates='receivable', cascade='all, delete-orphan')
    __table_args__ = (UniqueConstraint('external_source', 'external_id', name='uq_receivables_external_event'),)


class ReceivableAdjustment(Base, TimestampMixin):
    __tablename__ = 'receivable_adjustments'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receivable_id: Mapped[int] = mapped_column(ForeignKey('receivables.id'), index=True)
    adjustment_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    amount: Mapped[float] = mapped_column(Float, default=0)
    source_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    external_source: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    external_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    receivable: Mapped["Receivable"] = relationship(back_populates='adjustments')
    __table_args__ = (UniqueConstraint('external_source', 'external_id', name='uq_receivable_adjustments_external_event'),)


class Payable(Base, TimestampMixin):
    __tablename__ = 'payables'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    supplier_name: Mapped[str] = mapped_column(String(255), default='', index=True)
    payable_type: Mapped[str] = mapped_column(String(80), default='supplier_bill', index=True)
    bill_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    due_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    gross_amount: Mapped[float] = mapped_column(Float, default=0)
    amount_paid: Mapped[float] = mapped_column(Float, default=0)
    balance_due: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(50), default='open', index=True)
    posted_at: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    closed_at: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    bir_include: Mapped[bool] = mapped_column(Boolean, default=False)


class CashflowTemplate(Base, TimestampMixin):
    __tablename__ = 'cashflow_templates'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    direction: Mapped[str] = mapped_column(String(10), default='in', index=True)
    default_module: Mapped[str | None] = mapped_column(String(100), nullable=True)
    default_category: Mapped[str | None] = mapped_column(String(200), nullable=True)
    default_subcategory: Mapped[str | None] = mapped_column(String(200), nullable=True)
    default_level3_item: Mapped[str | None] = mapped_column(String(200), nullable=True)
    default_account_id: Mapped[int | None] = mapped_column(ForeignKey('financial_accounts.id'), nullable=True, index=True)
    default_payment_method: Mapped[str | None] = mapped_column(String(120), nullable=True)
    default_bir_include: Mapped[bool] = mapped_column(Boolean, default=False)
    default_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    default_account: Mapped["FinancialAccount"] = relationship()

class MenuItem(Base, TimestampMixin):
    __tablename__ = 'menu_items'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    module_slug: Mapped[str] = mapped_column(String(100), default='restaurant')
    category: Mapped[str] = mapped_column(String(100), default='')
    price: Mapped[float] = mapped_column(Float, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recipe_lines: Mapped[list["RecipeLine"]] = relationship(back_populates='menu_item', cascade='all, delete-orphan')
    skus: Mapped[list["MenuSKU"]] = relationship(back_populates='menu_item', cascade='all, delete-orphan')

class InventoryItem(Base, TimestampMixin):
    __tablename__ = 'inventory_items'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    module_name: Mapped[str] = mapped_column(String(100), default='Inventory')
    category_name: Mapped[str] = mapped_column(String(100), default='')
    subcategory_name: Mapped[str] = mapped_column(String(100), default='')
    unit: Mapped[str] = mapped_column(String(20), default='')
    quantity_on_hand: Mapped[float] = mapped_column(Float, default=0)
    reorder_level: Mapped[float] = mapped_column(Float, default=0)
    average_cost: Mapped[float] = mapped_column(Float, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    movements: Mapped[list['StockMovement']] = relationship(back_populates='item_obj', cascade='all, delete-orphan')
    batches: Mapped[list['InventoryBatch']] = relationship(back_populates='item_obj', cascade='all, delete-orphan')
    recipe_lines: Mapped[list["RecipeLine"]] = relationship(back_populates='inventory_item')

class InventoryBatch(Base, TimestampMixin):
    __tablename__ = 'inventory_batches'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey('inventory_items.id'), index=True)
    batch_code: Mapped[str] = mapped_column(String(100), index=True)
    received_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    reference_no: Mapped[str | None] = mapped_column(String(255), nullable=True)
    supplier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity_in: Mapped[float] = mapped_column(Float, default=0)
    quantity_remaining: Mapped[float] = mapped_column(Float, default=0)
    unit_cost: Mapped[float] = mapped_column(Float, default=0)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False)
    item_obj: Mapped["InventoryItem"] = relationship(back_populates='batches')
    allocations: Mapped[list["BatchAllocation"]] = relationship(back_populates='batch', cascade='all, delete-orphan')

class StockMovement(Base, TimestampMixin):
    __tablename__ = 'stock_movements'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey('inventory_items.id'), index=True)
    movement_type: Mapped[str] = mapped_column(String(30), index=True)  # in/out
    quantity: Mapped[float] = mapped_column(Float, default=0)
    unit_cost: Mapped[float] = mapped_column(Float, default=0)
    total_cost: Mapped[float] = mapped_column(Float, default=0)
    reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    module_slug: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reference_no: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    movement_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    receiving_record_id: Mapped[int | None] = mapped_column(ForeignKey('receiving_records.id'), nullable=True, index=True)
    item_obj: Mapped["InventoryItem"] = relationship(back_populates='movements')
    allocations: Mapped[list["BatchAllocation"]] = relationship(back_populates='movement', cascade='all, delete-orphan')

class BatchAllocation(Base):
    __tablename__ = 'batch_allocations'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey('inventory_batches.id'), index=True)
    stock_movement_id: Mapped[int] = mapped_column(ForeignKey('stock_movements.id'), index=True)
    quantity: Mapped[float] = mapped_column(Float, default=0)
    unit_cost: Mapped[float] = mapped_column(Float, default=0)
    total_cost: Mapped[float] = mapped_column(Float, default=0)
    batch: Mapped["InventoryBatch"] = relationship(back_populates='allocations')
    movement: Mapped["StockMovement"] = relationship(back_populates='allocations')

class RecipeLine(Base):
    __tablename__ = 'recipe_lines'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    menu_item_id: Mapped[int] = mapped_column(ForeignKey('menu_items.id'), index=True)
    inventory_item_id: Mapped[int] = mapped_column(ForeignKey('inventory_items.id'), index=True)
    quantity: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[str] = mapped_column(String(20), default='')
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    menu_item: Mapped["MenuItem"] = relationship(back_populates='recipe_lines')
    inventory_item: Mapped["InventoryItem"] = relationship(back_populates='recipe_lines')


class PrepComponent(Base, TimestampMixin):
    __tablename__ = 'prep_components'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    category_name: Mapped[str] = mapped_column(String(120), default='')
    yield_quantity: Mapped[float] = mapped_column(Float, default=1)
    yield_unit: Mapped[str] = mapped_column(String(20), default='')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    items: Mapped[list["PrepComponentItem"]] = relationship(back_populates='component', cascade='all, delete-orphan')


class PrepComponentItem(Base):
    __tablename__ = 'prep_component_items'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    component_id: Mapped[int] = mapped_column(ForeignKey('prep_components.id'), index=True)
    inventory_item_id: Mapped[int] = mapped_column(ForeignKey('inventory_items.id'), index=True)
    quantity: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[str] = mapped_column(String(20), default='')
    wastage_percent: Mapped[float] = mapped_column(Float, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    component: Mapped["PrepComponent"] = relationship(back_populates='items')
    inventory_item: Mapped["InventoryItem"] = relationship()


class MenuSKU(Base, TimestampMixin):
    __tablename__ = 'menu_skus'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    menu_item_id: Mapped[int] = mapped_column(ForeignKey('menu_items.id'), index=True)
    sku_code: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True, index=True)
    variant_name: Mapped[str] = mapped_column(String(255), default='')
    size_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    price: Mapped[float] = mapped_column(Float, default=0)
    packaging_cost: Mapped[float] = mapped_column(Float, default=0)
    labor_cost: Mapped[float] = mapped_column(Float, default=0)
    overhead_cost: Mapped[float] = mapped_column(Float, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    menu_item: Mapped["MenuItem"] = relationship(back_populates='skus')
    recipe_items: Mapped[list["MenuSKURecipeItem"]] = relationship(back_populates='sku', cascade='all, delete-orphan')


class MenuSKURecipeItem(Base):
    __tablename__ = 'menu_sku_recipe_items'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey('menu_skus.id'), index=True)
    line_type: Mapped[str] = mapped_column(String(20), default='inventory')  # inventory | component
    inventory_item_id: Mapped[int | None] = mapped_column(ForeignKey('inventory_items.id'), nullable=True, index=True)
    component_id: Mapped[int | None] = mapped_column(ForeignKey('prep_components.id'), nullable=True, index=True)
    quantity: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[str] = mapped_column(String(20), default='')
    wastage_percent: Mapped[float] = mapped_column(Float, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sku: Mapped["MenuSKU"] = relationship(back_populates='recipe_items')
    inventory_item: Mapped["InventoryItem"] = relationship()
    component: Mapped["PrepComponent"] = relationship()


class MenuPromotion(Base, TimestampMixin):
    __tablename__ = 'menu_promotions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    applies_to: Mapped[str] = mapped_column(String(20), default='sku')  # sku | menu_item
    sku_id: Mapped[int | None] = mapped_column(ForeignKey('menu_skus.id'), nullable=True, index=True)
    menu_item_id: Mapped[int | None] = mapped_column(ForeignKey('menu_items.id'), nullable=True, index=True)
    promo_type: Mapped[str] = mapped_column(String(30), default='percent_off')  # percent_off | fixed_discount | set_price
    promo_value: Mapped[float] = mapped_column(Float, default=0)
    min_qty: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sku: Mapped["MenuSKU"] = relationship()
    menu_item: Mapped["MenuItem"] = relationship()


class SaleOrder(Base, TimestampMixin):
    __tablename__ = 'sale_orders'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_no: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    order_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default='posted')
    payment_method: Mapped[str | None] = mapped_column(String(120), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(120), nullable=True)
    counterparty: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gross_amount: Mapped[float] = mapped_column(Float, default=0)
    discount_amount: Mapped[float] = mapped_column(Float, default=0)
    net_amount: Mapped[float] = mapped_column(Float, default=0)
    cogs_amount: Mapped[float] = mapped_column(Float, default=0)
    income_record_id: Mapped[int | None] = mapped_column(ForeignKey('records.id'), nullable=True)
    cogs_record_id: Mapped[int | None] = mapped_column(ForeignKey('records.id'), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_source: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    external_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    lines: Mapped[list["SaleOrderLine"]] = relationship(back_populates='order', cascade='all, delete-orphan')
    void_events: Mapped[list["SaleVoidEvent"]] = relationship(back_populates='sale_order', cascade='all, delete-orphan')
    __table_args__ = (UniqueConstraint('external_source', 'external_id', name='uq_sale_orders_external_event'),)


class SaleOrderLine(Base):
    __tablename__ = 'sale_order_lines'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sale_order_id: Mapped[int] = mapped_column(ForeignKey('sale_orders.id'), index=True)
    menu_item_id: Mapped[int | None] = mapped_column(ForeignKey('menu_items.id'), nullable=True, index=True)
    sku_id: Mapped[int | None] = mapped_column(ForeignKey('menu_skus.id'), nullable=True, index=True)
    item_name: Mapped[str] = mapped_column(String(255), default='')
    quantity: Mapped[float] = mapped_column(Float, default=0)
    unit_price: Mapped[float] = mapped_column(Float, default=0)
    discount_amount: Mapped[float] = mapped_column(Float, default=0)
    line_total: Mapped[float] = mapped_column(Float, default=0)
    order: Mapped["SaleOrder"] = relationship(back_populates='lines')
    menu_item: Mapped["MenuItem"] = relationship()
    sku: Mapped["MenuSKU"] = relationship()


class StockMovementAccountingLink(Base):
    __tablename__ = 'stock_movement_accounting_links'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_movement_id: Mapped[int] = mapped_column(ForeignKey('stock_movements.id'), index=True)
    record_id: Mapped[int] = mapped_column(ForeignKey('records.id'), index=True)
    link_type: Mapped[str] = mapped_column(String(30), default='expense')
    stock_movement: Mapped["StockMovement"] = relationship()
    record: Mapped["Record"] = relationship()
    __table_args__ = (UniqueConstraint('stock_movement_id', 'record_id', 'link_type', name='uq_stock_record_link'),)


class SaleAccountingLink(Base):
    __tablename__ = 'sale_accounting_links'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sale_order_id: Mapped[int] = mapped_column(ForeignKey('sale_orders.id'), index=True)
    record_id: Mapped[int] = mapped_column(ForeignKey('records.id'), index=True)
    link_type: Mapped[str] = mapped_column(String(30), default='income')  # income | cogs
    sale_order: Mapped["SaleOrder"] = relationship()
    record: Mapped["Record"] = relationship()
    __table_args__ = (UniqueConstraint('sale_order_id', 'record_id', 'link_type', name='uq_sale_record_link'),)


class SaleVoidEvent(Base, TimestampMixin):
    __tablename__ = 'sale_void_events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sale_order_id: Mapped[int] = mapped_column(ForeignKey('sale_orders.id'), index=True)
    void_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    reason: Mapped[str] = mapped_column(Text, default='')
    reverse_inventory: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_post_accounting: Mapped[bool] = mapped_column(Boolean, default=False)
    income_reversal_record_id: Mapped[int | None] = mapped_column(ForeignKey('records.id'), nullable=True)
    cogs_reversal_record_id: Mapped[int | None] = mapped_column(ForeignKey('records.id'), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sale_order: Mapped["SaleOrder"] = relationship(back_populates='void_events')
    income_reversal_record: Mapped["Record"] = relationship(foreign_keys=[income_reversal_record_id])
    cogs_reversal_record: Mapped["Record"] = relationship(foreign_keys=[cogs_reversal_record_id])
    __table_args__ = (UniqueConstraint('sale_order_id', name='uq_sale_void_event_sale'),)

class Asset(Base, TimestampMixin):
    __tablename__ = 'assets'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    asset_class: Mapped[str] = mapped_column(String(100), default='')
    location: Mapped[str | None] = mapped_column(String(100), nullable=True)
    acquisition_cost: Mapped[float] = mapped_column(Float, default=0)
    useful_life_months: Mapped[int] = mapped_column(Integer, default=60)
    salvage_value: Mapped[float] = mapped_column(Float, default=0)
    condition_status: Mapped[str] = mapped_column(String(50), default='Good')
    operational_status: Mapped[str] = mapped_column(String(50), default='Active')
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class RoomType(Base, TimestampMixin):
    __tablename__ = 'room_types'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_capacity: Mapped[int] = mapped_column(Integer, default=2)
    max_capacity: Mapped[int] = mapped_column(Integer, default=2)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Room(Base, TimestampMixin):
    __tablename__ = 'rooms'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_no: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(150), index=True)
    room_type_id: Mapped[int | None] = mapped_column(ForeignKey('room_types.id'), nullable=True, index=True)
    floor_zone: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    view_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default='available', index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    room_type: Mapped["RoomType"] = relationship()


class RatePlan(Base, TimestampMixin):
    __tablename__ = 'rate_plans'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(150), index=True)
    room_type_id: Mapped[int | None] = mapped_column(ForeignKey('room_types.id'), nullable=True, index=True)
    base_rate: Mapped[float] = mapped_column(Float, default=0)
    breakfast_included: Mapped[int] = mapped_column(Integer, default=0)
    pax_included: Mapped[int] = mapped_column(Integer, default=2)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    room_type: Mapped["RoomType"] = relationship()


class BookingChannel(Base, TimestampMixin):
    __tablename__ = 'booking_channels'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    channel_class: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    settlement_mode: Mapped[str | None] = mapped_column(String(80), nullable=True)
    default_commission_rate: Mapped[float] = mapped_column(Float, default=0)
    is_prepaid: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class RoomPackageRule(Base, TimestampMixin):
    __tablename__ = 'room_package_rules'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    room_type_id: Mapped[int | None] = mapped_column(ForeignKey('room_types.id'), nullable=True, index=True)
    rate_plan_id: Mapped[int | None] = mapped_column(ForeignKey('rate_plans.id'), nullable=True, index=True)
    included_breakfast: Mapped[int] = mapped_column(Integer, default=0)
    included_pax: Mapped[int] = mapped_column(Integer, default=2)
    extra_pax_rate: Mapped[float] = mapped_column(Float, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    room_type: Mapped["RoomType"] = relationship()
    rate_plan: Mapped["RatePlan"] = relationship()


class Guest(Base, TimestampMixin):
    __tablename__ = 'guests'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    last_name: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(80), nullable=True)
    birthday: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    company: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    vip_flag: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status_tags: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    tags: Mapped[list["GuestTag"]] = relationship(back_populates='guest', cascade='all, delete-orphan')
    preferences: Mapped[list["GuestPreference"]] = relationship(back_populates='guest', cascade='all, delete-orphan')


class GuestTag(Base, TimestampMixin):
    __tablename__ = 'guest_tags'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guest_id: Mapped[int] = mapped_column(ForeignKey('guests.id'), index=True)
    tag: Mapped[str] = mapped_column(String(120), index=True)
    guest: Mapped["Guest"] = relationship(back_populates='tags')
    __table_args__ = (UniqueConstraint('guest_id', 'tag', name='uq_guest_tag'),)


class GuestPreference(Base, TimestampMixin):
    __tablename__ = 'guest_preferences'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guest_id: Mapped[int] = mapped_column(ForeignKey('guests.id'), index=True)
    preference_key: Mapped[str] = mapped_column(String(120), index=True)
    preference_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    guest: Mapped["Guest"] = relationship(back_populates='preferences')


class GuestMergeHistory(Base, TimestampMixin):
    __tablename__ = 'guest_merge_history'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_guest_id: Mapped[int] = mapped_column(ForeignKey('guests.id'), index=True)
    target_guest_id: Mapped[int] = mapped_column(ForeignKey('guests.id'), index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    merged_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_guest: Mapped["Guest"] = relationship(foreign_keys=[source_guest_id])
    target_guest: Mapped["Guest"] = relationship(foreign_keys=[target_guest_id])


class Booking(Base, TimestampMixin):
    __tablename__ = 'bookings'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guest_id: Mapped[int | None] = mapped_column(ForeignKey('guests.id'), nullable=True, index=True)
    guest_name: Mapped[str] = mapped_column(String(255), index=True)
    room_id: Mapped[int | None] = mapped_column(ForeignKey('rooms.id'), nullable=True, index=True)
    room_type_id: Mapped[int | None] = mapped_column(ForeignKey('room_types.id'), nullable=True, index=True)
    rate_plan_id: Mapped[int | None] = mapped_column(ForeignKey('rate_plans.id'), nullable=True, index=True)
    channel_id: Mapped[int | None] = mapped_column(ForeignKey('booking_channels.id'), nullable=True, index=True)
    room_name: Mapped[str] = mapped_column(String(100), default='')
    room_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    channel: Mapped[str] = mapped_column(String(100), default='Walk-in')
    external_source: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    external_booking_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default='confirmed')
    check_in: Mapped[str | None] = mapped_column(String(50), nullable=True)
    check_out: Mapped[str | None] = mapped_column(String(50), nullable=True)
    gross_amount: Mapped[float] = mapped_column(Float, default=0)
    deposit_amount: Mapped[float] = mapped_column(Float, default=0)
    breakfast_included: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    guest: Mapped["Guest"] = relationship()
    room: Mapped["Room"] = relationship()
    room_type_obj: Mapped["RoomType"] = relationship(foreign_keys=[room_type_id])
    rate_plan: Mapped["RatePlan"] = relationship()
    channel_obj: Mapped["BookingChannel"] = relationship(foreign_keys=[channel_id])
    accounting_links: Mapped[list["BookingAccountingLink"]] = relationship(back_populates='booking', cascade='all, delete-orphan')
    breakfast_logs: Mapped[list["RoomBreakfastLog"]] = relationship(back_populates='booking', cascade='all, delete-orphan')
    folios: Mapped[list["BookingFolio"]] = relationship(back_populates='booking', cascade='all, delete-orphan')


class BookingAccountingLink(Base):
    __tablename__ = 'booking_accounting_links'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey('bookings.id'), index=True)
    record_id: Mapped[int] = mapped_column(ForeignKey('records.id'), index=True)
    link_type: Mapped[str] = mapped_column(String(40), default='room_income')
    booking: Mapped["Booking"] = relationship(back_populates='accounting_links')
    record: Mapped["Record"] = relationship()
    __table_args__ = (UniqueConstraint('booking_id', 'record_id', 'link_type', name='uq_booking_record_link'),)


class BookingFolio(Base, TimestampMixin):
    __tablename__ = 'booking_folios'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey('bookings.id'), index=True)
    guest_id: Mapped[int | None] = mapped_column(ForeignKey('guests.id'), nullable=True, index=True)
    folio_no: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default='open', index=True)
    opened_at: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    closed_at: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    booking: Mapped["Booking"] = relationship(back_populates='folios')
    guest: Mapped["Guest"] = relationship()
    lines: Mapped[list["BookingFolioLine"]] = relationship(back_populates='folio', cascade='all, delete-orphan')


class BookingFolioLine(Base, TimestampMixin):
    __tablename__ = 'booking_folio_lines'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    folio_id: Mapped[int] = mapped_column(ForeignKey('booking_folios.id'), index=True)
    line_type: Mapped[str] = mapped_column(String(80), default='manual_charge', index=True)
    description: Mapped[str] = mapped_column(String(255), default='')
    quantity: Mapped[float] = mapped_column(Float, default=1)
    unit_price: Mapped[float] = mapped_column(Float, default=0)
    amount: Mapped[float] = mapped_column(Float, default=0)
    transaction_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    reference_no: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    linked_money_transaction_id: Mapped[int | None] = mapped_column(ForeignKey('money_transactions.id'), nullable=True, index=True)
    linked_receivable_id: Mapped[int | None] = mapped_column(ForeignKey('receivables.id'), nullable=True, index=True)
    linked_payable_id: Mapped[int | None] = mapped_column(ForeignKey('payables.id'), nullable=True, index=True)
    linked_record_id: Mapped[int | None] = mapped_column(ForeignKey('records.id'), nullable=True, index=True)
    external_source: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    external_line_key: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    folio: Mapped["BookingFolio"] = relationship(back_populates='lines')
    linked_money_transaction: Mapped["MoneyTransaction"] = relationship()
    linked_receivable: Mapped["Receivable"] = relationship()
    linked_payable: Mapped["Payable"] = relationship()
    linked_record: Mapped["Record"] = relationship()


class Beds24BookingMap(Base, TimestampMixin):
    __tablename__ = 'beds24_booking_maps'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    beds24_booking_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    local_booking_id: Mapped[int | None] = mapped_column(ForeignKey('bookings.id'), nullable=True, index=True)
    local_guest_id: Mapped[int | None] = mapped_column(ForeignKey('guests.id'), nullable=True, index=True)
    beds24_property_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    beds24_room_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    beds24_room_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    beds24_unit_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    beds24_unit_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    beds24_channel_source: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    beds24_group_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    beds24_status: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    beds24_check_in: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    beds24_check_out: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    beds24_last_night: Mapped[str | None] = mapped_column(String(50), nullable=True)
    beds24_booking_time: Mapped[str | None] = mapped_column(String(50), nullable=True)
    beds24_num_adult: Mapped[int | None] = mapped_column(Integer, nullable=True)
    beds24_num_child: Mapped[int | None] = mapped_column(Integer, nullable=True)
    beds24_reference: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    beds24_original_ota: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    beds24_referer: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    beds24_original_referer: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    beds24_offer_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    beds24_voucher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    beds24_rate_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    beds24_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    beds24_tax: Mapped[float | None] = mapped_column(Float, nullable=True)
    beds24_deposit: Mapped[float | None] = mapped_column(Float, nullable=True)
    beds24_commission: Mapped[float | None] = mapped_column(Float, nullable=True)
    beds24_total_charges: Mapped[float | None] = mapped_column(Float, nullable=True)
    beds24_total_payments: Mapped[float | None] = mapped_column(Float, nullable=True)
    beds24_total_balance: Mapped[float | None] = mapped_column(Float, nullable=True)
    sync_status: Mapped[str] = mapped_column(String(50), default='pending', index=True)
    last_synced_at: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    local_booking: Mapped["Booking"] = relationship()
    local_guest: Mapped["Guest"] = relationship()


class Beds24GuestMap(Base, TimestampMixin):
    __tablename__ = 'beds24_guest_maps'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    beds24_guest_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    local_guest_id: Mapped[int] = mapped_column(ForeignKey('guests.id'), index=True)
    matching_strategy: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    last_synced_at: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    local_guest: Mapped["Guest"] = relationship()


class Beds24SyncLog(Base, TimestampMixin):
    __tablename__ = 'beds24_sync_logs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    source_type: Mapped[str] = mapped_column(String(30), default='manual', index=True)
    beds24_booking_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    local_booking_id: Mapped[int | None] = mapped_column(ForeignKey('bookings.id'), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default='info', index=True)
    message: Mapped[str] = mapped_column(Text, default='')
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    local_booking: Mapped["Booking"] = relationship()


class RoomBreakfastLog(Base, TimestampMixin):
    __tablename__ = 'room_breakfast_logs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    breakfast_no: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    booking_id: Mapped[int | None] = mapped_column(ForeignKey('bookings.id'), nullable=True, index=True)
    meal_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    guest_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    menu_item_id: Mapped[int | None] = mapped_column(ForeignKey('menu_items.id'), nullable=True, index=True)
    sku_id: Mapped[int | None] = mapped_column(ForeignKey('menu_skus.id'), nullable=True, index=True)
    quantity: Mapped[float] = mapped_column(Float, default=0)
    charged_amount: Mapped[float] = mapped_column(Float, default=0)
    charge_to_room: Mapped[bool] = mapped_column(Boolean, default=True)
    cogs_amount: Mapped[float] = mapped_column(Float, default=0)
    income_record_id: Mapped[int | None] = mapped_column(ForeignKey('records.id'), nullable=True)
    cogs_record_id: Mapped[int | None] = mapped_column(ForeignKey('records.id'), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    booking: Mapped["Booking"] = relationship(back_populates='breakfast_logs')
    menu_item: Mapped["MenuItem"] = relationship()
    sku: Mapped["MenuSKU"] = relationship()


class StaffMealLog(Base, TimestampMixin):
    __tablename__ = 'staff_meal_logs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meal_no: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    meal_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    dish_name: Mapped[str] = mapped_column(String(255), default='')
    menu_item_id: Mapped[int | None] = mapped_column(ForeignKey('menu_items.id'), nullable=True, index=True)
    sku_id: Mapped[int | None] = mapped_column(ForeignKey('menu_skus.id'), nullable=True, index=True)
    quantity: Mapped[float] = mapped_column(Float, default=0)
    served_to: Mapped[str | None] = mapped_column(String(120), nullable=True)
    cogs_amount: Mapped[float] = mapped_column(Float, default=0)
    expense_record_id: Mapped[int | None] = mapped_column(ForeignKey('records.id'), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    menu_item: Mapped["MenuItem"] = relationship()
    sku: Mapped["MenuSKU"] = relationship()
    lines: Mapped[list["StaffMealIngredient"]] = relationship(back_populates='log', cascade='all, delete-orphan')


class StaffMealIngredient(Base):
    __tablename__ = 'staff_meal_ingredients'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    staff_meal_log_id: Mapped[int] = mapped_column(ForeignKey('staff_meal_logs.id'), index=True)
    inventory_item_id: Mapped[int] = mapped_column(ForeignKey('inventory_items.id'), index=True)
    quantity: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[str] = mapped_column(String(20), default='')
    source: Mapped[str] = mapped_column(String(20), default='manual')
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    log: Mapped["StaffMealLog"] = relationship(back_populates='lines')
    inventory_item: Mapped["InventoryItem"] = relationship()

class ChannelPayout(Base, TimestampMixin):
    __tablename__ = 'channel_payouts'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int | None] = mapped_column(ForeignKey('booking_channels.id'), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(100), index=True)
    booking_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gross_amount: Mapped[float] = mapped_column(Float, default=0)
    commission_amount: Mapped[float] = mapped_column(Float, default=0)
    net_amount: Mapped[float] = mapped_column(Float, default=0)
    expected_payout_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    actual_payout_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default='pending')
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel_obj: Mapped["BookingChannel"] = relationship(foreign_keys=[channel_id])
    accounting_links: Mapped[list["ChannelPayoutAccountingLink"]] = relationship(back_populates='payout', cascade='all, delete-orphan')


class ChannelPayoutAccountingLink(Base):
    __tablename__ = 'channel_payout_accounting_links'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payout_id: Mapped[int] = mapped_column(ForeignKey('channel_payouts.id'), index=True)
    record_id: Mapped[int] = mapped_column(ForeignKey('records.id'), index=True)
    link_type: Mapped[str] = mapped_column(String(40), default='commission_expense')  # commission_expense | payout_settlement
    payout: Mapped["ChannelPayout"] = relationship(back_populates='accounting_links')
    record: Mapped["Record"] = relationship()
    __table_args__ = (UniqueConstraint('payout_id', 'record_id', 'link_type', name='uq_channel_payout_record_link'),)


class Supplier(Base, TimestampMixin):
    __tablename__ = 'suppliers'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    supplier_type: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    contact_person: Mapped[str | None] = mapped_column(String(150), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    tin: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    tax_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    payment_terms: Mapped[str | None] = mapped_column(String(80), nullable=True)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class PurchaseRequest(Base, TimestampMixin):
    __tablename__ = 'purchase_requests'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_no: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    request_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    needed_by_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    department: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey('suppliers.id'), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default='draft', index=True)
    requested_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    supplier: Mapped["Supplier"] = relationship()
    lines: Mapped[list["PurchaseRequestLine"]] = relationship(back_populates='purchase_request', cascade='all, delete-orphan')


class PurchaseRequestLine(Base):
    __tablename__ = 'purchase_request_lines'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_request_id: Mapped[int] = mapped_column(ForeignKey('purchase_requests.id'), index=True)
    inventory_item_id: Mapped[int | None] = mapped_column(ForeignKey('inventory_items.id'), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    estimated_unit_cost: Mapped[float] = mapped_column(Float, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    purchase_request: Mapped["PurchaseRequest"] = relationship(back_populates='lines')
    inventory_item: Mapped["InventoryItem"] = relationship()


class PurchaseOrder(Base, TimestampMixin):
    __tablename__ = 'purchase_orders'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    po_no: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    po_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey('suppliers.id'), nullable=True, index=True)
    purchase_request_id: Mapped[int | None] = mapped_column(ForeignKey('purchase_requests.id'), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default='draft', index=True)
    payment_terms: Mapped[str | None] = mapped_column(String(80), nullable=True)
    expected_delivery_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    total_amount: Mapped[float] = mapped_column(Float, default=0)
    issued_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    supplier: Mapped["Supplier"] = relationship()
    purchase_request: Mapped["PurchaseRequest"] = relationship()
    lines: Mapped[list["PurchaseOrderLine"]] = relationship(back_populates='purchase_order', cascade='all, delete-orphan')


class PurchaseOrderLine(Base):
    __tablename__ = 'purchase_order_lines'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey('purchase_orders.id'), index=True)
    purchase_request_line_id: Mapped[int | None] = mapped_column(ForeignKey('purchase_request_lines.id'), nullable=True, index=True)
    inventory_item_id: Mapped[int | None] = mapped_column(ForeignKey('inventory_items.id'), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity_ordered: Mapped[float] = mapped_column(Float, default=0)
    quantity_received: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    unit_cost: Mapped[float] = mapped_column(Float, default=0)
    line_total: Mapped[float] = mapped_column(Float, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates='lines')
    purchase_request_line: Mapped["PurchaseRequestLine"] = relationship()
    inventory_item: Mapped["InventoryItem"] = relationship()


class ReceivingRecord(Base, TimestampMixin):
    __tablename__ = 'receiving_records'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receiving_no: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    receiving_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey('suppliers.id'), nullable=True, index=True)
    purchase_order_id: Mapped[int | None] = mapped_column(ForeignKey('purchase_orders.id'), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default='draft', index=True)
    reference_no: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_amount: Mapped[float] = mapped_column(Float, default=0)
    received_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    posted_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    supplier: Mapped["Supplier"] = relationship()
    purchase_order: Mapped["PurchaseOrder"] = relationship()
    lines: Mapped[list["ReceivingLine"]] = relationship(back_populates='receiving_record', cascade='all, delete-orphan')


class ReceivingLine(Base):
    __tablename__ = 'receiving_lines'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receiving_record_id: Mapped[int] = mapped_column(ForeignKey('receiving_records.id'), index=True)
    purchase_order_line_id: Mapped[int | None] = mapped_column(ForeignKey('purchase_order_lines.id'), nullable=True, index=True)
    inventory_item_id: Mapped[int | None] = mapped_column(ForeignKey('inventory_items.id'), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity_received: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    unit_cost: Mapped[float] = mapped_column(Float, default=0)
    line_total: Mapped[float] = mapped_column(Float, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    receiving_record: Mapped["ReceivingRecord"] = relationship(back_populates='lines')
    purchase_order_line: Mapped["PurchaseOrderLine"] = relationship()
    inventory_item: Mapped["InventoryItem"] = relationship()

class PayrollRun(Base, TimestampMixin):
    __tablename__ = 'payroll_runs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    period_start: Mapped[str | None] = mapped_column(String(50), nullable=True)
    period_end: Mapped[str | None] = mapped_column(String(50), nullable=True)
    release_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default='draft')
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_journal_entry_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lines: Mapped[list['PayrollLine']] = relationship(back_populates='run', cascade='all, delete-orphan')


class PayrollPeriod(Base, TimestampMixin):
    __tablename__ = 'payroll_periods'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    period_start: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    period_end: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    release_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default='draft', index=True)
    source_type: Mapped[str] = mapped_column(String(50), default='manual')
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_journal_entry_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lines: Mapped[list["PayrollPeriodLine"]] = relationship(back_populates='period', cascade='all, delete-orphan')
    imports: Mapped[list["PayrollImportBatch"]] = relationship(back_populates='period', cascade='all, delete-orphan')


class PayrollPeriodLine(Base):
    __tablename__ = 'payroll_period_lines'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payroll_period_id: Mapped[int] = mapped_column(ForeignKey('payroll_periods.id'), index=True)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey('employees.id'), nullable=True)
    employee_name: Mapped[str] = mapped_column(String(255))
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    regular_hours: Mapped[float] = mapped_column(Float, default=0)
    overtime_hours: Mapped[float] = mapped_column(Float, default=0)
    regular_holiday_hours: Mapped[float] = mapped_column(Float, default=0)
    special_holiday_hours: Mapped[float] = mapped_column(Float, default=0)
    night_diff_hours: Mapped[float] = mapped_column(Float, default=0)
    regular_amount: Mapped[float] = mapped_column(Float, default=0)
    overtime_amount: Mapped[float] = mapped_column(Float, default=0)
    holiday_amount: Mapped[float] = mapped_column(Float, default=0)
    night_diff_amount: Mapped[float] = mapped_column(Float, default=0)
    allowances: Mapped[float] = mapped_column(Float, default=0)
    deductions: Mapped[float] = mapped_column(Float, default=0)
    employer_contribution: Mapped[float] = mapped_column(Float, default=0)
    gross_pay: Mapped[float] = mapped_column(Float, default=0)
    net_pay: Mapped[float] = mapped_column(Float, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    period: Mapped["PayrollPeriod"] = relationship(back_populates='lines')


class PayrollImportBatch(Base, TimestampMixin):
    __tablename__ = 'payroll_import_batches'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payroll_period_id: Mapped[int | None] = mapped_column(ForeignKey('payroll_periods.id'), nullable=True, index=True)
    file_name: Mapped[str] = mapped_column(String(255), default='')
    imported_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default='draft')
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    period: Mapped["PayrollPeriod"] = relationship(back_populates='imports')


class PayrollLine(Base):
    __tablename__ = 'payroll_lines'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payroll_run_id: Mapped[int] = mapped_column(ForeignKey('payroll_runs.id'), index=True)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey('employees.id'), nullable=True)
    employee_name: Mapped[str] = mapped_column(String(255))
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hours_worked: Mapped[float] = mapped_column(Float, default=0)
    basic_pay: Mapped[float] = mapped_column(Float, default=0)
    overtime_pay: Mapped[float] = mapped_column(Float, default=0)
    night_diff_pay: Mapped[float] = mapped_column(Float, default=0)
    holiday_pay: Mapped[float] = mapped_column(Float, default=0)
    allowances: Mapped[float] = mapped_column(Float, default=0)
    gross_pay: Mapped[float] = mapped_column(Float, default=0)
    sss_employee: Mapped[float] = mapped_column(Float, default=0)
    philhealth_employee: Mapped[float] = mapped_column(Float, default=0)
    pagibig_employee: Mapped[float] = mapped_column(Float, default=0)
    other_deductions: Mapped[float] = mapped_column(Float, default=0)
    total_deductions: Mapped[float] = mapped_column(Float, default=0)
    net_pay: Mapped[float] = mapped_column(Float, default=0)
    sss_employer: Mapped[float] = mapped_column(Float, default=0)
    philhealth_employer: Mapped[float] = mapped_column(Float, default=0)
    pagibig_employer: Mapped[float] = mapped_column(Float, default=0)
    run: Mapped['PayrollRun'] = relationship(back_populates='lines')

class JournalEntry(Base, TimestampMixin):
    __tablename__ = 'journal_entries'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entry_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    reference_no: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_module: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default='draft')
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    lines: Mapped[list['JournalLine']] = relationship(back_populates='entry', cascade='all, delete-orphan')

class JournalLine(Base):
    __tablename__ = 'journal_lines'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    journal_entry_id: Mapped[int] = mapped_column(ForeignKey('journal_entries.id'), index=True)
    account_code: Mapped[str] = mapped_column(String(50))
    account_name: Mapped[str] = mapped_column(String(255))
    debit: Mapped[float] = mapped_column(Float, default=0)
    credit: Mapped[float] = mapped_column(Float, default=0)
    memo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    entry: Mapped['JournalEntry'] = relationship(back_populates='lines')


class ChartAccount(Base, TimestampMixin):
    __tablename__ = 'chart_accounts'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    account_type: Mapped[str] = mapped_column(String(50), index=True)
    subtype: Mapped[str | None] = mapped_column(String(80), nullable=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey('chart_accounts.id'), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent: Mapped["ChartAccount"] = relationship(remote_side=[id], backref='children')


class AccountMappingRule(Base, TimestampMixin):
    __tablename__ = 'account_mapping_rules'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_slug: Mapped[str] = mapped_column(String(100), index=True)
    category: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    bucket: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    item: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    direction: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    payment_method: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    debit_account_code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    credit_account_code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

class BIRBookEntry(Base, TimestampMixin):
    __tablename__ = 'bir_book_entries'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_type: Mapped[str] = mapped_column(String(100), index=True)
    period_key: Mapped[str] = mapped_column(String(20), index=True)
    source_type: Mapped[str] = mapped_column(String(100), default='')
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entry_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_no: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[float] = mapped_column(Float, default=0)
    tax_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)


class BIRSelectionEntry(Base, TimestampMixin):
    __tablename__ = 'bir_selection_entries'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period_key: Mapped[str] = mapped_column(String(20), index=True)
    source_type: Mapped[str] = mapped_column(String(40), index=True)  # record | journal_entry
    source_id: Mapped[int] = mapped_column(Integer, index=True)
    include_in_bir: Mapped[bool] = mapped_column(Boolean, default=True)
    book_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tax_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    __table_args__ = (UniqueConstraint('period_key', 'source_type', 'source_id', name='uq_bir_selection_entry'),)

class PeriodLock(Base, TimestampMixin):
    __tablename__ = 'period_locks'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period_key: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    scope: Mapped[str] = mapped_column(String(50), default='bir')
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    locked_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class AssetDepreciationLog(Base, TimestampMixin):
    __tablename__ = 'asset_depreciation_logs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey('assets.id'), index=True)
    period_key: Mapped[str] = mapped_column(String(20), index=True)
    depreciation_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    amount: Mapped[float] = mapped_column(Float, default=0)
    record_id: Mapped[int | None] = mapped_column(ForeignKey('records.id'), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    asset: Mapped["Asset"] = relationship()
    record: Mapped["Record"] = relationship()
    __table_args__ = (UniqueConstraint('asset_id', 'period_key', name='uq_asset_depreciation_period'),)


class AssetMaintenanceLog(Base, TimestampMixin):
    __tablename__ = 'asset_maintenance_logs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey('assets.id'), index=True)
    service_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    vendor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[float] = mapped_column(Float, default=0)
    record_id: Mapped[int | None] = mapped_column(ForeignKey('records.id'), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    asset: Mapped["Asset"] = relationship()
    record: Mapped["Record"] = relationship()


class AssetDisposalLog(Base, TimestampMixin):
    __tablename__ = 'asset_disposal_logs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey('assets.id'), index=True)
    disposal_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    proceeds_amount: Mapped[float] = mapped_column(Float, default=0)
    writeoff_amount: Mapped[float] = mapped_column(Float, default=0)
    income_record_id: Mapped[int | None] = mapped_column(ForeignKey('records.id'), nullable=True, index=True)
    expense_record_id: Mapped[int | None] = mapped_column(ForeignKey('records.id'), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    asset: Mapped["Asset"] = relationship()

class IntegrationReviewItem(Base, TimestampMixin):
    __tablename__ = 'integration_review_items'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_app: Mapped[str] = mapped_column(String(80), index=True)
    source_event_id: Mapped[str] = mapped_column(String(180), index=True)
    source_entity_type: Mapped[str] = mapped_column(String(100), index=True)
    source_entity_id: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    source_revision: Mapped[int] = mapped_column(Integer, default=1)
    financial_effect: Mapped[str] = mapped_column(String(40), index=True)
    amount: Mapped[float] = mapped_column(Float, default=0)
    currency: Mapped[str] = mapped_column(String(10), default='PHP')
    proposed_account_id: Mapped[int | None] = mapped_column(ForeignKey('financial_accounts.id'), nullable=True, index=True)
    proposed_journal_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_links_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default='ready_for_review', index=True)
    reviewed_at: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    accepted_transaction_id: Mapped[int | None] = mapped_column(ForeignKey('money_transactions.id'), nullable=True, index=True)
    accepted_journal_entry_id: Mapped[int | None] = mapped_column(ForeignKey('journal_entries.id'), nullable=True, index=True)
    accepted_receivable_id: Mapped[int | None] = mapped_column(ForeignKey('receivables.id'), nullable=True, index=True)
    accepted_payable_id: Mapped[int | None] = mapped_column(ForeignKey('payables.id'), nullable=True, index=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    proposed_account: Mapped['FinancialAccount'] = relationship(foreign_keys=[proposed_account_id])
    accepted_transaction: Mapped['MoneyTransaction'] = relationship(foreign_keys=[accepted_transaction_id])
    accepted_journal_entry: Mapped['JournalEntry'] = relationship(foreign_keys=[accepted_journal_entry_id])
    accepted_receivable: Mapped['Receivable'] = relationship(foreign_keys=[accepted_receivable_id])
    accepted_payable: Mapped['Payable'] = relationship(foreign_keys=[accepted_payable_id])
    __table_args__ = (
        UniqueConstraint('source_app', 'source_event_id', 'source_revision', name='uq_integration_review_source_revision'),
        UniqueConstraint('idempotency_key', name='uq_integration_review_idempotency'),
    )
