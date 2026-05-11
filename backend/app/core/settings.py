from pathlib import Path

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
    trust_proxy_headers: bool = False
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
    def bootstrap_enabled(self) -> bool:
        if not self.allow_default_admin_bootstrap:
            return False
        return self.environment.strip().lower() != 'production'

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == 'production'

settings = Settings()
