from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.entities import BIRBookEntry, PeriodLock
from app.schemas.common import BIRGeneratePayload, BIRSelectionPayload, PeriodLockPayload
from app.services.bir_service import generate_books, list_bir_candidates, save_bir_selections
from app.api.deps import require_permissions

router = APIRouter()

@router.get('/books')
def books(period_key: str | None = None, db: Session = Depends(get_db), user=Depends(require_permissions('bir.view'))):
    q = db.query(BIRBookEntry)
    if period_key:
        q = q.filter(BIRBookEntry.period_key == period_key)
    return q.order_by(BIRBookEntry.period_key.desc(), BIRBookEntry.book_type.asc(), BIRBookEntry.id.asc()).all()

@router.post('/generate')
def generate(payload: BIRGeneratePayload, db: Session = Depends(get_db), user=Depends(require_permissions('bir.manage'))):
    try:
        return generate_books(db, payload.period_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get('/candidates')
def candidates(period_key: str, db: Session = Depends(get_db), user=Depends(require_permissions('bir.view'))):
    try:
        return list_bir_candidates(db, period_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/selections')
def save_selections(payload: BIRSelectionPayload, db: Session = Depends(get_db), user=Depends(require_permissions('bir.manage'))):
    try:
        return save_bir_selections(db, payload.period_key, payload.selections, username=getattr(user, 'username', None))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get('/locks')
def locks(db: Session = Depends(get_db), user=Depends(require_permissions('bir.view'))):
    return db.query(PeriodLock).order_by(PeriodLock.period_key.desc()).all()

@router.post('/locks')
def lock_period(payload: PeriodLockPayload, db: Session = Depends(get_db), user=Depends(require_permissions('bir.manage'))):
    obj = db.query(PeriodLock).filter(PeriodLock.period_key == payload.period_key, PeriodLock.scope == payload.scope).first()
    if not obj:
        obj = PeriodLock(period_key=payload.period_key, scope=payload.scope)
    obj.is_locked = payload.is_locked
    obj.locked_by = user.username
    obj.notes = payload.notes
    db.add(obj); db.commit(); db.refresh(obj)
    return obj
