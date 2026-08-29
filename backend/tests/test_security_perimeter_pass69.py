from __future__ import annotations

import logging
from pathlib import Path

from app.api.integrations_beds24 import _credential_safe_settings, _preserve_blank_credentials
from app.core.logging_security import SensitiveQueryAccessLogFilter, redact_sensitive_query


def test_sensitive_query_redaction_masks_secret_like_values():
    raw = '/api/integrations/beds24/webhook?secret=super-secret&foo=ok&token=abc123'
    redacted = redact_sensitive_query(raw)

    assert 'super-secret' not in redacted
    assert 'abc123' not in redacted
    assert 'foo=ok' in redacted
    assert '%5BREDACTED%5D' in redacted


def test_uvicorn_access_log_filter_redacts_path_argument():
    record = logging.LogRecord(
        name='uvicorn.access',
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=(
            '127.0.0.1:12345',
            'POST',
            '/api/integrations/beds24/webhook?secret=should-not-log&x=1',
            '1.1',
            400,
        ),
        exc_info=None,
    )

    assert SensitiveQueryAccessLogFilter().filter(record) is True
    rendered = record.getMessage()
    assert 'should-not-log' not in rendered
    assert 'x=1' in rendered
    assert 'REDACTED' in rendered


def test_beds24_webhook_no_longer_authenticates_query_secret():
    root = Path(__file__).resolve().parents[1]
    source = (root / 'app/api/integrations_beds24.py').read_text(encoding='utf-8')

    assert "if 'secret' in request.query_params" in source
    assert 'query_secret=None' in source
    assert 'secret: str | None = None' not in source
    assert 'query_secret=secret' not in source
    assert "detail='Beds24 webhook processing failed.'" in source


def test_beds24_settings_never_return_stored_credentials():
    safe = _credential_safe_settings(
        {
            'enabled': True,
            'access_token': 'access-secret',
            'refresh_token': 'refresh-secret',
            'invite_code': 'invite-secret',
            'webhook_secret': 'webhook-secret',
        }
    )

    for key in ('access_token', 'refresh_token', 'invite_code', 'webhook_secret'):
        assert safe[key] == ''
        assert safe[f'{key}_configured'] is True
    rendered = repr(safe)
    assert 'access-secret' not in rendered
    assert 'refresh-secret' not in rendered
    assert 'invite-secret' not in rendered
    assert 'webhook-secret' not in rendered


def test_blank_beds24_credentials_preserve_existing_values_on_save():
    payload = _preserve_blank_credentials(
        {
            'enabled': True,
            'access_token': '',
            'refresh_token': '   ',
            'webhook_secret': 'replacement-secret',
        }
    )

    assert 'access_token' not in payload
    assert 'refresh_token' not in payload
    assert payload['webhook_secret'] == 'replacement-secret'
    assert payload['enabled'] is True


def test_detailed_health_requires_privileged_auth_and_includes_outbox_health():
    root = Path(__file__).resolve().parents[1]
    source = (root / 'app/main.py').read_text(encoding='utf-8')

    assert "Depends(require_roles('owner', 'admin'))" in source
    assert "@app.get('/healthz/details')" in source
    assert "@app.get('/api/healthz/details')" in source
    assert "'operations_outbox': outbox" in source
    assert "openapi_url=None if settings.is_production" in source
    assert "docs_url=None if settings.is_production" in source


def test_backend_security_headers_are_mandatory():
    root = Path(__file__).resolve().parents[1]
    source = (root / 'app/main.py').read_text(encoding='utf-8')

    for header in (
        'X-Content-Type-Options',
        'X-Frame-Options',
        'Referrer-Policy',
        'Permissions-Policy',
        'Cross-Origin-Opener-Policy',
        'Content-Security-Policy',
        'Strict-Transport-Security',
        'X-Request-ID',
    ):
        assert header in source


def test_nextjs_framework_banner_disabled_and_security_headers_configured():
    root = Path(__file__).resolve().parents[2]
    source = (root / 'frontend/next.config.js').read_text(encoding='utf-8')

    assert 'poweredByHeader: false' in source
    for header in (
        'X-Content-Type-Options',
        'X-Frame-Options',
        'Referrer-Policy',
        'Permissions-Policy',
        'Cross-Origin-Opener-Policy',
        'Strict-Transport-Security',
    ):
        assert header in source
