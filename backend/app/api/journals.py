from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func
from app.db.database import get_db
from app.models.entities import JournalEntry, JournalLine
from app.schemas.common import JournalEntryCreate
from app.api.deps import require_permissions
from app.services.bir_service import ensure_date_unlocked
from app.services.audit_service import record_audit, list_audit

router = APIRouter()

def _entry(db, entry_id):
    row = db.query(JournalEntry).options(selectinload(JournalEntry.lines)).filter(JournalEntry.id==entry_id).first()
    if not row: raise HTTPException(status_code=404, detail='Entry not found')
    return row

@router.get('/entries')
def entries(db: Session = Depends(get_db), user=Depends(require_permissions('journals.view'))):
    return db.query(JournalEntry).options(selectinload(JournalEntry.lines)).order_by(JournalEntry.id.desc()).all()

@router.get('/entries/{entry_id}')
def entry_detail(entry_id:int, db:Session=Depends(get_db), user=Depends(require_permissions('journals.view'))):
    return {'entry': _entry(db,entry_id), 'audit': list_audit(db,'journal_entry',entry_id)}

@router.post('/entries')
def create_entry(payload: JournalEntryCreate, db: Session = Depends(get_db), user=Depends(require_permissions('journals.post'))):
    try: ensure_date_unlocked(db, payload.entry_date, scope='bir', action='create journal entry')
    except ValueError as e: raise HTTPException(status_code=400, detail=str(e))
    total_debit=sum(float(l.debit or 0) for l in payload.lines); total_credit=sum(float(l.credit or 0) for l in payload.lines)
    if round(total_debit,2)!=round(total_credit,2): raise HTTPException(status_code=400, detail='Debits and credits must balance')
    entry=JournalEntry(entry_date=payload.entry_date, reference_no=payload.reference_no, description=payload.description, source_module=payload.source_module, status=payload.status, posted_by=getattr(user,'username',None) if payload.status=='posted' else None)
    db.add(entry); db.flush()
    for line in payload.lines: db.add(JournalLine(journal_entry_id=entry.id, **line.model_dump()))
    record_audit(db, entity_type='journal_entry', entity_id=entry.id, action='created', user=user, after={'status':entry.status,'reference_no':entry.reference_no})
    db.commit(); return _entry(db,entry.id)

@router.post('/entries/{entry_id}/post')
def post_entry(entry_id:int, db:Session=Depends(get_db), user=Depends(require_permissions('journals.post'))):
    row=_entry(db,entry_id)
    if row.locked or row.is_reversed: raise HTTPException(status_code=400, detail='Locked or reversed entry cannot be posted')
    ensure_date_unlocked(db,row.entry_date,scope='bir',action='post journal entry')
    before={'status':row.status}; row.status='posted'; row.posted_by=getattr(user,'username',None)
    record_audit(db,entity_type='journal_entry',entity_id=row.id,action='posted',user=user,before=before,after={'status':'posted'})
    db.commit(); return _entry(db,row.id)

@router.post('/entries/{entry_id}/lock')
def lock_entry(entry_id:int, db:Session=Depends(get_db), user=Depends(require_permissions('journals.post'))):
    row=_entry(db,entry_id)
    if row.status!='posted': raise HTTPException(status_code=400, detail='Only posted entries can be locked')
    row.locked=True; row.locked_by=getattr(user,'username',None)
    record_audit(db,entity_type='journal_entry',entity_id=row.id,action='locked',user=user)
    db.commit(); return _entry(db,row.id)

@router.post('/entries/{entry_id}/reverse')
def reverse_entry(entry_id:int, db:Session=Depends(get_db), user=Depends(require_permissions('journals.post'))):
    row=_entry(db,entry_id)
    if row.status!='posted' or row.is_reversed: raise HTTPException(status_code=400, detail='Only unreversed posted entries can be reversed')
    ensure_date_unlocked(db,row.entry_date,scope='bir',action='reverse journal entry')
    rev=JournalEntry(entry_date=row.entry_date, reference_no=f'REV-{row.reference_no or row.id}', description=f'Reversal of {row.reference_no or row.id}: {row.description or ""}', source_module=row.source_module, status='posted', reversed_from_id=row.id, posted_by=getattr(user,'username',None))
    db.add(rev); db.flush()
    for line in row.lines: db.add(JournalLine(journal_entry_id=rev.id, account_code=line.account_code, account_name=line.account_name, debit=float(line.credit or 0), credit=float(line.debit or 0), memo=f'Reversal: {line.memo or ""}'))
    row.is_reversed=True
    record_audit(db,entity_type='journal_entry',entity_id=row.id,action='reversed',user=user,after={'reversal_entry_id':rev.id})
    record_audit(db,entity_type='journal_entry',entity_id=rev.id,action='created_as_reversal',user=user,after={'reversed_from_id':row.id})
    db.commit(); return _entry(db,rev.id)

@router.get('/trial-balance')
def trial_balance(db: Session = Depends(get_db), user=Depends(require_permissions('journals.view'))):
    rows=db.query(JournalLine.account_code,JournalLine.account_name,func.sum(JournalLine.debit).label('debit'),func.sum(JournalLine.credit).label('credit')).join(JournalEntry,JournalEntry.id==JournalLine.journal_entry_id).filter(JournalEntry.status=='posted').group_by(JournalLine.account_code,JournalLine.account_name).order_by(JournalLine.account_code.asc()).all()
    return [{'account_code':r[0],'account_name':r[1],'debit':float(r[2] or 0),'credit':float(r[3] or 0)} for r in rows]
