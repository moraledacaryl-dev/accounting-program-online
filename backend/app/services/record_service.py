from __future__ import annotations
import json
from types import SimpleNamespace
from app.services.audit_service import record_audit
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.entities import Record, JournalEntry
from app.schemas.common import RecordCreate, RecordUpdate
from app.services.taxonomy_service import get_module_name, validate_record
from app.services.accounting_service import autopost_record
from app.services.bir_service import ensure_date_unlocked

def serialize_record(record: Record):
    return {
        'id': record.id,
        'module_slug': record.module_slug,
        'module_name': record.module_name,
        'category': record.category,
        'bucket': record.bucket,
        'item': record.item,
        'name': record.name,
        'amount': record.amount,
        'quantity': record.quantity,
        'unit': record.unit,
        'direction': record.direction,
        'payment_method': record.payment_method,
        'counterparty': record.counterparty,
        'channel': record.channel,
        'bir_status': record.bir_status,
        'workflow_status': record.workflow_status,
        'transaction_date': record.transaction_date,
        'due_date': record.due_date,
        'document_ref': record.document_ref,
        'notes': record.notes,
        'metadata': json.loads(record.metadata_json or '{}'),
        'created_by': record.created_by,
        'approved_by': record.approved_by,
        'created_at': record.created_at.isoformat() if record.created_at else None,
        'updated_at': record.updated_at.isoformat() if record.updated_at else None,
    }

def create_record(db: Session, module_slug: str, payload: RecordCreate, username: str | None = None):
    ok, error = validate_record(module_slug, payload.category, payload.bucket, payload.item, db)
    if not ok:
        raise ValueError(error)
    ensure_date_unlocked(db, payload.transaction_date, scope='bir', action='create record')
    rec = Record(
        module_slug=module_slug,
        module_name=get_module_name(module_slug),
        category=payload.category,
        bucket=payload.bucket,
        item=payload.item,
        name=payload.name or payload.item,
        amount=payload.amount,
        quantity=payload.quantity,
        unit=payload.unit,
        direction=payload.direction,
        payment_method=payload.payment_method,
        counterparty=payload.counterparty,
        channel=payload.channel,
        bir_status=payload.bir_status,
        workflow_status=payload.workflow_status,
        transaction_date=payload.transaction_date,
        due_date=payload.due_date,
        document_ref=payload.document_ref,
        notes=payload.notes,
        metadata_json=json.dumps(payload.metadata or {}),
        created_by=username,
    )
    db.add(rec)
    db.flush()
    if rec.workflow_status == 'approved':
        autopost_record(db, rec, commit=False)
    record_audit(db, entity_type='record', entity_id=rec.id, action='created', user=SimpleNamespace(username=username), after=serialize_record(rec))
    db.commit()
    db.refresh(rec)
    return serialize_record(rec)

def list_records(db: Session, module_slug: str | None = None, limit: int = 200, search: str | None = None):
    stmt = select(Record)
    if module_slug:
        stmt = stmt.where(Record.module_slug == module_slug)
    if search:
        like = f'%{search}%'
        stmt = stmt.where(Record.name.ilike(like) | Record.notes.ilike(like) | Record.document_ref.ilike(like))
    stmt = stmt.order_by(Record.id.desc()).limit(limit)
    rows = db.execute(stmt).scalars().all()
    return [serialize_record(r) for r in rows]

def get_record_obj(db: Session, record_id: int):
    return db.get(Record, record_id)

def get_record(db: Session, record_id: int):
    row = get_record_obj(db, record_id)
    return serialize_record(row) if row else None

def update_record(db: Session, record_id: int, payload: RecordUpdate, approver: str | None = None):
    row = db.query(Record).filter(Record.id == record_id).populate_existing().with_for_update().first()
    if not row:
        return None
    # Block edits when either the original or target period is locked.
    ensure_date_unlocked(db, row.transaction_date, scope='bir', action='update record')
    old_status = row.workflow_status
    before = serialize_record(row)
    data = payload.model_dump(exclude_unset=True)
    posted = db.query(JournalEntry.id).filter(JournalEntry.reference_no == f'REC-{row.id}').first()
    protected = set(data) - {'notes'}
    if posted and any(getattr(row, key, None) != data[key] for key in protected):
        raise ValueError('Posted records cannot be changed. Reverse the journal and create a replacement record with a reference to the original.')
    if 'transaction_date' in data:
        ensure_date_unlocked(db, data.get('transaction_date'), scope='bir', action='move record to locked period')
    for key, value in data.items():
        if key == 'metadata':
            setattr(row, 'metadata_json', json.dumps(value or {}))
        else:
            setattr(row, key, value)
    if row.workflow_status == 'approved' and old_status != 'approved':
        row.approved_by = approver
    db.add(row)
    db.flush()
    if row.workflow_status == 'approved':
        autopost_record(db, row, commit=False)
    record_audit(db, entity_type='record', entity_id=row.id, action='updated', user=SimpleNamespace(username=approver), before=before, after=serialize_record(row))
    db.commit()
    db.refresh(row)
    return serialize_record(row)

def delete_record(db: Session, record_id: int, username: str | None = None):
    row = db.query(Record).filter(Record.id == record_id).populate_existing().with_for_update().first()
    if not row:
        return False
    ensure_date_unlocked(db, row.transaction_date, scope='bir', action='delete record')
    if db.query(JournalEntry.id).filter(JournalEntry.reference_no == f'REC-{row.id}').first():
        raise ValueError('Posted records cannot be deleted. Use a journal reversal to preserve the audit trail.')
    record_audit(db, entity_type='record', entity_id=row.id, action='deleted', user=SimpleNamespace(username=username), before=serialize_record(row))
    db.delete(row)
    db.commit()
    return True
