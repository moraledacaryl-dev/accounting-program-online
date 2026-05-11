from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.settings import settings
from app.db.database import get_db
from app.services.seed_service import seed_demo_data
from app.services.auth_service import ensure_admin_user

router = APIRouter()

@router.post('/demo')
def seed_demo(db: Session = Depends(get_db)):
    if not settings.allow_demo_seed:
        raise HTTPException(status_code=403, detail='Demo seed is disabled in this environment')
    ensure_admin_user(db)
    return seed_demo_data(db)
