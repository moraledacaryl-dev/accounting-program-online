from __future__ import annotations

from sqlalchemy.orm import Session, selectinload

from app.models.entities import AccountMappingRule, ChartAccount, JournalLine
from app.schemas.accounting_setup import (
    AccountMappingRuleCreate,
    AccountMappingRuleUpdate,
    ChartAccountCreate,
    ChartAccountUpdate,
)
from app.services.code_service import ensure_editable_after_create, generate_code


def _norm(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _code(value: str | None) -> str:
    return (value or '').strip().upper()


def _serialize_chart(row: ChartAccount) -> dict:
    return {
        'id': row.id,
        'code': row.code,
        'name': row.name,
        'account_type': row.account_type,
        'subtype': row.subtype,
        'parent_id': row.parent_id,
        'parent_code': row.parent.code if row.parent else None,
        'parent_name': row.parent.name if row.parent else None,
        'is_active': bool(row.is_active),
        'notes': row.notes,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_mapping(row: AccountMappingRule) -> dict:
    return {
        'id': row.id,
        'module_slug': row.module_slug,
        'category': row.category,
        'bucket': row.bucket,
        'item': row.item,
        'direction': row.direction,
        'payment_method': row.payment_method,
        'debit_account_code': row.debit_account_code,
        'credit_account_code': row.credit_account_code,
        'priority': int(row.priority or 100),
        'is_active': bool(row.is_active),
        'notes': row.notes,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def list_chart_accounts(db: Session, *, active_only: bool = False):
    query = db.query(ChartAccount).options(selectinload(ChartAccount.parent))
    if active_only:
        query = query.filter(ChartAccount.is_active == True)
    rows = query.order_by(ChartAccount.code.asc(), ChartAccount.name.asc()).all()
    return [_serialize_chart(row) for row in rows]


def create_chart_account(db: Session, payload: ChartAccountCreate):
    code = generate_code(db, 'chart_account', requested_code=payload.code)
    name = _norm(payload.name)
    account_type = _norm(payload.account_type)
    if not name:
        raise ValueError('name is required.')
    if not account_type:
        raise ValueError('account_type is required.')
    if payload.parent_id:
        parent = db.get(ChartAccount, int(payload.parent_id))
        if not parent:
            raise ValueError('parent_id not found.')
    row = ChartAccount(
        code=code,
        name=name,
        account_type=account_type,
        subtype=_norm(payload.subtype),
        parent_id=payload.parent_id,
        is_active=bool(payload.is_active),
        notes=payload.notes,
    )
    db.add(row)
    db.commit()
    row = db.query(ChartAccount).options(selectinload(ChartAccount.parent)).filter(ChartAccount.id == row.id).first()
    return _serialize_chart(row)


def update_chart_account(db: Session, account_id: int, payload: ChartAccountUpdate):
    row = db.get(ChartAccount, int(account_id))
    if not row:
        raise ValueError('Chart account not found.')
    data = payload.model_dump(exclude_unset=True)
    if 'code' in data:
        if data['code'] != row.code and db.query(JournalLine.id).filter(JournalLine.account_code == row.code).first():
            raise ValueError('An account used in journals cannot be renumbered. Create a new account instead.')
        code = ensure_editable_after_create(
            db,
            'chart_account',
            row.code,
            data.get('code'),
            exclude_id=row.id,
        )
        row.code = code
    if 'name' in data:
        name = _norm(data.get('name'))
        if not name:
            raise ValueError('name cannot be blank.')
        row.name = name
    if 'account_type' in data:
        account_type = _norm(data.get('account_type'))
        if not account_type:
            raise ValueError('account_type cannot be blank.')
        row.account_type = account_type
    if 'parent_id' in data:
        parent_id = data.get('parent_id')
        if parent_id and int(parent_id) == int(row.id):
            raise ValueError('parent_id cannot reference self.')
        if parent_id and not db.get(ChartAccount, int(parent_id)):
            raise ValueError('parent_id not found.')
        cursor, visited = parent_id, {row.id}
        while cursor:
            if cursor in visited:
                raise ValueError('Chart account hierarchy cannot contain a cycle.')
            visited.add(cursor)
            parent = db.get(ChartAccount, int(cursor))
            cursor = parent.parent_id if parent else None
        row.parent_id = parent_id
    for key in ('subtype', 'is_active', 'notes'):
        if key in data:
            value = data.get(key)
            if key == 'subtype':
                value = _norm(value)
            setattr(row, key, value)
    db.add(row)
    db.commit()
    row = db.query(ChartAccount).options(selectinload(ChartAccount.parent)).filter(ChartAccount.id == row.id).first()
    return _serialize_chart(row)


def delete_chart_account(db: Session, account_id: int):
    row = db.get(ChartAccount, int(account_id))
    if not row:
        raise ValueError('Chart account not found.')
    has_children = db.query(ChartAccount.id).filter(ChartAccount.parent_id == row.id).first()
    if has_children:
        raise ValueError('Cannot delete chart account with child accounts.')
    if db.query(JournalLine.id).filter(JournalLine.account_code == row.code).first():
        raise ValueError('An account used in journals cannot be deleted. Deactivate it instead.')
    if db.query(AccountMappingRule.id).filter((AccountMappingRule.debit_account_code == row.code) | (AccountMappingRule.credit_account_code == row.code)).first():
        raise ValueError('Remove posting rules referencing this account before deleting it.')
    db.delete(row)
    db.commit()
    return {'ok': True}


def list_account_mappings(db: Session, *, module_slug: str | None = None, active_only: bool = False):
    query = db.query(AccountMappingRule)
    if module_slug:
        query = query.filter(AccountMappingRule.module_slug == module_slug)
    if active_only:
        query = query.filter(AccountMappingRule.is_active == True)
    rows = query.order_by(AccountMappingRule.module_slug.asc(), AccountMappingRule.priority.asc(), AccountMappingRule.id.asc()).all()
    return [_serialize_mapping(row) for row in rows]


def create_account_mapping(db: Session, payload: AccountMappingRuleCreate):
    module_slug = _norm(payload.module_slug)
    if not module_slug:
        raise ValueError('module_slug is required.')
    row = AccountMappingRule(
        module_slug=module_slug,
        category=_norm(payload.category),
        bucket=_norm(payload.bucket),
        item=_norm(payload.item),
        direction=_norm(payload.direction),
        payment_method=_norm(payload.payment_method),
        debit_account_code=_code(payload.debit_account_code) if payload.debit_account_code else None,
        credit_account_code=_code(payload.credit_account_code) if payload.credit_account_code else None,
        priority=int(payload.priority if payload.priority is not None else 100),
        is_active=bool(payload.is_active),
        notes=payload.notes,
    )
    if row.debit_account_code and not db.query(ChartAccount).filter(ChartAccount.code == row.debit_account_code).first():
        raise ValueError(f'debit_account_code {row.debit_account_code} not found in chart of accounts.')
    if row.credit_account_code and not db.query(ChartAccount).filter(ChartAccount.code == row.credit_account_code).first():
        raise ValueError(f'credit_account_code {row.credit_account_code} not found in chart of accounts.')
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_mapping(row)


def update_account_mapping(db: Session, mapping_id: int, payload: AccountMappingRuleUpdate):
    row = db.get(AccountMappingRule, int(mapping_id))
    if not row:
        raise ValueError('Account mapping rule not found.')
    data = payload.model_dump(exclude_unset=True)
    for key in ('module_slug', 'category', 'bucket', 'item', 'direction', 'payment_method'):
        if key in data:
            setattr(row, key, _norm(data.get(key)))
    if 'debit_account_code' in data:
        debit = _code(data.get('debit_account_code')) if data.get('debit_account_code') else None
        if debit and not db.query(ChartAccount).filter(ChartAccount.code == debit).first():
            raise ValueError(f'debit_account_code {debit} not found in chart of accounts.')
        row.debit_account_code = debit
    if 'credit_account_code' in data:
        credit = _code(data.get('credit_account_code')) if data.get('credit_account_code') else None
        if credit and not db.query(ChartAccount).filter(ChartAccount.code == credit).first():
            raise ValueError(f'credit_account_code {credit} not found in chart of accounts.')
        row.credit_account_code = credit
    for key in ('priority', 'is_active', 'notes'):
        if key in data:
            setattr(row, key, data.get(key))
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_mapping(row)


def delete_account_mapping(db: Session, mapping_id: int):
    row = db.get(AccountMappingRule, int(mapping_id))
    if not row:
        raise ValueError('Account mapping rule not found.')
    db.delete(row)
    db.commit()
    return {'ok': True}


def resolve_record_accounts(db: Session, record, fallback_debit, fallback_credit):
    """First matching active rule wins: priority, specificity, then stable id."""
    fields = ('category', 'bucket', 'item', 'direction', 'payment_method')
    rules = db.query(AccountMappingRule).filter(
        AccountMappingRule.module_slug == record.module_slug,
        AccountMappingRule.is_active == True,
    ).all()
    matching = [rule for rule in rules if all(
        not getattr(rule, field) or str(getattr(rule, field)).strip().lower() == str(getattr(record, field, '') or '').strip().lower()
        for field in fields
    )]
    matching.sort(key=lambda rule: (rule.priority, -sum(bool(getattr(rule, field)) for field in fields), rule.id))
    if not matching:
        return fallback_debit, fallback_credit
    rule = matching[0]
    if not rule.debit_account_code or not rule.credit_account_code:
        raise ValueError('The matching posting rule needs both a debit and a credit account.')
    codes = {rule.debit_account_code, rule.credit_account_code}
    accounts = {a.code: a for a in db.query(ChartAccount).filter(ChartAccount.code.in_(codes), ChartAccount.is_active == True).all()}
    if set(accounts) != codes:
        raise ValueError('The matching posting rule references a missing or inactive chart account.')
    return ((rule.debit_account_code, accounts[rule.debit_account_code].name),
            (rule.credit_account_code, accounts[rule.credit_account_code].name))
