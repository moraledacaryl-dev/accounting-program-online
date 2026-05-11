
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from sqlalchemy import text
from app.api import api_router
from app.core.settings import settings
from app.db.database import Base, SessionLocal, engine
from app.db.schema_migration import run_startup_migrations
import app.models  # noqa: F401

run_startup_migrations(engine)
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name)
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
app.mount('/uploads', StaticFiles(directory=str(UPLOAD_ROOT)), name='uploads')

@app.get('/')
def root():
    return {'app': settings.app_name, 'status': 'ok'}

@app.get('/healthz')
def healthz():
    return {'ok': True, 'environment': settings.environment}

@app.get('/healthz/details')
def healthz_details():
    db_ok = False
    try:
        with SessionLocal() as db:
            db.execute(text('SELECT 1'))
        db_ok = True
    except Exception:
        db_ok = False
    return {
        'ok': db_ok,
        'environment': settings.environment,
        'database': 'ok' if db_ok else 'error',
        'uploads': UPLOAD_ROOT.exists(),
    }

app.include_router(api_router, prefix=settings.api_prefix)
