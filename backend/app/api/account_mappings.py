from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permissions
from app.db.database import get_db
from app.schemas.accounting_setup import AccountMappingRuleCreate, AccountMappingRuleUpdate
from app.services.account_mapping_service import (
    create_account_mapping,
    delete_account_mapping,
    list_account_mappings,
    update_account_mapping,
)

router = APIRouter()


@router.get('/')
def get_account_mappings(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    module_slug: str | None = None,
    active_only: bool = False,
):
    return list_account_mappings(db, module_slug=module_slug, active_only=active_only)


@router.post('/')
def add_account_mapping(
    payload: AccountMappingRuleCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('account_mapping.manage')),
):
    try:
        return create_account_mapping(db, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put('/{mapping_id}')
def edit_account_mapping(
    mapping_id: int,
    payload: AccountMappingRuleUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('account_mapping.manage')),
):
    try:
        return update_account_mapping(db, mapping_id, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete('/{mapping_id}')
def remove_account_mapping(
    mapping_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('account_mapping.manage')),
):
    try:
        return delete_account_mapping(db, mapping_id)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
