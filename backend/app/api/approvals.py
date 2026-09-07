from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.entities import JournalEntry, PayrollRun
from app.api.deps import require_permissions
from app.schemas.common import RecordUpdate
from app.api.records import _authorize_record_write
from app.api.journals import lock_entry
from app.services.record_service import get_record_obj
from app.services.record_service import update_record
from app.services.audit_service import record_audit

router = APIRouter()

@router.post('/records/{record_id}/approve')
def approve_record(record_id: int, db: Session = Depends(get_db), user=Depends(require_permissions('approvals.act'))):
    try:
        current = get_record_obj(db, record_id)
        if not current:
            raise HTTPException(status_code=404, detail='Record not found')
        _authorize_record_write(db, user, current.module_slug, direction=current.direction, approval=True)
        obj = update_record(db, record_id, RecordUpdate(workflow_status='approved'), approver=user.username)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    if not obj:
        raise HTTPException(status_code=404, detail='Record not found')
    return obj

@router.post('/journals/{entry_id}/lock')
def lock_journal(entry_id: int, db: Session = Depends(get_db), user=Depends(require_permissions('journals.post'))):
    return lock_entry(entry_id, db=db, user=user)

@router.post('/payroll/{run_id}/approve')
def approve_payroll(run_id: int, db: Session = Depends(get_db), user=Depends(require_permissions('approvals.act'))):
    obj = db.get(PayrollRun, run_id)
    if not obj:
        raise HTTPException(status_code=404, detail='Payroll run not found')
    obj.status = 'approved'
    db.add(obj); db.commit(); db.refresh(obj)
    return obj
