from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import require_any_permissions, require_permissions
from app.db.database import get_db
from app.schemas.beds24 import (
    Beds24BackfillPayload,
    Beds24ResetExecutePayload,
    Beds24ResetPreviewPayload,
    Beds24SettingsUpdate,
    Beds24SyncBookingPayload,
    Beds24SyncRecentPayload,
)
from app.services.beds24_service import Beds24ApiError, load_beds24_settings, save_beds24_settings, test_beds24_connection
from app.services.beds24_sync_service import (
    list_mapping_helpers,
    list_sync_logs,
    list_sync_state,
    preview_reset_mode,
    execute_reset_mode,
    rebuild_booking_mirror_by_id,
    backfill_bookings_by_date_range,
    sync_booking_by_id,
    sync_from_webhook,
    sync_recent_bookings,
)

router = APIRouter()


@router.get('/settings')
def get_beds24_settings(
    db: Session = Depends(get_db),
    user=Depends(require_permissions('integrations.view')),
):
    return {
        'settings': load_beds24_settings(db),
    }


@router.put('/settings')
def update_beds24_settings(
    payload: Beds24SettingsUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('integrations.manage')),
):
    data = payload.model_dump(exclude_unset=True)
    try:
        settings = save_beds24_settings(db, data, updated_by=getattr(user, 'username', None))
        return {
            'settings': settings,
            'message': 'Beds24 settings saved.',
        }
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.post('/test-connection')
def beds24_test_connection(
    db: Session = Depends(get_db),
    user=Depends(require_permissions('integrations.sync')),
):
    try:
        return test_beds24_connection(db)
    except Beds24ApiError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post('/sync/booking')
def beds24_sync_booking(
    payload: Beds24SyncBookingPayload,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('integrations.sync')),
):
    try:
        return sync_booking_by_id(
            db,
            payload.booking_id,
            source_type='manual',
            include_invoice_items=payload.include_invoice_items,
            triggered_by=getattr(user, 'username', None),
            replace_mirror=bool(payload.force_resync),
            force_folio_mirror=bool(payload.force_resync),
        )
    except Beds24ApiError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post('/sync/booking/rebuild')
def beds24_rebuild_booking_mirror(
    payload: Beds24SyncBookingPayload,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('integrations.manage')),
):
    try:
        return rebuild_booking_mirror_by_id(
            db,
            payload.booking_id,
            include_invoice_items=payload.include_invoice_items,
            triggered_by=getattr(user, 'username', None),
        )
    except Beds24ApiError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post('/sync/recent')
def beds24_sync_recent(
    payload: Beds24SyncRecentPayload,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('integrations.sync')),
):
    try:
        return sync_recent_bookings(
            db,
            limit=payload.limit,
            status=payload.status,
            filter_value=payload.filter,
            include_invoice_items=payload.include_invoice_items,
            source_type='manual',
            triggered_by=getattr(user, 'username', None),
        )
    except Beds24ApiError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post('/sync/backfill')
def beds24_sync_backfill(
    payload: Beds24BackfillPayload,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('integrations.sync')),
):
    try:
        return backfill_bookings_by_date_range(
            db,
            from_date=payload.from_date,
            to_date=payload.to_date,
            property_id=payload.property_id,
            statuses=payload.statuses,
            include_invoice_items=payload.include_invoice_items,
            dry_run=payload.dry_run,
            chunk_days=payload.chunk_days,
            request_delay_seconds=payload.request_delay_seconds,
            source_type='backfill_preview' if payload.dry_run else 'backfill',
            triggered_by=getattr(user, 'username', None),
        )
    except Beds24ApiError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get('/logs')
def beds24_logs(
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('integrations.logs.view', 'integrations.sync', 'integrations.manage')),
    limit: int = Query(200, ge=1, le=2000),
    status: str | None = None,
    source_type: str | None = None,
):
    return list_sync_logs(db, limit=limit, status=status, source_type=source_type)


@router.get('/sync-state')
def beds24_sync_state(
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('integrations.logs.view', 'integrations.sync', 'integrations.manage')),
    limit: int = Query(100, ge=1, le=1000),
):
    return list_sync_state(db, limit=limit)


@router.get('/mapping-helpers')
def beds24_mapping_helpers(
    db: Session = Depends(get_db),
    user=Depends(require_permissions('integrations.view')),
):
    return list_mapping_helpers(db)


@router.post('/reset/preview')
def beds24_reset_preview(
    payload: Beds24ResetPreviewPayload,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('integrations.manage')),
):
    try:
        return preview_reset_mode(db, payload.mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post('/reset/execute')
def beds24_reset_execute(
    payload: Beds24ResetExecutePayload,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('integrations.manage')),
):
    try:
        return execute_reset_mode(
            db,
            payload.mode,
            confirmation=payload.confirmation,
            triggered_by=getattr(user, 'username', None),
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))


@router.post('/webhook')
async def beds24_webhook(
    request: Request,
    secret: str | None = None,
    db: Session = Depends(get_db),
):
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    try:
        result = sync_from_webhook(
            db,
            payload,
            headers={k.lower(): v for k, v in request.headers.items()},
            query_secret=secret,
            triggered_by='beds24_webhook',
        )
        return {'ok': True, 'result': result}
    except Beds24ApiError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
