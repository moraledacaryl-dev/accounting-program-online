from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from app.api.auth import login
from app.api.deps import get_current_user
from app.core.settings import settings
from app.db.database import Base
from app.models.entities import User
from app.schemas.common import LoginPayload
from app.services.auth_service import ALGORITHM, create_access_token, decode_access_token, hash_password


def make_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    return TestingSession()


def make_request(method='GET', path='/api/auth/me'):
    return Request({
        'type': 'http',
        'method': method,
        'scheme': 'https',
        'server': ('accounting.hiddenoasis.app', 443),
        'client': ('127.0.0.1', 10000),
        'root_path': '',
        'path': path,
        'raw_path': path.encode(),
        'query_string': b'',
        'headers': [],
    })


def add_user(db, username='jwt-owner', password='correct-password'):
    user = User(
        username=username,
        full_name='JWT Owner',
        hashed_password=hash_password(password),
        role='owner',
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_pyjwt_create_and_decode_preserves_subject():
    token = create_access_token('jwt-subject')
    payload = decode_access_token(token)
    assert payload['sub'] == 'jwt-subject'
    assert 'exp' in payload


def test_login_token_authenticates_follow_up_api_access():
    db = make_session()
    user = add_user(db)
    response = Response()

    result = login(
        LoginPayload(username=user.username, password='correct-password'),
        make_request('POST', '/api/auth/login'),
        response,
        db,
    )

    token = result['access_token']
    authenticated = get_current_user(
        make_request('GET', '/api/auth/me'),
        db=db,
        bearer_token=token,
        cookie_token=None,
    )

    assert authenticated.id == user.id
    assert authenticated.username == user.username
    assert result['token_type'] == 'bearer'
    assert response.headers.get('set-cookie')


def test_invalid_signature_is_rejected_as_401():
    db = make_session()
    add_user(db)
    token = jwt.encode(
        {'sub': 'jwt-owner', 'exp': datetime.now(timezone.utc) + timedelta(minutes=5)},
        'definitely-not-the-accounting-secret',
        algorithm=ALGORITHM,
    )

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(
            make_request(),
            db=db,
            bearer_token=token,
            cookie_token=None,
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == 'Could not validate credentials'


def test_expired_token_is_rejected_as_401():
    db = make_session()
    add_user(db)
    token = jwt.encode(
        {'sub': 'jwt-owner', 'exp': datetime.now(timezone.utc) - timedelta(seconds=1)},
        settings.secret_key,
        algorithm=ALGORITHM,
    )

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(
            make_request(),
            db=db,
            bearer_token=token,
            cookie_token=None,
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == 'Could not validate credentials'


def test_token_without_subject_is_rejected_as_401():
    db = make_session()
    token = jwt.encode(
        {'exp': datetime.now(timezone.utc) + timedelta(minutes=5)},
        settings.secret_key,
        algorithm=ALGORITHM,
    )

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(
            make_request(),
            db=db,
            bearer_token=token,
            cookie_token=None,
        )

    assert exc_info.value.status_code == 401
