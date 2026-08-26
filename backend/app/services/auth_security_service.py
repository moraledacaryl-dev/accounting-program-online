from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.auth_security import AuthLoginFailure, RevokedAccessToken

LOGIN_FAILURE_WINDOW_SECONDS = 5 * 60
LOGIN_MAX_FAILURES = 8


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def login_failure_key(client_host: str | None, username: str | None) -> str:
    normalized_host = (client_host or 'unknown').strip().lower()
    normalized_username = (username or '').strip().lower()
    material = f'{normalized_host}:{normalized_username}'.encode('utf-8')
    return sha256(material).hexdigest()


def _failure_cutoff(now: datetime | None = None) -> datetime:
    return (now or _utcnow()) - timedelta(seconds=LOGIN_FAILURE_WINDOW_SECONDS)


def recent_login_failure_count(db: Session, key_hash: str, *, now: datetime | None = None) -> int:
    cutoff = _failure_cutoff(now)
    count = db.scalar(
        select(func.count(AuthLoginFailure.id)).where(
            AuthLoginFailure.key_hash == key_hash,
            AuthLoginFailure.attempted_at >= cutoff,
        )
    )
    return int(count or 0)


def record_login_failure(db: Session, key_hash: str, *, attempted_at: datetime | None = None) -> int:
    current = attempted_at or _utcnow()
    db.execute(delete(AuthLoginFailure).where(AuthLoginFailure.attempted_at < _failure_cutoff(current)))
    db.add(AuthLoginFailure(key_hash=key_hash, attempted_at=current))
    db.commit()
    return recent_login_failure_count(db, key_hash, now=current)


def clear_login_failures(db: Session, key_hash: str) -> None:
    db.execute(delete(AuthLoginFailure).where(AuthLoginFailure.key_hash == key_hash))
    db.commit()


def purge_stale_login_failures(db: Session, *, now: datetime | None = None) -> int:
    result = db.execute(delete(AuthLoginFailure).where(AuthLoginFailure.attempted_at < _failure_cutoff(now)))
    db.commit()
    return int(result.rowcount or 0)


def access_token_fingerprint(token: str) -> str:
    return sha256((token or '').encode('utf-8')).hexdigest()


def is_access_token_revoked(db: Session, token: str) -> bool:
    token_hash = access_token_fingerprint(token)
    row = db.scalar(select(RevokedAccessToken.id).where(RevokedAccessToken.token_hash == token_hash))
    return row is not None


def revoke_access_token(
    db: Session,
    token: str,
    *,
    subject: str | None = None,
    expires_at: datetime | None = None,
) -> None:
    current = _utcnow()
    db.execute(
        delete(RevokedAccessToken).where(
            RevokedAccessToken.expires_at.is_not(None),
            RevokedAccessToken.expires_at < current,
        )
    )
    token_hash = access_token_fingerprint(token)
    existing = db.scalar(select(RevokedAccessToken).where(RevokedAccessToken.token_hash == token_hash))
    if existing:
        db.commit()
        return
    db.add(
        RevokedAccessToken(
            token_hash=token_hash,
            subject=(subject or '').strip() or None,
            expires_at=expires_at,
        )
    )
    db.commit()


def purge_expired_revocations(db: Session, *, now: datetime | None = None) -> int:
    current = now or _utcnow()
    result = db.execute(
        delete(RevokedAccessToken).where(
            RevokedAccessToken.expires_at.is_not(None),
            RevokedAccessToken.expires_at < current,
        )
    )
    db.commit()
    return int(result.rowcount or 0)
