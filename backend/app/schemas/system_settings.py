from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SystemSettingsPayload(BaseModel):
    general: dict[str, Any] | None = None
    dashboard: dict[str, Any] | None = None
    code_generation: dict[str, Any] | None = None
    financial_defaults: dict[str, Any] | None = None
    workflow: dict[str, Any] | None = None
    hospitality: dict[str, Any] | None = None
    payroll: dict[str, Any] | None = None
    ui: dict[str, Any] | None = None


class UserDashboardOverridePayload(BaseModel):
    user_id: int
    widgets: list[str] = Field(default_factory=list)


class CodePreviewOut(BaseModel):
    entity: str
    code: str
