import secrets
from time import monotonic

from fastapi import APIRouter, Depends, HTTPException, Request, Response
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

LOGIN_FAILURE_WINDOW_SECONDS = 5 * 60
LOGIN_MAX_FAILURES = 8
_login_failures: dict[str, list[float]] = {}


def _login_failure_key(request: Request, username: str) -> str:
    client_host = request.client.host if request.client else 'unknown'
    normalized_username = (username or '').strip().lower()
    return f'{client_host}:{normalized_username}'


def _recent_login_failures(key: str) -> list[float]:
    cutoff = monotonic() - LOGIN_FAILURE_WINDOW_SECONDS
    recent = [stamp for stamp in _login_failures.get(key, []) if stamp >= cutoff]
    if recent:
        _login_failures[key] = recent
    else:
        _login_failures.pop(key, None)
    return recent


def _assert_login_allowed(key: str):
    if len(_recent_login_failures(key)) >= LOGIN_MAX_FAILURES:
        raise HTTPException(status_code=429, detail='Too many failed login attempts. Please wait a few minutes and try again.')


def _record_login_failure(key: str):
    recent = _recent_login_failures(key)
    recent.append(monotonic())
    _login_failures[key] = recent


def _clear_login_failures(key: str):
    _login_failures.pop(key, None)


def _set_session_cookie(response: Response, token: str):
    max_age = int(settings.access_token_expire_minutes) * 60
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=max_age,
        expires=max_age,
        path='/',
        domain=settings.auth_cookie_domain_value,
        secure=settings.auth_cookie_secure_effective,
        httponly=True,
        samesite=settings.auth_cookie_samesite_value,
    )


def _set_csrf_cookie(response: Response) -> str:
    token = secrets.token_urlsafe(32)
    max_age = int(settings.access_token_expire_minutes) * 60
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=token,
        max_age=max_age,
        expires=max_age,
        path='/',
        domain=settings.auth_cookie_domain_value,
        secure=settings.auth_cookie_secure_effective,
        httponly=False,
        samesite=settings.auth_cookie_samesite_value,
    )
    return token


def _clear_session_cookie(response: Response):
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path='/',
        domain=settings.auth_cookie_domain_value,
        secure=settings.auth_cookie_secure_effective,
        httponly=True,
        samesite=settings.auth_cookie_samesite_value,
    )
    response.delete_cookie(
        key=settings.csrf_cookie_name,
        path='/',
        domain=settings.auth_cookie_domain_value,
        secure=settings.auth_cookie_secure_effective,
        httponly=False,
        samesite=settings.auth_cookie_samesite_value,
    )

@router.post('/bootstrap')
def bootstrap(db: Session = Depends(get_db)):
    if not settings.bootstrap_enabled:
        raise HTTPException(status_code=403, detail='Default admin bootstrap is disabled in this environment')
    admin_result = ensure_admin_user(db)
    if settings.integration_enabled:
        ensure_integration_user(db)
    response = {
        'ok': True,
        'admin_username': 'admin',
        'admin_created': bool(admin_result.get('created')),
        'integration_user': settings.integration_username,
        'integration_user_ready': bool(settings.integration_enabled),
        'message': 'Admin bootstrap is ready. Store the temporary password now if one was generated.',
    }
    if admin_result.get('temporary_password'):
        response['temporary_password'] = admin_result['temporary_password']
        response['temporary_password_shown_once'] = True
    return response

@router.post('/login')
def login(payload: LoginPayload, request: Request, response: Response, db: Session = Depends(get_db)):
    failure_key = _login_failure_key(request, payload.username)
    _assert_login_allowed(failure_key)
    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        _record_login_failure(failure_key)
        raise HTTPException(status_code=401, detail='Incorrect username or password')
    _clear_login_failures(failure_key)
    perms = get_user_effective_permissions(db, user.id)
    token = create_access_token(user.username)
    _set_session_cookie(response, token)
    csrf_token = _set_csrf_cookie(response)
    return {
        'access_token': token,
        'token_type': 'bearer',
        'csrf_token': csrf_token,
        'user': {
            'id': user.id,
            'username': user.username,
            'full_name': user.full_name,
            'role': user.role,
            'roles': perms.get('roles', {}).get('roles', []),
            'permissions': perms.get('permissions', []),
        },
    }


@router.post('/logout')
def logout(response: Response, user: User = Depends(get_current_user)):
    _clear_session_cookie(response)
    return {'ok': True}


@router.get('/csrf')
def csrf(response: Response, user: User = Depends(get_current_user)):
    return {'csrf_token': _set_csrf_cookie(response)}


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
    if settings.is_production and settings.integration_secret_is_placeholder:
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
