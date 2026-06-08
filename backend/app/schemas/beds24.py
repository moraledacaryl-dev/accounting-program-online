from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Beds24SettingsUpdate(BaseModel):
    enabled: bool | None = None
    api_base_url: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    invite_code: str | None = None
    webhook_enabled: bool | None = None
    webhook_secret: str | None = None
    webhook_require_secret: bool | None = None
    manual_sync_only: bool | None = None
    auto_create_guest: bool | None = None
    auto_create_folio_mirror: bool | None = None
    auto_create_receivable_mirror: bool | None = None
    auto_link_room: bool | None = None
    auto_link_channel: bool | None = None
    auto_link_property: bool | None = None
    fallback_unknown_room_behavior: str | None = None
    fallback_unknown_channel_behavior: str | None = None
    include_invoice_items: bool | None = None
    log_verbosity: str | None = None
    room_map_by_room_id: dict[str, int] | None = None
    room_map_by_unit_id: dict[str, int] | None = None
    channel_map_by_source: dict[str, int] | None = None
    property_map_by_id: dict[str, str] | None = None


class Beds24SyncBookingPayload(BaseModel):
    booking_id: str = Field(min_length=1)
    include_invoice_items: bool | None = None
    force_resync: bool = False


class Beds24SyncRecentPayload(BaseModel):
    limit: int = Field(default=25, ge=1, le=200)
    status: str | None = None
    filter: str | None = None
    include_invoice_items: bool | None = None


class Beds24BackfillPayload(BaseModel):
    from_date: str = Field(min_length=10, max_length=10)
    to_date: str = Field(min_length=10, max_length=10)
    property_id: str | None = None
    statuses: list[str] = Field(default_factory=list)
    include_invoice_items: bool | None = None
    dry_run: bool = False
    chunk_days: int = Field(default=31, ge=1, le=92)
    request_delay_seconds: float = Field(default=4, ge=0, le=30)


class Beds24FolioLineReclassifyPayload(BaseModel):
    dry_run: bool = True
    include_manual_source: bool = False
    include_payment_lines: bool = True
    limit: int = Field(default=5000, ge=1, le=50000)


class Beds24WebhookPayload(BaseModel):
    event_type: str | None = None
    booking_id: str | None = None
    booking_ids: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class Beds24ResetPreviewPayload(BaseModel):
    mode: str = Field(min_length=1)


class Beds24ResetExecutePayload(BaseModel):
    mode: str = Field(min_length=1)
    confirmation: str = Field(min_length=1)
