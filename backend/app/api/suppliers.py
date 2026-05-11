from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_permissions
from app.db.database import get_db
from app.schemas.suppliers import SupplierCreate, SupplierUpdate
from app.services.supplier_service import create_supplier, delete_supplier, list_suppliers, update_supplier

router = APIRouter()


@router.get('/')
def get_suppliers(
    db: Session = Depends(get_db),
    user=Depends(require_permissions('suppliers.view')),
    active_only: bool = False,
    q: str | None = None,
):
    return list_suppliers(db, active_only=active_only, q=q)


@router.post('/')
def add_supplier(
    payload: SupplierCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('suppliers.manage')),
):
    try:
        return create_supplier(db, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put('/{supplier_id}')
def edit_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('suppliers.manage')),
):
    try:
        return update_supplier(db, supplier_id, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete('/{supplier_id}')
def remove_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('suppliers.manage')),
):
    try:
        return delete_supplier(db, supplier_id)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
