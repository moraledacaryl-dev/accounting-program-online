from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.entities import User
from app.schemas.common import (
    UserCreate,
    UserUpdate,
    LoginPayload,
    TokenOut,
    IntegrationTokenPayload,
)
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    ensure_admin_user,
    ensure_integration_user,
    hash_password,
)
from app.api.deps import get_current_user, require_permissions
from app.core.settings import settings
from app.services.permission_service import assign_user_roles, get_user_effective_permissions, get_user_roles

router = APIRouter()

@router.post('/bootstrap')
def bootstrap(db: Session = Depends(get_db)):
    if not settings.bootstrap_enabled:
        raise HTTPException(status_code=403, detail='Default admin bootstrap is disabled in this environment')
    ensure_admin_user(db)
    if settings.integration_enabled:
        ensure_integration_user(db)
    return {
        'ok': True,
        'default_admin': 'admin',
        'default_password': 'admin123',
        'integration_user': settings.integration_username,
        'integration_password': settings.integration_password,
    }

@router.post('/login')
def login(payload: LoginPayload, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail='Incorrect username or password')
    perms = get_user_effective_permissions(db, user.id)
    return {
        'access_token': create_access_token(user.username),
        'token_type': 'bearer',
        'user': {
            'id': user.id,
            'username': user.username,
            'full_name': user.full_name,
            'role': user.role,
            'roles': perms.get('roles', {}).get('roles', []),
            'permissions': perms.get('permissions', []),
        },
    }

@router.get('/me')
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    perms = get_user_effective_permissions(db, user.id)
    return {
        'id': user.id,
        'username': user.username,
        'full_name': user.full_name,
        'role': user.role,
        'is_active': user.is_active,
        'roles': perms.get('roles', {}).get('roles', []),
        'permissions': perms.get('permissions', []),
    }


@router.post('/integration/token', response_model=TokenOut)
def integration_token(payload: IntegrationTokenPayload, db: Session = Depends(get_db)):
    if not settings.integration_enabled:
        raise HTTPException(status_code=403, detail='Integration tokens are disabled in this environment')
    if settings.is_production and settings.integration_secret in {'', 'pos-integration-secret'}:
        raise HTTPException(status_code=503, detail='Integration secret is not configured for production')
    if payload.secret != settings.integration_secret:
        raise HTTPException(status_code=401, detail='Invalid integration secret')
    ensure_integration_user(db)
    return {'access_token': create_access_token(settings.integration_username)}

@router.get('/users')
def list_users(db: Session = Depends(get_db), user: User = Depends(require_permissions('users.manage'))):
    rows = db.query(User).order_by(User.username.asc()).all()
    out = []
    for row in rows:
        roles = get_user_roles(db, row.id)
        out.append({
            'id': row.id,
            'username': row.username,
            'full_name': row.full_name,
            'role': row.role,
            'is_active': bool(row.is_active),
            'role_ids': roles.get('role_ids', []),
            'roles': roles.get('roles', []),
        })
    return out

@router.post('/users')
def create_user(payload: UserCreate, db: Session = Depends(get_db), user: User = Depends(require_permissions('users.manage'))):
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail='Username already exists')
    obj = User(username=payload.username, full_name=payload.full_name, hashed_password=hash_password(payload.password), role=payload.role, is_active=payload.is_active)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    if payload.role_ids:
        assign_user_roles(db, obj.id, payload.role_ids)
    roles = get_user_roles(db, obj.id)
    return {
        'id': obj.id,
        'username': obj.username,
        'full_name': obj.full_name,
        'role': obj.role,
        'is_active': bool(obj.is_active),
        'role_ids': roles.get('role_ids', []),
        'roles': roles.get('roles', []),
    }

@router.put('/users/{user_id}')
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db), user: User = Depends(require_permissions('users.manage'))):
    obj = db.get(User, user_id)
    if not obj:
        raise HTTPException(status_code=404, detail='User not found')
    data = payload.model_dump(exclude_unset=True)
    if data.get('password'):
        obj.hashed_password = hash_password(data.pop('password'))
    for k, v in data.items():
        if k == 'role_ids':
            continue
        setattr(obj, k, v)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    if payload.role_ids is not None:
        assign_user_roles(db, obj.id, payload.role_ids)
    roles = get_user_roles(db, obj.id)
    return {
        'id': obj.id,
        'username': obj.username,
        'full_name': obj.full_name,
        'role': obj.role,
        'is_active': bool(obj.is_active),
        'role_ids': roles.get('role_ids', []),
        'roles': roles.get('roles', []),
    }
