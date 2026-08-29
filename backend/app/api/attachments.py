from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.settings import settings
from app.db.database import get_db
from app.models.entities import (
    AccountTransfer,
    Asset,
    Attachment,
    Booking,
    CashReconciliation,
    ChannelPayout,
    MoneyTransaction,
    Payable,
    PayrollRun,
    Receivable,
    Record,
    SaleOrder,
    StockMovement,
)
from app.services.attachment_security_service import (
    MAX_FILE_SIZE_BYTES,
    authorize_attachment_entity,
    can_access_attachment_entity,
    enforce_upload_quota,
    inspect_attachment_content,
    promote_quarantined_file,
    quarantine_path,
    scan_quarantined_file,
    write_quarantine_file,
)

router = APIRouter()

UPLOAD_ROOT = settings.uploads_path
ALLOWED_ENTITY_TYPES = {
    'record': Record,
    'stock_movement': StockMovement,
    'sale_order': SaleOrder,
    'booking': Booking,
    'asset': Asset,
    'payroll_run': PayrollRun,
    'channel_payout': ChannelPayout,
    'money_transaction': MoneyTransaction,
    'account_transfer': AccountTransfer,
    'cash_reconciliation': CashReconciliation,
    'receivable': Receivable,
    'payable': Payable,
}


def _normalize_entity_type(value: str | None) -> str:
    return (value or '').strip().lower()


def _ensure_upload_dir():
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)


def _sanitize_filename(name: str | None) -> str:
    base = Path((name or '').strip() or 'attachment.bin').name
    if not base:
        return 'attachment.bin'
    return base[:240]


def _attachment_disk_path(row: Attachment) -> Path:
    stored_name = row.stored_name or Path(row.file_path or '').name
    return UPLOAD_ROOT / Path(stored_name).name


def _serialize_attachment(row: Attachment) -> dict:
    # Internal storage paths/names are intentionally never exposed through the API.
    return {
        'id': row.id,
        'entity_type': row.entity_type,
        'entity_id': row.entity_id,
        'file_name': row.file_name,
        'content_type': row.content_type,
        'size_bytes': row.size_bytes,
        'download_url': f'{settings.api_prefix}/attachments/{row.id}/download',
        'note': row.note,
        'uploaded_by': row.uploaded_by,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def _validate_entity(db: Session, entity_type: str, entity_id: int):
    model = ALLOWED_ENTITY_TYPES.get(entity_type)
    if not model:
        allowed = ', '.join(sorted(ALLOWED_ENTITY_TYPES.keys()))
        raise ValueError(f'Invalid entity_type "{entity_type}". Allowed: {allowed}.')
    if int(entity_id) <= 0:
        raise ValueError('entity_id must be greater than zero.')
    obj = db.get(model, int(entity_id))
    if not obj:
        raise ValueError(f'{entity_type} {entity_id} not found.')
    return obj


def _entity_or_400(db: Session, entity_type: str, entity_id: int):
    try:
        return _validate_entity(db, entity_type, entity_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/')
def list_attachments(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    entity_type: str | None = None,
    entity_id: int | None = None,
    limit: int = Query(200, ge=1, le=1000),
):
    normalized_entity_type = _normalize_entity_type(entity_type) if entity_type else None
    if entity_id is not None and not normalized_entity_type:
        raise HTTPException(status_code=400, detail='entity_type is required when entity_id is supplied.')

    q = db.query(Attachment)
    if normalized_entity_type:
        if normalized_entity_type not in ALLOWED_ENTITY_TYPES:
            raise HTTPException(status_code=400, detail='Invalid entity_type.')
        q = q.filter(Attachment.entity_type == normalized_entity_type)
    if entity_id is not None:
        obj = _entity_or_400(db, normalized_entity_type, int(entity_id))
        authorize_attachment_entity(db, user, normalized_entity_type, obj, write=False)
        q = q.filter(Attachment.entity_id == int(entity_id))

    # Read authorization is evaluated per underlying resource so a global list can
    # never become a cross-module attachment enumeration endpoint.
    rows = q.order_by(Attachment.id.desc()).limit(min(limit * 5, 5000)).all()
    visible = []
    for row in rows:
        model = ALLOWED_ENTITY_TYPES.get(row.entity_type)
        if not model:
            continue
        obj = db.get(model, int(row.entity_id))
        if not obj:
            continue
        if can_access_attachment_entity(db, user, row.entity_type, obj, write=False):
            visible.append(_serialize_attachment(row))
            if len(visible) >= limit:
                break
    return visible


@router.post('/upload')
async def upload_attachment(
    file: UploadFile = File(...),
    entity_type: str = Form(...),
    entity_id: int = Form(...),
    note: str | None = Form(None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    normalized_entity_type = _normalize_entity_type(entity_type)
    entity = _entity_or_400(db, normalized_entity_type, int(entity_id))
    authorize_attachment_entity(db, user, normalized_entity_type, entity, write=True)

    safe_name = _sanitize_filename(file.filename)
    data = await file.read(MAX_FILE_SIZE_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail='File is empty.')
    if len(data) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail=f'File exceeds max size of {MAX_FILE_SIZE_BYTES} bytes.')

    try:
        inspection = inspect_attachment_content(safe_name, data, file.content_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    enforce_upload_quota(db, getattr(user, 'username', None), len(data))
    _ensure_upload_dir()

    stored_name = f'{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")}-{uuid4().hex}{inspection.extension}'
    relative_path = f'/uploads/{stored_name}'
    absolute_path = UPLOAD_ROOT / stored_name
    quarantined = quarantine_path(UPLOAD_ROOT, stored_name)

    try:
        write_quarantine_file(quarantined, data)
        scan_quarantined_file(quarantined)
        promote_quarantined_file(quarantined, absolute_path)
        row = Attachment(
            entity_type=normalized_entity_type,
            entity_id=int(entity_id),
            file_name=safe_name,
            stored_name=stored_name,
            content_type=inspection.content_type,
            size_bytes=len(data),
            file_path=relative_path,
            note=note,
            uploaded_by=getattr(user, 'username', None),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _serialize_attachment(row)
    except HTTPException:
        quarantined.unlink(missing_ok=True)
        absolute_path.unlink(missing_ok=True)
        db.rollback()
        raise
    except Exception:
        quarantined.unlink(missing_ok=True)
        absolute_path.unlink(missing_ok=True)
        db.rollback()
        raise


@router.get('/{attachment_id}/download')
def download_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    row = db.get(Attachment, int(attachment_id))
    if not row:
        raise HTTPException(status_code=404, detail='Attachment not found.')
    entity = _entity_or_400(db, row.entity_type, int(row.entity_id))
    authorize_attachment_entity(db, user, row.entity_type, entity, write=False)

    absolute_path = _attachment_disk_path(row)
    if not absolute_path.exists() or not absolute_path.is_file():
        raise HTTPException(status_code=404, detail='Attachment file is missing from storage.')
    if absolute_path.parent.resolve() != UPLOAD_ROOT.resolve():
        raise HTTPException(status_code=404, detail='Attachment storage path is invalid.')

    # Historical files are re-sniffed at download time so unsafe legacy content is
    # not grandfathered merely because it predates Pass 67.
    try:
        inspection = inspect_attachment_content(row.file_name or absolute_path.name, absolute_path.read_bytes(), None)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail='Attachment is blocked by the current file security policy.') from exc

    return FileResponse(
        path=str(absolute_path),
        filename=row.file_name or absolute_path.name,
        media_type=inspection.content_type,
        headers={
            'Cache-Control': 'private, no-store',
            'X-Content-Type-Options': 'nosniff',
            'Content-Security-Policy': 'sandbox',
        },
    )


@router.delete('/{attachment_id}')
def delete_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    row = db.get(Attachment, int(attachment_id))
    if not row:
        raise HTTPException(status_code=404, detail='Attachment not found.')
    entity = _entity_or_400(db, row.entity_type, int(row.entity_id))
    authorize_attachment_entity(db, user, row.entity_type, entity, write=True)

    absolute_path = _attachment_disk_path(row)
    db.delete(row)
    db.commit()
    if absolute_path.exists() and absolute_path.parent.resolve() == UPLOAD_ROOT.resolve():
        absolute_path.unlink(missing_ok=True)
    return {'ok': True}
