from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.common import RecordCreate, RecordUpdate, ApprovalPayload
from app.services.record_service import create_record, delete_record, get_record, list_records, update_record, get_record_obj
from app.services.taxonomy_service import get_module_by_slug, get_module_name
from app.services.permission_service import get_user_permission_keys
from app.api.deps import enforce_external_record_ownership, get_current_user, require_any_permissions, require_permissions

router = APIRouter()

RECORD_READ_PERMISSIONS = {
    'rooms': ('bookings.view', 'guests.view', 'folios.view', 'room_setup.view'),
    'restaurant': ('restaurant.view', 'menu.view'),
    'breakfast': ('restaurant.view',),
    'cafe': ('restaurant.view',),
    'bar': ('restaurant.view',),
    'events': ('events.view',),
    'inventory': ('inventory.view',),
    'procurement': ('inventory.view', 'suppliers.view', 'purchase_requests.view', 'purchase_orders.view', 'receiving.view'),
    'internal': ('dashboard.view',),
    'channel_ota': ('bookings.view',),
    'reconciliation': ('cashflow.view',),
    'payroll': ('payroll_periods.view',),
    'assets': ('assets.view',),
    'utilities': ('cashflow.view',),
    'finance': ('cashflow.view', 'journals.view', 'reports.view'),
    'other_income': ('cashflow.view',),
    'bir_statutory': ('bir.view',),
    'master_data': ('master_data.manage',),
    'workflow_status_control': ('approvals.view',),
}


def _authorize_record_read(db: Session, user, module_slug: str):
    slug = (module_slug or '').strip().lower()
    required = RECORD_READ_PERMISSIONS.get(slug)
    if not required:
        raise HTTPException(status_code=404, detail='Record module not found')
    if getattr(user, 'role', None) in {'owner', 'admin'}:
        return
    effective = get_user_permission_keys(db, user)
    if not any(key in effective for key in required):
        raise HTTPException(status_code=403, detail='Not enough privileges for this record module')


@router.get('/{module_slug}/meta')
def module_meta(module_slug: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _authorize_record_read(db, user, module_slug)
    return {'slug': module_slug, 'name': get_module_name(module_slug), 'taxonomy': get_module_by_slug(module_slug, db)}


@router.get('/{module_slug}/records')
def module_records(module_slug: str, db: Session = Depends(get_db), user=Depends(get_current_user), limit: int = Query(200, ge=1, le=1000), search: str | None = None):
    _authorize_record_read(db, user, module_slug)
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
    current = get_record_obj(db, record_id)
    if not current:
        raise HTTPException(status_code=404, detail='Record not found')
    _authorize_record_read(db, user, current.module_slug)
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
        current = get_record_obj(db, record_id)
        if not current:
            raise HTTPException(status_code=404, detail='Record not found')
        enforce_external_record_ownership(current.module_slug, user)
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
        if not current:
            raise HTTPException(status_code=404, detail='Record not found')
        enforce_external_record_ownership(current.module_slug, user)
        notes = current.notes
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
        current = get_record_obj(db, record_id)
        if not current:
            raise HTTPException(status_code=404, detail='Record not found')
        enforce_external_record_ownership(current.module_slug, user)
        ok = delete_record(db, record_id)
        if not ok:
            raise HTTPException(status_code=404, detail='Record not found')
        return {'ok': True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))