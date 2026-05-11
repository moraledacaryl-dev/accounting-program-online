from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_any_permissions, require_permissions
from app.db.database import get_db
from app.schemas.system_settings import CodePreviewOut, SystemSettingsPayload, UserDashboardOverridePayload
from app.services.code_service import generate_code
from app.services.permission_service import get_user_permission_keys
from app.services.system_settings_service import (
    load_system_settings,
    save_system_settings,
    set_user_dashboard_override,
    settings_meta,
)

router = APIRouter()


@router.get('/')
def get_system_settings(
    db: Session = Depends(get_db),
    user=Depends(require_permissions('system_settings.manage')),
):
    return {
        'settings': load_system_settings(db),
        'meta': settings_meta(),
    }


@router.put('/')
def update_system_settings(
    payload: SystemSettingsPayload,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('system_settings.manage')),
):
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return {
            'settings': load_system_settings(db),
            'meta': settings_meta(),
        }
    try:
        settings = save_system_settings(db, data, updated_by=getattr(user, 'username', None))
        return {
            'settings': settings,
            'meta': settings_meta(),
        }
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get('/next-code', response_model=CodePreviewOut)
def get_next_code(
    entity: str,
    draft: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(
        require_any_permissions(
            'room_setup.manage',
            'suppliers.manage',
            'purchase_requests.create',
            'purchase_orders.create',
            'receiving.post',
            'chart_of_accounts.manage',
            'cashflow.view',
            'assets.manage',
            'system_settings.manage',
        )
    ),
):
    try:
        code = generate_code(db, entity, requested_code=draft)
        return {'entity': entity, 'code': code}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/dashboard/user-override')
def save_dashboard_user_override(
    payload: UserDashboardOverridePayload,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('dashboard.view')),
):
    effective_keys = get_user_permission_keys(db, user)
    can_manage = 'system_settings.manage' in effective_keys or getattr(user, 'role', '') in {'owner', 'admin'}
    if int(payload.user_id) != int(user.id) and not can_manage:
        raise HTTPException(status_code=403, detail='Not allowed to edit dashboard override for other users.')

    settings = set_user_dashboard_override(
        db,
        user_id=int(payload.user_id),
        widgets=payload.widgets,
        updated_by=getattr(user, 'username', None),
    )
    return {
        'settings': settings,
        'meta': settings_meta(),
    }
