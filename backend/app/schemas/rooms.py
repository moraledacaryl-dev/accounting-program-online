from __future__ import annotations

from pydantic import BaseModel


class RoomTypeCreate(BaseModel):
    code: str | None = None
    name: str
    description: str | None = None
    base_capacity: int = 2
    max_capacity: int = 2
    is_active: bool = True
    notes: str | None = None


class RoomTypeUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    description: str | None = None
    base_capacity: int | None = None
    max_capacity: int | None = None
    is_active: bool | None = None
    notes: str | None = None


class RoomCreate(BaseModel):
    room_no: str | None = None
    name: str
    room_type_id: int | None = None
    floor_zone: str | None = None
    view_name: str | None = None
    status: str = 'available'
    is_active: bool = True
    notes: str | None = None


class RoomUpdate(BaseModel):
    room_no: str | None = None
    name: str | None = None
    room_type_id: int | None = None
    floor_zone: str | None = None
    view_name: str | None = None
    status: str | None = None
    is_active: bool | None = None
    notes: str | None = None


class RatePlanCreate(BaseModel):
    code: str | None = None
    name: str
    room_type_id: int | None = None
    base_rate: float = 0
    breakfast_included: int = 0
    pax_included: int = 2
    is_active: bool = True
    notes: str | None = None


class RatePlanUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    room_type_id: int | None = None
    base_rate: float | None = None
    breakfast_included: int | None = None
    pax_included: int | None = None
    is_active: bool | None = None
    notes: str | None = None


class BookingChannelCreate(BaseModel):
    code: str | None = None
    name: str
    channel_class: str | None = None
    settlement_mode: str | None = None
    default_commission_rate: float = 0
    is_prepaid: bool = False
    is_active: bool = True
    notes: str | None = None


class BookingChannelUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    channel_class: str | None = None
    settlement_mode: str | None = None
    default_commission_rate: float | None = None
    is_prepaid: bool | None = None
    is_active: bool | None = None
    notes: str | None = None


class RoomPackageRuleCreate(BaseModel):
    name: str
    room_type_id: int | None = None
    rate_plan_id: int | None = None
    included_breakfast: int = 0
    included_pax: int = 2
    extra_pax_rate: float = 0
    is_active: bool = True
    notes: str | None = None


class RoomPackageRuleUpdate(BaseModel):
    name: str | None = None
    room_type_id: int | None = None
    rate_plan_id: int | None = None
    included_breakfast: int | None = None
    included_pax: int | None = None
    extra_pax_rate: float | None = None
    is_active: bool | None = None
    notes: str | None = None
