from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_permissions
from app.db.database import get_db
from app.schemas.rooms import RoomPackageRuleCreate, RoomPackageRuleUpdate
from app.services.room_setup_service import create_package_rule, delete_package_rule, list_package_rules, update_package_rule

router = APIRouter()


@router.get('/')
def get_package_rules(
    db: Session = Depends(get_db),
    user=Depends(require_permissions('room_setup.view')),
    active_only: bool = False,
):
    return list_package_rules(db, active_only=active_only)


@router.post('/')
def add_package_rule(
    payload: RoomPackageRuleCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('room_setup.manage')),
):
    try:
        return create_package_rule(db, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put('/{package_rule_id}')
def edit_package_rule(
    package_rule_id: int,
    payload: RoomPackageRuleUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('room_setup.manage')),
):
    try:
        return update_package_rule(db, package_rule_id, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete('/{package_rule_id}')
def remove_package_rule(
    package_rule_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('room_setup.manage')),
):
    try:
        return delete_package_rule(db, package_rule_id)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
