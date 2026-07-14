from __future__ import annotations

import json
from sqlalchemy.orm import Session
from app.models.entities import AuditEvent

def record_audit(db: Session, *, entity_type: str, entity_id: int, action: str, user=None, before=None, after=None, source_app=None, correlation_id=None):
    row = AuditEvent(
        entity_type=entity_type, entity_id=int(entity_id), action=action,
        before_json=json.dumps(before or {}, default=str), after_json=json.dumps(after or {}, default=str),
        user_id=getattr(user, 'id', None), username=getattr(user, 'username', None),
        source_app=source_app, correlation_id=correlation_id,
    )
    db.add(row)
    return row

def list_audit(db: Session, entity_type: str, entity_id: int):
    rows = db.query(AuditEvent).filter(AuditEvent.entity_type==entity_type, AuditEvent.entity_id==int(entity_id)).order_by(AuditEvent.id.desc()).all()
    return rows
