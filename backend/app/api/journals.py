from fastapi import APIRouter, Depends, HTTPException, Query, Header
from typing import Annotated
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func
from app.db.database import get_db
from app.models.entities import JournalEntry, JournalLine, ChartAccount
from app.schemas.common import JournalEntryCreate
from app.api.deps import require_permissions
from app.services.bir_service import ensure_date_unlocked
from app.services.audit_service import record_audit, list_audit

from app.services.payable_atomicity_service import _reserve, _fingerprint, IdempotencyConflict
from app.services.journal_integrity_service import validate_journal, posted_journal_filter, money

router = APIRouter()

def _entry(db, entry_id, *, lock=False):
    query = db.query(JournalEntry).options(selectinload(JournalEntry.lines)).filter(JournalEntry.id==entry_id)
    if lock:
        query = query.populate_existing().with_for_update()
    row = query.first()
    if not row: raise HTTPException(status_code=404, detail='Entry not found')
    return row

@router.get('/entries')
def entries(
    db: Session = Depends(get_db),
    user=Depends(require_permissions('journals.view')),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return (
        db.query(JournalEntry)
        .options(selectinload(JournalEntry.lines))
        .order_by(JournalEntry.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

@router.get('/entries/{entry_id}')
def entry_detail(entry_id:int, db:Session=Depends(get_db), user=Depends(require_permissions('journals.view'))):
    return {'entry': _entry(db,entry_id), 'audit': list_audit(db,'journal_entry',entry_id)}

@router.post('/entries')
def create_entry(payload: JournalEntryCreate, db: Session = Depends(get_db), user=Depends(require_permissions('journals.post')), idempotency_key: Annotated[str | None, Header(alias='Idempotency-Key')] = None):
    reservation = None
    try:
        if idempotency_key:
            reservation, replayed = _reserve(db, scope=f'journal:create:{user.username}', idempotency_key=idempotency_key, fingerprint=_fingerprint(payload.model_dump(mode='json')))
            if replayed:
                if reservation.resource_type != 'journal' or not reservation.resource_id:
                    raise IdempotencyConflict('Journal request is incomplete and cannot be replayed.')
                return _entry(db, reservation.resource_id)
        ensure_date_unlocked(db, payload.entry_date, scope='bir', action='create journal entry')
        validate_journal(db, payload.entry_date, payload.lines)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=409 if isinstance(e, IdempotencyConflict) else 400, detail=str(e))
    account_names = {a.code: a.name for a in db.query(ChartAccount).filter(ChartAccount.code.in_([line.account_code for line in payload.lines])).all()}
    entry=JournalEntry(entry_date=payload.entry_date, reference_no=payload.reference_no, description=payload.description, source_module=payload.source_module, status=payload.status, posted_by=getattr(user,'username',None) if payload.status=='posted' else None)
    db.add(entry); db.flush()
    for line in payload.lines:
        values = line.model_dump()
        values['account_name'] = account_names[line.account_code]
        db.add(JournalLine(journal_entry_id=entry.id, **values))
    record_audit(db, entity_type='journal_entry', entity_id=entry.id, action='created', user=user, after={'status':entry.status,'reference_no':entry.reference_no})
    if reservation is not None:
        reservation.resource_type = 'journal'
        reservation.resource_id = entry.id
    db.commit(); return _entry(db,entry.id)

@router.post('/entries/{entry_id}/post')
def post_entry(entry_id:int, db:Session=Depends(get_db), user=Depends(require_permissions('journals.post'))):
    row=_entry(db,entry_id,lock=True)
    if row.locked or row.is_reversed: raise HTTPException(status_code=400, detail='Locked or reversed entry cannot be posted')
    if row.status != 'draft': raise HTTPException(status_code=400, detail='Only draft journals can be posted')
    try:
        ensure_date_unlocked(db,row.entry_date,scope='bir',action='post journal entry')
        validate_journal(db, row.entry_date, row.lines)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    before={'status':row.status}; row.status='posted'; row.posted_by=getattr(user,'username',None)
    record_audit(db,entity_type='journal_entry',entity_id=row.id,action='posted',user=user,before=before,after={'status':'posted'})
    db.commit(); return _entry(db,row.id)

@router.post('/entries/{entry_id}/lock')
def lock_entry(entry_id:int, db:Session=Depends(get_db), user=Depends(require_permissions('journals.post'))):
    row=_entry(db,entry_id,lock=True)
    if row.status!='posted': raise HTTPException(status_code=400, detail='Only posted entries can be locked')
    row.locked=True; row.locked_by=getattr(user,'username',None)
    record_audit(db,entity_type='journal_entry',entity_id=row.id,action='locked',user=user)
    db.commit(); return _entry(db,row.id)

@router.post('/entries/{entry_id}/reverse')
def reverse_entry(entry_id:int, db:Session=Depends(get_db), user=Depends(require_permissions('journals.post'))):
    row=_entry(db,entry_id,lock=True)
    if row.status!='posted' or row.is_reversed: raise HTTPException(status_code=400, detail='Only unreversed posted entries can be reversed')
    try:
        ensure_date_unlocked(db,row.entry_date,scope='bir',action='reverse journal entry')
        validate_journal(db, row.entry_date, row.lines, check_accounts=False)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    if db.query(JournalEntry.id).filter(JournalEntry.reversed_from_id == row.id).first():
        raise HTTPException(status_code=409, detail='This journal already has a reversal')
    rev=JournalEntry(entry_date=row.entry_date, reference_no=f'REV-{row.reference_no or row.id}', description=f'Reversal of {row.reference_no or row.id}: {row.description or ""}', source_module=row.source_module, status='posted', reversed_from_id=row.id, posted_by=getattr(user,'username',None))
    db.add(rev); db.flush()
    for line in row.lines: db.add(JournalLine(journal_entry_id=rev.id, account_code=line.account_code, account_name=line.account_name, debit=money(line.credit), credit=money(line.debit), memo=f'Reversal: {line.memo or ""}'))
    row.is_reversed=True
    record_audit(db,entity_type='journal_entry',entity_id=row.id,action='reversed',user=user,after={'reversal_entry_id':rev.id})
    record_audit(db,entity_type='journal_entry',entity_id=rev.id,action='created_as_reversal',user=user,after={'reversed_from_id':row.id})
    db.commit(); return _entry(db,rev.id)

@router.get('/trial-balance')
def trial_balance(db: Session = Depends(get_db), user=Depends(require_permissions('journals.view'))):
    rows=db.query(JournalLine.account_code,JournalLine.account_name,func.sum(JournalLine.debit).label('debit'),func.sum(JournalLine.credit).label('credit')).join(JournalEntry,JournalEntry.id==JournalLine.journal_entry_id).filter(posted_journal_filter()).group_by(JournalLine.account_code,JournalLine.account_name).order_by(JournalLine.account_code.asc()).all()
    return [{'account_code':r[0],'account_name':r[1],'debit':float(r[2] or 0),'credit':float(r[3] or 0)} for r in rows]
