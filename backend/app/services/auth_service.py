from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.core.settings import settings
from app.models.entities import User
from app.services.permission_service import assign_user_roles, ensure_permissions_seed, list_roles

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": subject, "exp": expire}, settings.secret_key, algorithm=ALGORITHM)

def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def ensure_integration_user(db: Session):
    if not settings.integration_enabled:
        return None
    integration_username = settings.integration_username
    integration_user = db.query(User).filter(User.username == integration_username).first()
    if not integration_user:
        integration_user = User(
            username=integration_username,
            full_name='POS Integration Service',
            hashed_password=hash_password(settings.integration_password),
            role='admin',
            is_active=True,
        )
        db.add(integration_user)
        db.commit()
        db.refresh(integration_user)
    else:
        if not integration_user.is_active:
            integration_user.is_active = True
            db.add(integration_user)
            db.commit()
            db.refresh(integration_user)
    return integration_user


def ensure_admin_user(db: Session):
    ensure_permissions_seed(db)
    admin = db.query(User).filter(User.username == 'admin').first()
    if not admin:
        admin = User(username='admin', full_name='System Admin', hashed_password=hash_password('admin123'), role='admin', is_active=True)
        db.add(admin)
        db.commit()
        db.refresh(admin)
    roles = list_roles(db)
    owner_role = next((row for row in roles if row.get('code') == 'owner'), None)
    if owner_role:
        assign_user_roles(db, admin.id, [int(owner_role['id'])])
