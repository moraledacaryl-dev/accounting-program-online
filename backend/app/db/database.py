from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.settings import settings
from app.db import monetary_precision as _monetary_precision  # noqa: F401

database_url = settings.resolved_database_url
connect_args = {'check_same_thread': False} if database_url.startswith('sqlite') else {}
engine = create_engine(database_url, future=True, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
