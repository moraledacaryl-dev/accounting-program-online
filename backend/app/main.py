
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from app.api import api_router
from app.core.migrations import ensure_database_ready, migration_status
from app.core.settings import settings
from app.db.database import SessionLocal, engine
from app.db.schema_migration import run_startup_migrations
import app.models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_database_ready(engine)
    run_startup_migrations(engine)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
allowed_origins = settings.cors_origin_list or ['*']
allow_credentials = '*' not in allowed_origins

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
    return {'ok': True, 'environment': settings.environment}

@app.get('/api/healthz')
def api_healthz():
    return healthz()

@app.get('/healthz/details')
def healthz_details():
    db_ok = False
    migration = None
    try:
        with SessionLocal() as db:
            db.execute(text('SELECT 1'))
        db_ok = True
        migration = migration_status(engine)
    except Exception:
        db_ok = False
    return {
        'ok': db_ok and (not migration or bool(migration.get('ok', True))),
        'environment': settings.environment,
        'database': 'ok' if db_ok else 'error',
        'migration': migration,
        'uploads': UPLOAD_ROOT.exists(),
    }

@app.get('/api/healthz/details')
def api_healthz_details():
    return healthz_details()

app.include_router(api_router, prefix=settings.api_prefix)
