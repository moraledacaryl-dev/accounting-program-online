from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.entities import (
    BookingChannel,
    ChartAccount,
    FinancialAccount,
    PurchaseOrder,
    PurchaseRequest,
    RatePlan,
    ReceivingRecord,
    Room,
    RoomType,
    Supplier,
)
from app.services.system_settings_service import get_code_rule, load_system_settings

ENTITY_MODEL_FIELD = {
    'room_type': (RoomType, 'code'),
    'room': (Room, 'room_no'),
    'rate_plan': (RatePlan, 'code'),
    'booking_channel': (BookingChannel, 'code'),
    'supplier': (Supplier, 'code'),
    'purchase_request': (PurchaseRequest, 'request_no'),
    'purchase_order': (PurchaseOrder, 'po_no'),
    'receiving': (ReceivingRecord, 'receiving_no'),
    'chart_account': (ChartAccount, 'code'),
    'financial_account': (FinancialAccount, 'code'),
}


def normalize_code_value(value: str | None) -> str:
    return (value or '').strip().upper()


def _model_and_field(entity_key: str):
    if entity_key not in ENTITY_MODEL_FIELD:
        raise ValueError(f'Unsupported code entity: {entity_key}.')
    return ENTITY_MODEL_FIELD[entity_key]


def code_exists(db: Session, entity_key: str, code: str, *, exclude_id: int | None = None) -> bool:
    model, field_name = _model_and_field(entity_key)
    field = getattr(model, field_name)
    query = db.query(model).filter(field == code)
    if exclude_id:
        query = query.filter(model.id != int(exclude_id))
    return query.first() is not None


def _build_stem(rule: dict, now: datetime | None = None) -> tuple[str, str]:
    now = now or datetime.utcnow()
    prefix = normalize_code_value(rule.get('prefix') or '')
    if not prefix:
        prefix = 'DOC'
    sep = str(rule.get('separator') or '-').strip() or '-'
    parts = [prefix]
    if bool(rule.get('include_year')):
        parts.append(now.strftime('%Y'))
    if bool(rule.get('include_month')):
        parts.append(now.strftime('%m'))
    return sep.join(parts), sep


def _extract_seq(candidate: str, stem: str, sep: str) -> int | None:
    prefix = f'{stem}{sep}'
    if not candidate.startswith(prefix):
        return None
    tail = candidate[len(prefix):]
    if not tail.isdigit():
        return None
    try:
        return int(tail)
    except Exception:
        return None


def _next_sequence(db: Session, entity_key: str, stem: str, sep: str) -> int:
    model, field_name = _model_and_field(entity_key)
    field = getattr(model, field_name)
    like_pattern = f'{stem}{sep}%'
    rows = db.query(field).filter(field.like(like_pattern)).all()
    max_seq = 0
    for (value,) in rows:
        seq = _extract_seq(str(value or ''), stem, sep)
        if seq and seq > max_seq:
            max_seq = seq
    return max_seq + 1


def ensure_editable_after_create(
    db: Session,
    entity_key: str,
    current_code: str | None,
    requested_code: str | None,
    *,
    exclude_id: int | None = None,
) -> str:
    current_norm = normalize_code_value(current_code)
    requested_norm = normalize_code_value(requested_code)
    if not requested_norm:
        return current_norm
    if requested_norm == current_norm:
        return current_norm

    settings = load_system_settings(db)
    rule = get_code_rule(settings, entity_key)
    if not bool(rule.get('editable_after_create', True)):
        raise ValueError(f'{entity_key} code cannot be edited after creation.')
    if code_exists(db, entity_key, requested_norm, exclude_id=exclude_id):
        raise ValueError(f'{entity_key} code {requested_norm} already exists.')
    return requested_norm


def generate_code(
    db: Session,
    entity_key: str,
    *,
    requested_code: str | None = None,
    exclude_id: int | None = None,
) -> str:
    settings = load_system_settings(db)
    code_settings = (settings.get('code_generation') or {}) if isinstance(settings, dict) else {}
    allow_manual_override = bool(code_settings.get('allow_manual_override', True))
    rule = get_code_rule(settings, entity_key)

    manual = normalize_code_value(requested_code)
    if manual and allow_manual_override:
        if code_exists(db, entity_key, manual, exclude_id=exclude_id):
            raise ValueError(f'{entity_key} code {manual} already exists.')
        return manual

    stem, sep = _build_stem(rule)
    digits = int(rule.get('digits') or 4)
    digits = max(2, min(8, digits))

    sequence = _next_sequence(db, entity_key, stem, sep)
    for offset in range(0, 200000):
        seq = sequence + offset
        candidate = f'{stem}{sep}{seq:0{digits}d}'
        if not code_exists(db, entity_key, candidate, exclude_id=exclude_id):
            return candidate
    raise ValueError(f'Unable to generate unique code for {entity_key}.')
