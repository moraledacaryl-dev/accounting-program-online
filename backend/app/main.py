from __future__ import annotations

from contextlib import asynccontextmanager
import shutil
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import api_router
from app.api.deps import require_roles
from app.core.logging_security import install_sensitive_access_log_filter
from app.core.migrations import ensure_database_ready, migration_status
from app.core.settings import settings
from app.db.database import SessionLocal, engine
from app.db.schema_migration import run_startup_migrations
from app.services.operations_outbox_service import operations_outbox_status
import app.models  # noqa: F401


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        response.headers['X-Request-ID'] = uuid4().hex
        if settings.is_production:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_production_security()
    install_sensitive_access_log_filter()
    ensure_database_ready(engine)
    run_startup_migrations(engine)
    yield


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    docs_url=None if settings.is_production else '/docs',
    redoc_url=None if settings.is_production else '/redoc',
    openapi_url=None if settings.is_production else '/openapi.json',
)
allowed_origins = settings.cors_origin_list or ['*']
allow_credentials = '*' not in allowed_origins

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=allow_credentials,
    allow_methods=['*'],
    allow_headers=['*'],
)

UPLOAD_ROOT = settings.uploads_path
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
if settings.public_uploads_enabled:
    app.mount('/uploads', StaticFiles(directory=str(UPLOAD_ROOT)), name='uploads')


@app.get('/')
def root():
    return {'app': settings.app_name, 'status': 'ok'}


@app.get('/healthz')
def healthz():
    return {'ok': True}


@app.get('/api/healthz')
def api_healthz():
    return healthz()


def _healthz_details_payload():
    db_ok = False
    migration = None
    outbox = None
    try:
        with SessionLocal() as db:
            db.execute(text('SELECT 1'))
            outbox = operations_outbox_status(db)
        db_ok = True
        migration = migration_status(engine)
    except Exception:
        db_ok = False
    scanner_available = bool(shutil.which('clamscan'))
    scanner_required = settings.is_production
    scanner_ok = scanner_available or not scanner_required
    outbox_ok = bool(outbox is None or outbox.get('healthy', False))
    return {
        'ok': db_ok and (not migration or bool(migration.get('ok', True))) and scanner_ok and outbox_ok,
        'database': 'ok' if db_ok else 'error',
        'migration': migration,
        'uploads': UPLOAD_ROOT.exists(),
        'attachment_scanner': {
            'required': scanner_required,
            'available': scanner_available,
            'ok': scanner_ok,
        },
        'operations_outbox': outbox,
    }


@app.get('/healthz/details')
def healthz_details(user=Depends(require_roles('owner', 'admin'))):
    return _healthz_details_payload()


@app.get('/api/healthz/details')
def api_healthz_details(user=Depends(require_roles('owner', 'admin'))):
    return _healthz_details_payload()


app.include_router(api_router, prefix=settings.api_prefix)
