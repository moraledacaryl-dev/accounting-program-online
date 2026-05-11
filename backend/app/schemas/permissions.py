from __future__ import annotations

from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    code: str
    name: str
    description: str | None = None
    is_active: bool = True


class RoleUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class RolePermissionUpdate(BaseModel):
    permission_keys: list[str] = Field(default_factory=list)


class UserRoleAssignment(BaseModel):
    role_ids: list[int] = Field(default_factory=list)


class UserPermissionOverrideInput(BaseModel):
    permission_key: str
    is_allowed: bool = True


class UserPermissionOverrideUpdate(BaseModel):
    overrides: list[UserPermissionOverrideInput] = Field(default_factory=list)
