from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Response
import jwt
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from app.api.auth import LOGIN_MAX_FAILURES, login, logout
from app.api.deps import get_current_user
from app.core.settings import settings
from app.db.database import Base
from app.models.auth_security import RevokedAccessToken
from app.models.entities import User
from app.schemas.common import LoginPayload
from app.services.auth_security_service import (
    access_token_fingerprint,
    login_failure_key,
    recent_login_failure_count,
)
from app.services.auth_service import ALGORITHM, create_access_token, hash_password


def make_database(tmp_path):
    path = tmp_path / 'auth-security.db'
    engine = create_engine(f'sqlite:///{path}', future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def make_request(method='POST', path='/api/auth/login', *, token=None, host='203.0.113.10'):
    headers = []
    if token:
        headers.append((b'authorization', f'Bearer {token}'.encode()))
    return Request({
        'type': 'http',
        'method': method,
        'scheme': 'https',
        'server': ('accounting.hiddenoasis.app', 443),
        'client': (host, 12345),
        'root_path': '',
        'path': path,
        'raw_path': path.encode(),
        'query_string': b'',
        'headers': headers,
    })


def add_user(db, username='shared-owner', password='correct-password'):
    user = User(
        username=username,
        full_name='Shared Owner',
        hashed_password=hash_password(password),
        role='owner',
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_login_failures_survive_new_database_sessions_and_rate_limit(tmp_path):
    Session = make_database(tmp_path)
    payload = LoginPayload(username='missing-user', password='wrong-password')
    request = make_request()

    for _ in range(LOGIN_MAX_FAILURES):
        with Session() as db:
            with pytest.raises(HTTPException) as exc_info:
                login(payload, request, Response(), db)
            assert exc_info.value.status_code == 401

    with Session() as db:
        key_hash = login_failure_key('203.0.113.10', 'missing-user')
        assert recent_login_failure_count(db, key_hash) == LOGIN_MAX_FAILURES
        with pytest.raises(HTTPException) as exc_info:
            login(payload, request, Response(), db)
        assert exc_info.value.status_code == 429


def test_successful_login_clears_shared_failure_state(tmp_path):
    Session = make_database(tmp_path)
    with Session() as db:
        add_user(db)

    request = make_request()
    for _ in range(3):
        with Session() as db:
            with pytest.raises(HTTPException):
                login(LoginPayload(username='shared-owner', password='wrong'), request, Response(), db)

    with Session() as db:
        result = login(LoginPayload(username='shared-owner', password='correct-password'), request, Response(), db)
        assert result['access_token']

    with Session() as db:
        key_hash = login_failure_key('203.0.113.10', 'shared-owner')
        assert recent_login_failure_count(db, key_hash) == 0


def test_logout_revokes_exact_bearer_token_across_sessions(tmp_path):
    Session = make_database(tmp_path)
    with Session() as db:
        user = add_user(db)
        token = create_access_token(user.username)
        authenticated = get_current_user(
            make_request('GET', '/api/auth/me', token=token),
            db=db,
            bearer_token=token,
            cookie_token=None,
        )
        assert authenticated.username == user.username

        result = logout(
            make_request('POST', '/api/auth/logout', token=token),
            Response(),
            db,
            user,
        )
        assert result == {'ok': True}

    with Session() as db:
        revoked = db.scalar(select(RevokedAccessToken).where(RevokedAccessToken.token_hash == access_token_fingerprint(token)))
        assert revoked is not None
        assert revoked.token_hash != token

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(
                make_request('GET', '/api/auth/me', token=token),
                db=db,
                bearer_token=token,
                cookie_token=None,
            )
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == 'Could not validate credentials'


def test_revoking_one_session_does_not_revoke_another_for_same_user(tmp_path):
    Session = make_database(tmp_path)
    with Session() as db:
        user = add_user(db)
        revoked_token = create_access_token(user.username)
        other_token = create_access_token(user.username)
        assert other_token != revoked_token

        logout(make_request('POST', '/api/auth/logout', token=revoked_token), Response(), db, user)

    with Session() as db:
        authenticated = get_current_user(
            make_request('GET', '/api/auth/me', token=other_token),
            db=db,
            bearer_token=other_token,
            cookie_token=None,
        )
        assert authenticated.username == 'shared-owner'


def test_legacy_hs256_token_without_jti_remains_valid_and_revocable(tmp_path):
    Session = make_database(tmp_path)
    legacy_token = jwt.encode(
        {
            'sub': 'shared-owner',
            'exp': datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        settings.secret_key,
        algorithm=ALGORITHM,
    )

    with Session() as db:
        user = add_user(db)
        authenticated = get_current_user(
            make_request('GET', '/api/auth/me', token=legacy_token),
            db=db,
            bearer_token=legacy_token,
            cookie_token=None,
        )
        assert authenticated.username == user.username
        logout(make_request('POST', '/api/auth/logout', token=legacy_token), Response(), db, user)

    with Session() as db:
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(
                make_request('GET', '/api/auth/me', token=legacy_token),
                db=db,
                bearer_token=legacy_token,
                cookie_token=None,
            )
        assert exc_info.value.status_code == 401
