from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.database import get_db
from app.models.entities import JournalEntry, JournalLine
from app.schemas.common import JournalEntryCreate
from app.api.deps import require_permissions
from app.services.bir_service import ensure_date_unlocked

router = APIRouter()

@router.get('/entries')
def entries(db: Session = Depends(get_db), user=Depends(require_permissions('journals.view'))):
    return db.query(JournalEntry).order_by(JournalEntry.id.desc()).all()

@router.post('/entries')
def create_entry(payload: JournalEntryCreate, db: Session = Depends(get_db), user=Depends(require_permissions('journals.post'))):
    try:
        ensure_date_unlocked(db, payload.entry_date, scope='bir', action='create journal entry')
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    total_debit = sum(float(l.debit or 0) for l in payload.lines)
    total_credit = sum(float(l.credit or 0) for l in payload.lines)
    if round(total_debit, 2) != round(total_credit, 2):
        raise HTTPException(status_code=400, detail='Debits and credits must balance')
    entry = JournalEntry(entry_date=payload.entry_date, reference_no=payload.reference_no, description=payload.description, source_module=payload.source_module, status=payload.status)
    db.add(entry); db.flush()
    for line in payload.lines:
        db.add(JournalLine(journal_entry_id=entry.id, **line.model_dump()))
    db.commit(); db.refresh(entry)
    return entry

@router.get('/trial-balance')
def trial_balance(db: Session = Depends(get_db), user=Depends(require_permissions('journals.view'))):
    rows = db.query(JournalLine.account_code, JournalLine.account_name, func.sum(JournalLine.debit).label('debit'), func.sum(JournalLine.credit).label('credit')).group_by(JournalLine.account_code, JournalLine.account_name).order_by(JournalLine.account_code.asc()).all()
    return [{'account_code': r[0], 'account_name': r[1], 'debit': float(r[2] or 0), 'credit': float(r[3] or 0)} for r in rows]
