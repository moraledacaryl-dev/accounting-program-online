from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / 'frontend'


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def test_browser_api_never_reads_or_sends_legacy_bearer_token():
    api_source = _read('frontend/lib/api.js')

    assert 'erp_token' not in api_source
    assert 'localStorage' not in api_source
    assert 'getToken' not in api_source
    assert 'setToken' not in api_source
    assert "headers['Authorization']" not in api_source
    assert 'credentials: \'include\'' in api_source


def test_login_and_logout_use_cookie_session_only():
    login_source = _read('frontend/app/login/page.js')
    header_source = _read('frontend/components/Header.js')

    assert 'clearToken' not in login_source
    assert 'clearToken' not in header_source
    assert 'setToken' not in login_source
    assert 'setToken' not in header_source


def test_existing_legacy_browser_token_is_purged_before_user_bootstrap():
    purge_source = _read('frontend/components/LegacyBrowserCredentialPurge.js')
    layout_source = _read('frontend/app/layout.js')

    assert "LEGACY_BROWSER_TOKEN_KEY = 'erp_token'" in purge_source
    assert 'window.localStorage.removeItem(LEGACY_BROWSER_TOKEN_KEY)' in purge_source
    assert '<LegacyBrowserCredentialPurge />' in layout_source
    assert layout_source.index('<LegacyBrowserCredentialPurge />') < layout_source.index('<CurrentUserProvider>')


def test_legacy_token_key_has_no_other_frontend_references():
    references = []
    for path in FRONTEND.rglob('*'):
        if not path.is_file() or path.suffix not in {'.js', '.jsx', '.ts', '.tsx'}:
            continue
        if path.name == 'LegacyBrowserCredentialPurge.js':
            continue
        if 'erp_token' in path.read_text(encoding='utf-8'):
            references.append(str(path.relative_to(ROOT)))

    assert references == []
