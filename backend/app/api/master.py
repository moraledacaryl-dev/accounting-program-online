from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.entities import MasterValue
from app.schemas.common import MasterValueCreate, MasterValueUpdate
from app.api.deps import get_current_user, require_permissions

router = APIRouter()

@router.get('/values')
def values(
    group_name: str | None = Query(None),
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    q = db.query(MasterValue)
    if group_name:
        q = q.filter(MasterValue.group_name == group_name)
    if active_only:
        q = q.filter(MasterValue.is_active == True)
    return q.order_by(MasterValue.group_name.asc(), MasterValue.is_active.desc(), MasterValue.value.asc()).all()

@router.post('/values')
def add_value(payload: MasterValueCreate, db: Session = Depends(get_db), user=Depends(require_permissions('master_data.manage'))):
    obj = MasterValue(**payload.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@router.put('/values/{value_id}')
def update_value(value_id: int, payload: MasterValueUpdate, db: Session = Depends(get_db), user=Depends(require_permissions('master_data.manage'))):
    obj = db.get(MasterValue, value_id)
    if not obj:
        raise HTTPException(status_code=404, detail='Value not found')
    for k,v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@router.delete('/values/{value_id}')
def delete_value(value_id: int, db: Session = Depends(get_db), user=Depends(require_permissions('master_data.manage'))):
    obj = db.get(MasterValue, value_id)
    if not obj:
        raise HTTPException(status_code=404, detail='Value not found')
    db.delete(obj); db.commit()
    return {'ok': True}
