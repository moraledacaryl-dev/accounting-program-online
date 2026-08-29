from __future__ import annotations

from datetime import date

from app.core.business_clock import business_today


def is_due_or_overdue(due_date: str | None) -> bool:
    if not due_date:
        return False
    try:
        parsed = date.fromisoformat(due_date[:10])
        today = date.fromisoformat(business_today())
    except ValueError:
        return False
    return parsed <= today
