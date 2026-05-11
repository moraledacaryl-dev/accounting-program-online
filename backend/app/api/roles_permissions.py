from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_any_permissions, require_permissions
from app.db.database import get_db
from app.schemas.permissions import (
    RoleCreate,
    RolePermissionUpdate,
    RoleUpdate,
    UserPermissionOverrideUpdate,
    UserRoleAssignment,
)
from app.services.permission_service import (
    assign_user_roles,
    create_role,
    delete_role,
    get_user_effective_permissions,
    get_user_roles,
    list_permissions,
    list_roles,
    set_role_permissions,
    set_user_permission_overrides,
    update_role,
)

router = APIRouter()


@router.get('/permissions')
def get_permissions(
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('roles.manage', 'users.manage')),
):
    return list_permissions(db)


@router.get('/roles')
def get_roles(
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('roles.manage', 'users.manage')),
    active_only: bool = False,
):
    return list_roles(db, active_only=active_only)


@router.post('/roles')
def add_role(
    payload: RoleCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('roles.manage')),
):
    try:
        return create_role(db, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put('/roles/{role_id}')
def edit_role(
    role_id: int,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('roles.manage')),
):
    try:
        return update_role(db, role_id, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete('/roles/{role_id}')
def remove_role(
    role_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('roles.manage')),
):
    try:
        return delete_role(db, role_id)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/roles/{role_id}/permissions')
def update_role_permissions(
    role_id: int,
    payload: RolePermissionUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('roles.manage')),
):
    try:
        return set_role_permissions(db, role_id, payload.permission_keys)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get('/users/{user_id}/roles')
def get_roles_for_user(
    user_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('users.manage', 'roles.manage')),
):
    try:
        return get_user_roles(db, user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post('/users/{user_id}/roles')
def set_roles_for_user(
    user_id: int,
    payload: UserRoleAssignment,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('users.manage')),
):
    try:
        return assign_user_roles(db, user_id, payload.role_ids)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get('/users/{user_id}/permissions')
def get_permissions_for_user(
    user_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('users.manage', 'roles.manage')),
):
    try:
        return get_user_effective_permissions(db, user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post('/users/{user_id}/overrides')
def set_permission_overrides_for_user(
    user_id: int,
    payload: UserPermissionOverrideUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('users.manage')),
):
    try:
        return set_user_permission_overrides(db, user_id, [item.model_dump() for item in payload.overrides])
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
