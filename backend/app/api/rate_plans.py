from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_permissions
from app.db.database import get_db
from app.schemas.rooms import RatePlanCreate, RatePlanUpdate
from app.services.room_setup_service import create_rate_plan, delete_rate_plan, list_rate_plans, update_rate_plan

router = APIRouter()


@router.get('/')
def get_rate_plans(
    db: Session = Depends(get_db),
    user=Depends(require_permissions('room_setup.view')),
    active_only: bool = False,
):
    return list_rate_plans(db, active_only=active_only)


@router.post('/')
def add_rate_plan(
    payload: RatePlanCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('room_setup.manage')),
):
    try:
        return create_rate_plan(db, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put('/{rate_plan_id}')
def edit_rate_plan(
    rate_plan_id: int,
    payload: RatePlanUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('room_setup.manage')),
):
    try:
        return update_rate_plan(db, rate_plan_id, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete('/{rate_plan_id}')
def remove_rate_plan(
    rate_plan_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('room_setup.manage')),
):
    try:
        return delete_rate_plan(db, rate_plan_id)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
