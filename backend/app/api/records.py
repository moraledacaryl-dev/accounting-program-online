from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.common import RecordCreate, RecordUpdate, ApprovalPayload
from app.services.record_service import create_record, delete_record, get_record, list_records, update_record, get_record_obj
from app.services.taxonomy_service import get_module_by_slug, get_module_name
from app.api.deps import get_current_user, require_any_permissions, require_permissions

router = APIRouter()

@router.get('/{module_slug}/meta')
def module_meta(module_slug: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return {'slug': module_slug, 'name': get_module_name(module_slug), 'taxonomy': get_module_by_slug(module_slug, db)}

@router.get('/{module_slug}/records')
def module_records(module_slug: str, db: Session = Depends(get_db), user=Depends(get_current_user), limit: int = Query(200, ge=1, le=1000), search: str | None = None):
    return list_records(db, module_slug, limit=limit, search=search)

@router.post('/{module_slug}/records')
def module_create_record(
    module_slug: str,
    payload: RecordCreate,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions(
        'cashflow.money_in',
        'cashflow.money_out',
        'inventory.manage',
        'assets.manage',
        'payroll_periods.manage',
        'menu.manage',
        'bookings.edit',
    )),
):
    try:
        return create_record(db, module_slug, payload, username=user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get('/single/{record_id}')
def single_record(record_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    record = get_record(db, record_id)
    if not record:
        raise HTTPException(status_code=404, detail='Record not found')
    return record

@router.put('/single/{record_id}')
def single_update(
    record_id: int,
    payload: RecordUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions(
        'cashflow.money_in',
        'cashflow.money_out',
        'inventory.manage',
        'assets.manage',
        'payroll_periods.manage',
        'menu.manage',
        'bookings.edit',
    )),
):
    try:
        record = update_record(db, record_id, payload, approver=user.username)
        if not record:
            raise HTTPException(status_code=404, detail='Record not found')
        return record
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post('/single/{record_id}/approve')
def approve_record(record_id: int, payload: ApprovalPayload, db: Session = Depends(get_db), user=Depends(require_permissions('approvals.act'))):
    status = 'approved' if payload.approved else 'rejected'
    try:
        current = get_record_obj(db, record_id)
        notes = current.notes if current else None
        if payload.note:
            notes = '\n'.join(filter(None, [notes, f'{status.title()} by {user.username}: {payload.note.strip()}']))
        record = update_record(db, record_id, RecordUpdate(workflow_status=status, notes=notes), approver=user.username)
        if not record:
            raise HTTPException(status_code=404, detail='Record not found')
        return record
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete('/single/{record_id}')
def single_delete(
    record_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('approvals.act', 'cashflow.money_out', 'inventory.manage', 'assets.manage')),
):
    try:
        ok = delete_record(db, record_id)
        if not ok:
            raise HTTPException(status_code=404, detail='Record not found')
        return {'ok': True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
