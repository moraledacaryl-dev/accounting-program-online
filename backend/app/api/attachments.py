from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.api.deps import get_current_user, require_any_permissions
from app.db.database import get_db
from app.models.entities import (
    Asset,
    AccountTransfer,
    Attachment,
    Booking,
    CashReconciliation,
    ChannelPayout,
    MoneyTransaction,
    Payable,
    PayrollRun,
    Record,
    Receivable,
    SaleOrder,
    StockMovement,
)

router = APIRouter()

UPLOAD_ROOT = settings.uploads_path
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024
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


def _serialize_attachment(row: Attachment) -> dict:
    return {
        'id': row.id,
        'entity_type': row.entity_type,
        'entity_id': row.entity_id,
        'file_name': row.file_name,
        'stored_name': row.stored_name,
        'content_type': row.content_type,
        'size_bytes': row.size_bytes,
        'file_path': row.file_path,
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


@router.get('/')
def list_attachments(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    entity_type: str | None = None,
    entity_id: int | None = None,
    limit: int = Query(200, ge=1, le=1000),
):
    q = db.query(Attachment)
    normalized_entity_type = _normalize_entity_type(entity_type) if entity_type else None
    if normalized_entity_type:
        q = q.filter(Attachment.entity_type == normalized_entity_type)
    if entity_id:
        q = q.filter(Attachment.entity_id == int(entity_id))
    rows = q.order_by(Attachment.id.desc()).limit(limit).all()
    return [_serialize_attachment(row) for row in rows]


@router.post('/upload')
async def upload_attachment(
    file: UploadFile = File(...),
    entity_type: str = Form(...),
    entity_id: int = Form(...),
    note: str | None = Form(None),
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions(
        'bookings.edit',
        'suppliers.manage',
        'purchase_requests.create',
        'purchase_orders.create',
        'receiving.post',
        'cashflow.money_in',
        'cashflow.money_out',
        'cashflow.reconcile',
        'payroll_periods.manage',
        'assets.manage',
        'bir.manage',
    )),
):
    normalized_entity_type = _normalize_entity_type(entity_type)
    _validate_entity(db, normalized_entity_type, int(entity_id))

    safe_name = _sanitize_filename(file.filename)
    ext = Path(safe_name).suffix.lower()[:16]
    stored_name = f'{datetime.utcnow().strftime("%Y%m%d%H%M%S")}-{uuid4().hex}{ext}'
    relative_path = f'/uploads/{stored_name}'
    absolute_path = UPLOAD_ROOT / stored_name

    _ensure_upload_dir()
    data = await file.read(MAX_FILE_SIZE_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail='File is empty.')
    if len(data) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail=f'File exceeds max size of {MAX_FILE_SIZE_BYTES} bytes.')

    try:
        absolute_path.write_bytes(data)
        row = Attachment(
            entity_type=normalized_entity_type,
            entity_id=int(entity_id),
            file_name=safe_name,
            stored_name=stored_name,
            content_type=file.content_type,
            size_bytes=len(data),
            file_path=relative_path,
            note=note,
            uploaded_by=getattr(user, 'username', None),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _serialize_attachment(row)
    except ValueError as e:
        if absolute_path.exists():
            absolute_path.unlink(missing_ok=True)
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        if absolute_path.exists():
            absolute_path.unlink(missing_ok=True)
        db.rollback()
        raise


@router.delete('/{attachment_id}')
def delete_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions(
        'bookings.edit',
        'suppliers.manage',
        'purchase_requests.create',
        'purchase_orders.create',
        'receiving.post',
        'cashflow.money_in',
        'cashflow.money_out',
        'cashflow.reconcile',
        'payroll_periods.manage',
        'assets.manage',
        'bir.manage',
    )),
):
    row = db.get(Attachment, int(attachment_id))
    if not row:
        raise HTTPException(status_code=404, detail='Attachment not found.')

    absolute_path = UPLOAD_ROOT / Path(row.file_path or '').name
    db.delete(row)
    db.commit()
    if absolute_path.exists():
        absolute_path.unlink(missing_ok=True)
    return {'ok': True}
