from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / 'frontend'


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def _frontend_sources():
    for path in FRONTEND.rglob('*'):
        if path.is_file() and path.suffix in {'.js', '.jsx', '.ts', '.tsx'}:
            yield path


def test_browser_api_never_reads_or_sends_legacy_bearer_token():
    api_source = _read('frontend/lib/api.js')

    assert 'erp_token' not in api_source
    assert 'localStorage' not in api_source
    assert 'getToken' not in api_source
    assert 'setToken' not in api_source
    assert 'clearToken' not in api_source
    assert "headers['Authorization']" not in api_source
    assert 'credentials: \'include\'' in api_source


def test_browser_auth_ui_uses_cookie_session_only():
    for relative_path in (
        'frontend/app/login/page.js',
        'frontend/components/Header.js',
        'frontend/components/AppShell.js',
    ):
        source = _read(relative_path)
        assert 'getToken' not in source
        assert 'setToken' not in source
        assert 'clearToken' not in source


def test_existing_legacy_browser_token_is_purged_before_user_bootstrap():
    purge_source = _read('frontend/components/LegacyBrowserCredentialPurge.js')
    layout_source = _read('frontend/app/layout.js')

    assert "LEGACY_BROWSER_TOKEN_KEY = 'erp_token'" in purge_source
    assert 'window.localStorage.removeItem(LEGACY_BROWSER_TOKEN_KEY)' in purge_source
    assert '<LegacyBrowserCredentialPurge />' in layout_source
    assert layout_source.index('<LegacyBrowserCredentialPurge />') < layout_source.index('<CurrentUserProvider>')


def test_legacy_token_key_has_no_other_frontend_references():
    references = []
    for path in _frontend_sources():
        if path.name == 'LegacyBrowserCredentialPurge.js':
            continue
        if 'erp_token' in path.read_text(encoding='utf-8'):
            references.append(str(path.relative_to(ROOT)))

    assert references == []


def test_legacy_browser_token_helpers_have_no_frontend_callers():
    references = []
    forbidden = ('getToken', 'setToken', 'clearToken')
    for path in _frontend_sources():
        source = path.read_text(encoding='utf-8')
        if any(name in source for name in forbidden):
            references.append(str(path.relative_to(ROOT)))

    assert references == []
