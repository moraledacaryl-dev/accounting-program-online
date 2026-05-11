from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.entities import Supplier
from app.schemas.suppliers import SupplierCreate, SupplierUpdate
from app.services.code_service import ensure_editable_after_create, generate_code


def _norm(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _serialize(row: Supplier) -> dict:
    return {
        'id': row.id,
        'name': row.name,
        'code': row.code,
        'supplier_type': row.supplier_type,
        'contact_person': row.contact_person,
        'phone': row.phone,
        'email': row.email,
        'address': row.address,
        'tin': row.tin,
        'tax_id': row.tax_id,
        'payment_terms': row.payment_terms,
        'category': row.category,
        'is_active': bool(row.is_active),
        'notes': row.notes,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def list_suppliers(db: Session, *, active_only: bool = False, q: str | None = None):
    query = db.query(Supplier)
    if active_only:
        query = query.filter(Supplier.is_active == True)
    if q:
        like_q = f'%{q.strip()}%'
        query = query.filter((Supplier.name.like(like_q)) | (Supplier.code.like(like_q)) | (Supplier.contact_person.like(like_q)))
    rows = query.order_by(Supplier.name.asc()).all()
    return [_serialize(row) for row in rows]


def create_supplier(db: Session, payload: SupplierCreate):
    name = _norm(payload.name)
    code = generate_code(db, 'supplier', requested_code=payload.code)
    if not name:
        raise ValueError('name is required.')
    if db.query(Supplier).filter(Supplier.name == name).first():
        raise ValueError(f'Supplier {name} already exists.')
    row = Supplier(
        name=name,
        code=code,
        supplier_type=_norm(payload.supplier_type),
        contact_person=_norm(payload.contact_person),
        phone=_norm(payload.phone),
        email=_norm(payload.email),
        address=_norm(payload.address),
        tin=_norm(payload.tin),
        tax_id=_norm(payload.tax_id),
        payment_terms=_norm(payload.payment_terms),
        category=_norm(payload.category),
        is_active=bool(payload.is_active),
        notes=payload.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize(row)


def update_supplier(db: Session, supplier_id: int, payload: SupplierUpdate):
    row = db.get(Supplier, int(supplier_id))
    if not row:
        raise ValueError('Supplier not found.')
    data = payload.model_dump(exclude_unset=True)
    if 'name' in data:
        name = _norm(data.get('name'))
        if not name:
            raise ValueError('name cannot be blank.')
        dup = db.query(Supplier).filter(Supplier.name == name, Supplier.id != row.id).first()
        if dup:
            raise ValueError(f'Supplier {name} already exists.')
        row.name = name
    if 'code' in data:
        code = ensure_editable_after_create(
            db,
            'supplier',
            row.code,
            data.get('code'),
            exclude_id=row.id,
        )
        row.code = code
    for key in ('supplier_type', 'contact_person', 'phone', 'email', 'address', 'tin', 'tax_id', 'payment_terms', 'category'):
        if key in data:
            setattr(row, key, _norm(data.get(key)))
    for key in ('is_active', 'notes'):
        if key in data:
            setattr(row, key, data.get(key))
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize(row)


def delete_supplier(db: Session, supplier_id: int):
    row = db.get(Supplier, int(supplier_id))
    if not row:
        raise ValueError('Supplier not found.')
    db.delete(row)
    db.commit()
    return {'ok': True}
