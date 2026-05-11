from __future__ import annotations

from pydantic import BaseModel


class ChartAccountCreate(BaseModel):
    code: str | None = None
    name: str
    account_type: str
    subtype: str | None = None
    parent_id: int | None = None
    is_active: bool = True
    notes: str | None = None


class ChartAccountUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    account_type: str | None = None
    subtype: str | None = None
    parent_id: int | None = None
    is_active: bool | None = None
    notes: str | None = None


class AccountMappingRuleCreate(BaseModel):
    module_slug: str
    category: str | None = None
    bucket: str | None = None
    item: str | None = None
    direction: str | None = None
    payment_method: str | None = None
    debit_account_code: str | None = None
    credit_account_code: str | None = None
    priority: int = 100
    is_active: bool = True
    notes: str | None = None


class AccountMappingRuleUpdate(BaseModel):
    module_slug: str | None = None
    category: str | None = None
    bucket: str | None = None
    item: str | None = None
    direction: str | None = None
    payment_method: str | None = None
    debit_account_code: str | None = None
    credit_account_code: str | None = None
    priority: int | None = None
    is_active: bool | None = None
    notes: str | None = None
