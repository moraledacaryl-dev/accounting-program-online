from fastapi import HTTPException
from starlette.requests import Request

from app.api.deps import _enforce_cookie_csrf, _select_auth_token
from app.core.settings import settings


def _request(method: str, *, csrf_cookie: str | None = None, csrf_header: str | None = None) -> Request:
    headers = []
    if csrf_cookie is not None:
        headers.append((b'cookie', f'{settings.csrf_cookie_name}={csrf_cookie}'.encode()))
    if csrf_header is not None:
        headers.append((settings.csrf_header_name.lower().encode(), csrf_header.encode()))
    return Request({
        'type': 'http',
        'method': method,
        'scheme': 'https',
        'path': '/api/cashflow/transactions',
        'raw_path': b'/api/cashflow/transactions',
        'query_string': b'',
        'headers': headers,
        'client': ('127.0.0.1', 12345),
        'server': ('accounting.hiddenoasis.app', 443),
    })


def test_cookie_session_wins_when_cookie_and_bearer_are_both_present():
    assert _select_auth_token('cookie-session', 'stale-browser-bearer') == 'cookie-session'
    assert _select_auth_token(None, 'service-bearer') == 'service-bearer'
    assert _select_auth_token('cookie-session', None) == 'cookie-session'
    assert _select_auth_token(None, None) is None


def test_mixed_cookie_and_bearer_does_not_bypass_cookie_csrf():
    request = _request('POST')
    try:
        _enforce_cookie_csrf(request, 'stale-browser-bearer', 'cookie-session')
    except HTTPException as exc:
        assert exc.status_code == 403
        assert exc.detail == 'CSRF token missing or invalid'
    else:
        raise AssertionError('Mixed cookie + bearer request bypassed cookie CSRF enforcement')


def test_mixed_cookie_and_bearer_accepts_matching_csrf_pair():
    request = _request('POST', csrf_cookie='csrf-proof', csrf_header='csrf-proof')
    _enforce_cookie_csrf(request, 'stale-browser-bearer', 'cookie-session')


def test_pure_bearer_request_remains_available_for_non_browser_clients():
    request = _request('POST')
    _enforce_cookie_csrf(request, 'service-bearer', None)


def test_safe_cookie_request_does_not_require_csrf_header():
    request = _request('GET')
    _enforce_cookie_csrf(request, None, 'cookie-session')
