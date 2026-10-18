"""Recover Beds24 cancellations missed by booking webhooks.

Only imported reservations already linked by exact Beds24 ID are eligible.
Do not create bookings, guests, folios, payments, or mirror snapshots.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.entities import SystemSetting
from app.services.beds24_cancellation_service import apply_beds24_cancellation
from app.services.beds24_service import fetch_beds24_bookings, load_beds24_settings
from app.services.beds24_sync_service import _upsert_sync_log

logger = logging.getLogger(__name__)
STATE_KEY = 'beds24_cancellation_reconcile_state'
INITIAL_LOOKBACK_DAYS = 30
OVERLAP_MINUTES = 15
MAX_PAGES = 20


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def _previous_watermark(db: Session, now: datetime) -> datetime:
    row = db.query(SystemSetting).filter(SystemSetting.key == STATE_KEY).one_or_none()
    fallback = now - timedelta(days=INITIAL_LOOKBACK_DAYS)
    if not row:
        return fallback
    try:
        data = json.loads(row.value_json or '{}')
        value = datetime.fromisoformat(str(data['last_success_utc']).replace('Z', '+00:00'))
        if value.tzinfo is None:
            raise ValueError('Missing UTC offset')
        return max(fallback, min(value.astimezone(timezone.utc) - timedelta(minutes=OVERLAP_MINUTES), now))
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return fallback


def _save_watermark(db: Session, now: datetime) -> None:
    row = db.query(SystemSetting).filter(SystemSetting.key == STATE_KEY).one_or_none()
    if row is None:
        row = SystemSetting(key=STATE_KEY)
    row.value_json = json.dumps({'last_success_utc': _utc_iso(now)})
    row.updated_by = 'beds24_cancellation_reconcile'
    db.add(row)
    db.commit()


def reconcile_beds24_cancellations(
    db: Session, *, now: datetime | None = None, max_pages: int = MAX_PAGES
) -> dict:
    """Recheck modified bookings irrespective of their arrival or departure dates.

    An incomplete page, API error, or failed booking never advances the watermark.
    All changes reuse the status-only cancellation path, preserving the ledger.
    """
    settings = load_beds24_settings(db)
    if not settings.get('enabled') or settings.get('manual_sync_only'):
        return {'ok': True, 'skipped': True, 'reason': 'beds24_automatic_sync_disabled'}

    end = now or _utc_now()
    if end.tzinfo is None:
        raise ValueError('A timezone-aware UTC timestamp is required')
    start = _previous_watermark(db, end)
    counters = {'fetched': 0, 'cancelled': 0, 'unchanged': 0, 'not_linked': 0, 'pages': 0}
    failed_ids: list[str] = []

    try:
        for page in range(1, max_pages + 1):
            bookings, payload, _ = fetch_beds24_bookings(
                db,
                modified_from=_utc_iso(start),
                page=page,
                include_invoice_items=False,
            )
            counters['pages'] += 1
            counters['fetched'] += len(bookings)
            for item in bookings:
                if str(item.get('status') or '').strip().lower() not in {'cancelled', 'canceled'}:
                    continue
                bid = str(item.get('id') or item.get('bookingId') or '').strip()
                if not bid:
                    failed_ids.append('<missing-id>')
                    continue
                try:
                    result = apply_beds24_cancellation(db, item, source_type='reconciliation')
                    db.commit()
                    action = result.get('action', 'unchanged')
                    if action == 'cancelled':
                        counters['cancelled'] += 1
                    elif action == 'not_linked':
                        counters['not_linked'] += 1
                    else:
                        counters['unchanged'] += 1
                except Exception:
                    db.rollback()
                    logger.exception('Beds24 cancellation reconciliation failed for booking %s', bid)
                    failed_ids.append(bid)

            # Beds24 V2 explicitly advertises the next page. Never guess by
            # list length or reuse arrival-date filters when checking changes.
            next_link = payload.get('nextPageLink') if isinstance(payload, dict) else None
            if not next_link:
                break
        else:
            raise RuntimeError(f'Beds24 modified-booking scan exceeded {max_pages} pages; watermark not advanced')

        if failed_ids:
            raise RuntimeError(f'{len(failed_ids)} Beds24 cancellations need review; watermark not advanced')

        _save_watermark(db, end)
        _upsert_sync_log(
            db, event_type='cancellation_reconciliation', source_type='scheduled',
            status='success', message='Beds24 modified booking reconciliation completed.',
            payload={'modified_from': _utc_iso(start), 'through': _utc_iso(end), **counters},
        )
        return {'ok': True, 'modified_from': _utc_iso(start), 'through': _utc_iso(end), **counters}
    except Exception as exc:
        db.rollback()
        _upsert_sync_log(
            db, event_type='cancellation_reconciliation', source_type='scheduled',
            status='error', message='Beds24 cancellation reconciliation incomplete; retry required.',
            payload={
                'modified_from': _utc_iso(start),
                'through': _utc_iso(end),
                **counters,
                'failed_booking_ids': failed_ids[:25],
                'error_type': type(exc).__name__,
            },
        )
        raise
