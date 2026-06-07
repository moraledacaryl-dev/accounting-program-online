from pathlib import Path
import re

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_PATH = BACKEND_ROOT / 'accounting.db'


def _default_database_url() -> str:
    return f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"


def _resolve_sqlite_url(url: str) -> str:
    prefix = 'sqlite:///./'
    if not url.startswith(prefix):
        return url
    relative_path = url[len(prefix):]
    resolved_path = (BACKEND_ROOT / relative_path).resolve()
    return f"sqlite:///{resolved_path.as_posix()}"


_KNOWN_PLACEHOLDER_SECRETS = {
    '',
    'admin123',
    'changemesupersecret',
    'changemegeneratewithopensslrandhex32',
    'changemeerpdbpassword',
    'changemesharedsecretlater',
    'changemesharedposaccountingintegrationsecret',
    'changemestrongintegrationuserpassword',
    'default',
    'password',
    'placeholder',
    'pos1234',
    'posintegrationsecret',
    'secret',
}


def _compact_secret(value: str | None) -> str:
    return re.sub(r'[^a-z0-9]+', '', (value or '').strip().lower())


def looks_like_placeholder_secret(value: str | None) -> bool:
    compact = _compact_secret(value)
    if compact in _KNOWN_PLACEHOLDER_SECRETS:
        return True
    return compact.startswith(('changeme', 'replacewith', 'replace', 'todo'))

class Settings(BaseSettings):
    app_name: str = 'Resort Accounting ERP'
    environment: str = 'development'
    api_prefix: str = '/api'
    database_url: str = _default_database_url()
    secret_key: str = 'change-me-super-secret'
    access_token_expire_minutes: int = 60 * 24
    allow_default_admin_bootstrap: bool = True
    allow_demo_seed: bool = False
    integration_enabled: bool = True
    integration_username: str = 'pos_integration'
    integration_password: str = 'pos1234'
    integration_secret: str = 'pos-integration-secret'
    cors_origins: str = 'http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001'
    uploads_dir: str = str(BACKEND_ROOT / 'uploads')
    public_uploads_enabled: bool = False
    auth_cookie_name: str = 'erp_session'
    auth_cookie_domain: str = ''
    auth_cookie_samesite: str = 'lax'
    auth_cookie_secure: bool | None = None
    csrf_cookie_name: str = 'erp_csrf'
    csrf_header_name: str = 'x-csrf-token'
    trust_proxy_headers: bool = False
    startup_require_migrations: bool = True
    model_config = SettingsConfigDict(env_file=str(BACKEND_ROOT / '.env'), extra='ignore')

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(',') if origin.strip()]

    @property
    def resolved_database_url(self) -> str:
        return _resolve_sqlite_url(self.database_url)

    @property
    def uploads_path(self) -> Path:
        return Path(self.uploads_dir).expanduser().resolve()

    @property
    def auth_cookie_secure_effective(self) -> bool:
        if self.auth_cookie_secure is not None:
            return bool(self.auth_cookie_secure)
        return self.is_production

    @property
    def auth_cookie_domain_value(self) -> str | None:
        value = (self.auth_cookie_domain or '').strip()
        return value or None

    @property
    def auth_cookie_samesite_value(self) -> str:
        value = (self.auth_cookie_samesite or 'lax').strip().lower()
        return value if value in {'lax', 'strict', 'none'} else 'lax'

    @property
    def bootstrap_enabled(self) -> bool:
        if not self.allow_default_admin_bootstrap:
            return False
        return self.environment.strip().lower() != 'production'

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == 'production'

    @property
    def secret_key_is_placeholder(self) -> bool:
        return looks_like_placeholder_secret(self.secret_key)

    @property
    def integration_secret_is_placeholder(self) -> bool:
        return looks_like_placeholder_secret(self.integration_secret)

    @property
    def integration_password_is_placeholder(self) -> bool:
        return looks_like_placeholder_secret(self.integration_password)

    @property
    def security_warnings(self) -> list[str]:
        warnings: list[str] = []
        if self.secret_key_is_placeholder:
            warnings.append('SECRET_KEY is unset or still using a placeholder value.')
        if self.integration_enabled and self.integration_secret_is_placeholder:
            warnings.append('INTEGRATION_SECRET is unset or still using a placeholder value.')
        if self.integration_enabled and self.integration_password_is_placeholder:
            warnings.append('INTEGRATION_PASSWORD is unset or still using a placeholder value.')
        if self.is_production and self.allow_default_admin_bootstrap:
            warnings.append('ALLOW_DEFAULT_ADMIN_BOOTSTRAP should be false in production.')
        return warnings

settings = Settings()
