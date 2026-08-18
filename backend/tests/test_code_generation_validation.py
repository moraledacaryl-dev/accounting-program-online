from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.system_settings import get_next_code
from app.db.database import Base
from app.services.system_settings_service import get_code_rule, normalize_system_settings


def make_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    return TestingSession()


def test_get_code_rule_rejects_unknown_entity_with_domain_error():
    settings = normalize_system_settings({})
    with pytest.raises(ValueError, match='Unsupported code entity: not_real_entity'):
        get_code_rule(settings, 'not_real_entity')


def test_next_code_api_converts_unknown_entity_to_http_400():
    db = make_session()
    with pytest.raises(HTTPException) as exc_info:
        get_next_code(
            entity='not_real_entity',
            draft=None,
            db=db,
            user=SimpleNamespace(username='owner', role='owner'),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == 'Unsupported code entity: not_real_entity.'


def test_known_code_entity_still_returns_normalized_rule():
    settings = normalize_system_settings({})
    rule = get_code_rule(settings, 'SUPPLIER')
    assert rule['prefix'] == 'SUP'
    assert rule['digits'] == 4
