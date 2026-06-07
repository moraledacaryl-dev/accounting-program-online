from hmac import compare_digest

from jose import JWTError, jwt
from fastapi import Cookie, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.settings import settings
from app.db.database import get_db
from app.models.entities import User
from app.services.permission_service import get_user_permission_keys

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)
SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS', 'TRACE'}


def _csrf_tokens_match(cookie_token: str | None, header_token: str | None) -> bool:
    if not cookie_token or not header_token:
        return False
    return compare_digest(str(cookie_token), str(header_token))


def _enforce_cookie_csrf(request: Request, bearer_token: str | None, cookie_token: str | None):
    if bearer_token or not cookie_token or request.method.upper() in SAFE_METHODS:
        return
    csrf_cookie = request.cookies.get(settings.csrf_cookie_name)
    csrf_header = request.headers.get(settings.csrf_header_name)
    if not _csrf_tokens_match(csrf_cookie, csrf_header):
        raise HTTPException(status_code=403, detail='CSRF token missing or invalid')

def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    bearer_token: str | None = Depends(oauth2_scheme),
    cookie_token: str | None = Cookie(default=None, alias=settings.auth_cookie_name),
):
    credentials_exception = HTTPException(status_code=401, detail="Could not validate credentials")
    _enforce_cookie_csrf(request, bearer_token, cookie_token)
    token = bearer_token or cookie_token
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        username = payload.get("sub")
        if not username:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    if not user:
        raise credentials_exception
    return user

def require_roles(*roles):
    def inner(user: User = Depends(get_current_user)):
        if roles and user.role not in roles:
            raise HTTPException(status_code=403, detail="Not enough privileges")
        return user
    return inner


def require_permissions(*permission_keys):
    def inner(
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ):
        if not permission_keys:
            return user
        effective = get_user_permission_keys(db, user)
        missing = [key for key in permission_keys if key not in effective]
        if missing and user.role not in {'owner', 'admin'}:
            raise HTTPException(status_code=403, detail=f"Missing permissions: {', '.join(missing)}")
        return user
    return inner


def require_any_permissions(*permission_keys):
    def inner(
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ):
        if not permission_keys:
            return user
        effective = get_user_permission_keys(db, user)
        if user.role in {'owner', 'admin'}:
            return user
        if any(key in effective for key in permission_keys):
            return user
        raise HTTPException(status_code=403, detail=f"Missing any of permissions: {', '.join(permission_keys)}")
    return inner
