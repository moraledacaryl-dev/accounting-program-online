from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_any_permissions
from app.db.database import get_db
from app.schemas.cashflow import CashflowTemplateCreate, CashflowTemplateLaunchPayload, CashflowTemplateUpdate
from app.services.cashflow_service import create_template, delete_template, launch_template, list_templates, update_template

router = APIRouter()


@router.get('/')
def get_templates(db: Session = Depends(get_db), user=Depends(get_current_user), active_only: bool = False):
    return list_templates(db, active_only=active_only)


@router.post('/')
def add_template(
    payload: CashflowTemplateCreate,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('cashflow.money_in', 'cashflow.money_out')),
):
    try:
        return create_template(db, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put('/{template_id}')
def edit_template(
    template_id: int,
    payload: CashflowTemplateUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('cashflow.money_in', 'cashflow.money_out')),
):
    try:
        return update_template(db, template_id, payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete('/{template_id}')
def remove_template(
    template_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('cashflow.money_in', 'cashflow.money_out')),
):
    try:
        return delete_template(db, template_id)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(e))


@router.post('/launch')
def launch_template_entry(
    payload: CashflowTemplateLaunchPayload,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('cashflow.money_in', 'cashflow.money_out')),
):
    try:
        return launch_template(db, payload.template_id, payload.overrides or {}, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
