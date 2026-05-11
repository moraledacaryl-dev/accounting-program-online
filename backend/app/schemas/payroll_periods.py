from __future__ import annotations

from pydantic import BaseModel, Field


class PayrollPeriodLineInput(BaseModel):
    employee_id: int | None = None
    employee_name: str
    department: str | None = None
    regular_hours: float = 0
    overtime_hours: float = 0
    regular_holiday_hours: float = 0
    special_holiday_hours: float = 0
    night_diff_hours: float = 0
    regular_amount: float = 0
    overtime_amount: float = 0
    holiday_amount: float = 0
    night_diff_amount: float = 0
    allowances: float = 0
    deductions: float = 0
    employer_contribution: float = 0
    gross_pay: float = 0
    net_pay: float = 0
    notes: str | None = None


class PayrollPeriodCreate(BaseModel):
    name: str
    period_start: str | None = None
    period_end: str | None = None
    release_date: str | None = None
    status: str = 'draft'
    source_type: str = 'manual'
    notes: str | None = None
    lines: list[PayrollPeriodLineInput] = Field(default_factory=list)


class PayrollPeriodUpdate(BaseModel):
    name: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    release_date: str | None = None
    status: str | None = None
    source_type: str | None = None
    notes: str | None = None
    lines: list[PayrollPeriodLineInput] | None = None


class PayrollImportCreate(BaseModel):
    payroll_period_id: int | None = None
    file_name: str
    status: str = 'imported'
    notes: str | None = None
    lines: list[PayrollPeriodLineInput] = Field(default_factory=list)


class PayrollPostAction(BaseModel):
    post_date: str | None = None
