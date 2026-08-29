from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib import error, request

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.models.operations_outbox import OperationsOutboxEvent

OUTBOX_MAX_ATTEMPTS = 12
OUTBOX_BASE_RETRY_SECONDS = 15
OUTBOX_MAX_RETRY_SECONDS = 1800
OUTBOX_PROCESSING_LEASE_SECONDS = 120


class OperationsDeliveryError(RuntimeError):
    def __init__(self, message: str, *, http_status: int | None = None):
        super().__init__(message)
        self.http_status = http_status


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, 'isoformat'):
        try:
            return value.isoformat()
        except TypeError:
            pass
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def build_operations_envelope(
    *,
    event_id: str,
    event_type: str,
    title: str,
    summary: str,
    payload: dict[str, Any],
    priority: str = 'Normal',
    subject_type: str | None = None,
    subject_id: int | str | None = None,
    occurred_at: datetime | None = None,
) -> dict[str, Any]:
    envelope: dict[str, Any] = {
        'event_id': event_id,
        'event_type': event_type,
        'schema_version': 1,
        'occurred_at': (occurred_at or datetime.now(timezone.utc)).isoformat(),
        'title': title,
        'summary': summary,
        'priority': priority,
        'payload': _json_value(payload),
        'metadata': {'producer': 'accounting-program-online'},
    }
    if subject_type and subject_id is not None:
        envelope['subject'] = {'type': subject_type, 'id': str(subject_id)}
    return envelope


def enqueue_operations_event(
    db: Session,
    *,
    event_id: str,
    event_type: str,
    title: str,
    summary: str,
    payload: dict[str, Any],
    priority: str = 'Normal',
    subject_type: str | None = None,
    subject_id: int | str | None = None,
) -> OperationsOutboxEvent | None:
    if not settings.operations_integration_enabled:
        return None

    normalized_id = (event_id or '').strip()
    if not normalized_id:
        raise ValueError('event_id is required for durable Operations delivery.')

    existing = db.query(OperationsOutboxEvent).filter(
        OperationsOutboxEvent.event_id == normalized_id
    ).first()
    if existing:
        return existing

    envelope = build_operations_envelope(
        event_id=normalized_id,
        event_type=event_type,
        title=title,
        summary=summary,
        payload=payload,
        priority=priority,
        subject_type=subject_type,
        subject_id=subject_id,
    )
    row = OperationsOutboxEvent(
        event_id=normalized_id,
        event_type=(event_type or '').strip() or 'accounting.event',
        envelope_json=json.dumps(envelope, separators=(',', ':'), sort_keys=True),
        status='pending',
        attempt_count=0,
        next_attempt_at=datetime.now(timezone.utc),
    )

    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
        return row
    except IntegrityError:
        existing = db.query(OperationsOutboxEvent).filter(
            OperationsOutboxEvent.event_id == normalized_id
        ).first()
        if existing:
            return existing
        raise


def _claimable_filter(now: datetime):
    stale_before = now - timedelta(seconds=OUTBOX_PROCESSING_LEASE_SECONDS)
    return or_(
        OperationsOutboxEvent.status.in_(['pending', 'retry']),
        (
            (OperationsOutboxEvent.status == 'processing')
            & (OperationsOutboxEvent.last_attempt_at.is_not(None))
            & (OperationsOutboxEvent.last_attempt_at <= stale_before)
        ),
    )


def claim_next_operations_event(db: Session, *, now: datetime | None = None) -> OperationsOutboxEvent | None:
    instant = now or datetime.now(timezone.utc)
    row = (
        db.query(OperationsOutboxEvent)
        .filter(
            _claimable_filter(instant),
            or_(
                OperationsOutboxEvent.next_attempt_at.is_(None),
                OperationsOutboxEvent.next_attempt_at <= instant,
            ),
            OperationsOutboxEvent.attempt_count < OUTBOX_MAX_ATTEMPTS,
        )
        .order_by(OperationsOutboxEvent.id.asc())
        .with_for_update(skip_locked=True)
        .first()
    )
    if not row:
        return None

    row.status = 'processing'
    row.attempt_count = int(row.attempt_count or 0) + 1
    row.last_attempt_at = instant
    row.last_error = None
    row.last_http_status = None
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def deliver_operations_envelope(envelope_json: str) -> int:
    base = settings.operations_api_base.rstrip('/')
    key = settings.operations_integration_key.strip()
    if not settings.operations_integration_enabled:
        raise OperationsDeliveryError('Operations integration is disabled.')
    if not base or not key:
        raise OperationsDeliveryError('Operations integration endpoint or key is missing.')

    try:
        envelope = json.loads(envelope_json)
    except json.JSONDecodeError as exc:
        raise OperationsDeliveryError(f'Outbox envelope is invalid JSON: {exc}') from exc

    event_id = str(envelope.get('event_id') or '').strip()
    if not event_id:
        raise OperationsDeliveryError('Outbox envelope is missing event_id.')

    body = json.dumps(envelope, separators=(',', ':')).encode('utf-8')
    endpoint = f"{base}/integrations/v2/events/{settings.operations_source_app}"
    outbound = request.Request(
        endpoint,
        data=body,
        method='POST',
        headers={
            'Content-Type': 'application/json',
            'X-Integration-Api-Key': key,
            'Idempotency-Key': event_id,
            'X-Integration-Event-Id': event_id,
        },
    )
    try:
        with request.urlopen(outbound, timeout=settings.operations_integration_timeout_seconds) as response:
            response.read()
            status = int(getattr(response, 'status', 200) or 200)
            if status < 200 or status >= 300:
                raise OperationsDeliveryError(
                    f'Operations returned HTTP {status}.',
                    http_status=status,
                )
            return status
    except error.HTTPError as exc:
        try:
            exc.read()
        except Exception:
            pass
        raise OperationsDeliveryError(
            f'Operations returned HTTP {exc.code}.',
            http_status=int(exc.code),
        ) from exc
    except (error.URLError, TimeoutError, OSError) as exc:
        raise OperationsDeliveryError(f'Operations delivery failed: {exc}') from exc


def mark_operations_event_delivered(
    db: Session,
    event_id: int,
    *,
    http_status: int,
    now: datetime | None = None,
) -> OperationsOutboxEvent:
    row = db.get(OperationsOutboxEvent, int(event_id))
    if not row:
        raise ValueError('Operations outbox event not found.')
    instant = now or datetime.now(timezone.utc)
    row.status = 'delivered'
    row.delivered_at = instant
    row.next_attempt_at = None
    row.last_http_status = int(http_status)
    row.last_error = None
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _retry_delay_seconds(attempt_count: int) -> int:
    power = max(0, int(attempt_count or 1) - 1)
    return min(OUTBOX_MAX_RETRY_SECONDS, OUTBOX_BASE_RETRY_SECONDS * (2 ** power))


def mark_operations_event_failed(
    db: Session,
    event_id: int,
    *,
    error_message: str,
    http_status: int | None = None,
    now: datetime | None = None,
) -> OperationsOutboxEvent:
    row = db.get(OperationsOutboxEvent, int(event_id))
    if not row:
        raise ValueError('Operations outbox event not found.')
    instant = now or datetime.now(timezone.utc)
    attempts = int(row.attempt_count or 0)
    row.last_error = (error_message or 'Unknown delivery error')[:4000]
    row.last_http_status = int(http_status) if http_status is not None else None
    if attempts >= OUTBOX_MAX_ATTEMPTS:
        row.status = 'dead'
        row.next_attempt_at = None
    else:
        row.status = 'retry'
        row.next_attempt_at = instant + timedelta(seconds=_retry_delay_seconds(attempts))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def operations_outbox_status(db: Session) -> dict[str, Any]:
    counts = {
        status: int(count)
        for status, count in (
            db.query(OperationsOutboxEvent.status, func.count(OperationsOutboxEvent.id))
            .group_by(OperationsOutboxEvent.status)
            .all()
        )
    }
    oldest = (
        db.query(OperationsOutboxEvent)
        .filter(OperationsOutboxEvent.status.in_(['pending', 'retry', 'processing']))
        .order_by(OperationsOutboxEvent.created_at.asc())
        .first()
    )
    now = datetime.now(timezone.utc)
    oldest_age_seconds = None
    if oldest and oldest.created_at:
        created = oldest.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        oldest_age_seconds = max(0, int((now - created).total_seconds()))

    pending = sum(counts.get(key, 0) for key in ('pending', 'retry', 'processing'))
    dead = counts.get('dead', 0)
    return {
        'enabled': bool(settings.operations_integration_enabled),
        'pending': pending,
        'dead': dead,
        'delivered': counts.get('delivered', 0),
        'counts': counts,
        'oldest_pending_age_seconds': oldest_age_seconds,
        'healthy': (not settings.operations_integration_enabled) or dead == 0,
    }
