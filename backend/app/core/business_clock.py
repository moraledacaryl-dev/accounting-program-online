from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


BUSINESS_TIMEZONE_NAME = 'Asia/Manila'
BUSINESS_TIMEZONE = ZoneInfo(BUSINESS_TIMEZONE_NAME)


def business_now(now: datetime | None = None) -> datetime:
    """Return an aware datetime in the configured business timezone.

    Naive injected datetimes are treated as UTC so tests and callers cannot
    accidentally depend on the host machine timezone.
    """
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(BUSINESS_TIMEZONE)


def business_today(now: datetime | None = None) -> str:
    return business_now(now).date().isoformat()


def business_month(now: datetime | None = None) -> str:
    return business_today(now)[:7]
