from pathlib import Path
import re

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_PATH = BACKEND_ROOT / 'accounting.db'
DEFAULT_UPLOADS_PATH = BACKEND_ROOT / 'uploads'
PRODUCTION_UPLOADS_PATH = Path('/var/lib/hiddenoasis/accounting/uploads')
MINIMUM_SECRET_LENGTH = 32


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


def secret_is_too_short(value: str | None) -> bool:
    return len((value or '').strip()) < MINIMUM_SECRET_LENGTH


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
    integration_api_key: str = ''
    cors_origins: str = 'http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001'
    uploads_dir: str = str(DEFAULT_UPLOADS_PATH)
    public_uploads_enabled: bool = False
    auth_cookie_name: str = 'erp_session'
    auth_cookie_domain: str = ''
    auth_cookie_samesite: str = 'lax'
    auth_cookie_secure: bool | None = None
    csrf_cookie_name: str = 'erp_csrf'
    csrf_header_name: str = 'x-csrf-token'
    trust_proxy_headers: bool = False
    startup_require_migrations: bool = True
    operations_integration_enabled: bool = False
    operations_api_base: str = 'https://operations.hiddenoasis.app/api'
    operations_integration_key: str = ''
    operations_source_app: str = 'accounting_program'
    operations_integration_timeout_seconds: int = 5
    operations_reconciliation_variance_threshold: float = 1.0
    model_config = SettingsConfigDict(env_file=str(BACKEND_ROOT / '.env'), extra='ignore')

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(',') if origin.strip()]

    @property
    def resolved_database_url(self) -> str:
        return _resolve_sqlite_url(self.database_url)

    @property
    def uploads_path(self) -> Path:
        configured = Path(self.uploads_dir).expanduser().resolve()
        if self.is_production and configured == DEFAULT_UPLOADS_PATH.resolve():
            return PRODUCTION_UPLOADS_PATH
        return configured

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
        return not self.is_production

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == 'production'

    @property
    def secret_key_is_placeholder(self) -> bool:
        return looks_like_placeholder_secret(self.secret_key)

    @property
    def integration_secret_is_placeholder(self) -> bool:
        return looks_like_placeholder_secret(self.integration_receive_secret)

    @property
    def integration_receive_secret(self) -> str:
        return (self.integration_api_key or self.integration_secret or '').strip()

    @property
    def integration_password_is_placeholder(self) -> bool:
        return looks_like_placeholder_secret(self.integration_password)

    @property
    def security_warnings(self) -> list[str]:
        warnings: list[str] = []
        if self.secret_key_is_placeholder:
            warnings.append('SECRET_KEY is unset or still using a placeholder value.')
        elif secret_is_too_short(self.secret_key):
            warnings.append(f'SECRET_KEY must be at least {MINIMUM_SECRET_LENGTH} characters.')
        if self.integration_enabled and self.integration_secret_is_placeholder:
            warnings.append('INTEGRATION_SECRET is unset or still using a placeholder value.')
        elif self.integration_enabled and secret_is_too_short(self.integration_receive_secret):
            warnings.append(f'INTEGRATION_SECRET must be at least {MINIMUM_SECRET_LENGTH} characters.')
        if self.integration_enabled and self.integration_password_is_placeholder:
            warnings.append('INTEGRATION_PASSWORD is unset or still using a placeholder value.')
        elif self.integration_enabled and secret_is_too_short(self.integration_password):
            warnings.append(f'INTEGRATION_PASSWORD must be at least {MINIMUM_SECRET_LENGTH} characters.')
        if self.is_production and self.allow_default_admin_bootstrap:
            warnings.append('ALLOW_DEFAULT_ADMIN_BOOTSTRAP must be false in production.')
        if self.is_production and not self.auth_cookie_secure_effective:
            warnings.append('AUTH_COOKIE_SECURE must be true in production.')
        if self.is_production and not self.cors_origin_list:
            warnings.append('CORS_ORIGINS must contain at least one explicit production origin.')
        if self.is_production and '*' in self.cors_origin_list:
            warnings.append('Wildcard CORS origins are not allowed in production.')
        if self.auth_cookie_samesite_value == 'none' and not self.auth_cookie_secure_effective:
            warnings.append('SameSite=None cookies require AUTH_COOKIE_SECURE=true.')
        return warnings

    def validate_production_security(self) -> None:
        if not self.is_production:
            return
        warnings = self.security_warnings
        if warnings:
            formatted = '\n - '.join(warnings)
            raise RuntimeError(f'Unsafe production configuration:\n - {formatted}')


settings = Settings()