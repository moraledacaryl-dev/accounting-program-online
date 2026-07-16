from fastapi import HTTPException

from app.api.integration_review import require_service_integration_key
from app.core.settings import settings


def test_service_integration_key_accepts_configured_secret(monkeypatch):
    monkeypatch.setattr(settings, 'environment', 'production')
    monkeypatch.setattr(settings, 'integration_api_key', 'test-integration-key')
    monkeypatch.setattr(settings, 'integration_secret', 'unused-secret')
    assert require_service_integration_key('test-integration-key') is True


def test_service_integration_key_rejects_wrong_secret(monkeypatch):
    monkeypatch.setattr(settings, 'environment', 'production')
    monkeypatch.setattr(settings, 'integration_api_key', 'test-integration-key')
    monkeypatch.setattr(settings, 'integration_secret', 'unused-secret')
    try:
        require_service_integration_key('wrong-key')
    except HTTPException as exc:
        assert exc.status_code == 401
    else:
        raise AssertionError('Wrong integration key should be rejected')


def test_service_integration_key_fails_closed_when_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, 'environment', 'production')
    monkeypatch.setattr(settings, 'integration_api_key', '')
    monkeypatch.setattr(settings, 'integration_secret', 'change-me-shared-secret-later')
    try:
        require_service_integration_key(None)
    except HTTPException as exc:
        assert exc.status_code == 503
    else:
        raise AssertionError('Production service intake must fail closed without a real secret')
