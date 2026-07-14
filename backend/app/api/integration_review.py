from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.api.deps import require_any_permissions, require_permissions
from app.db.database import get_db
from app.schemas.integration_review import IntegrationReviewCreate, IntegrationReviewDecision, IntegrationReviewRetry
from app.services.integration_review_service import accept_item, create_review_item, get_item, list_review_items, reject_item, retry_item, summary, _serialize

router = APIRouter()

@router.post('/intake')
def intake(payload: IntegrationReviewCreate, db: Session = Depends(get_db), user=Depends(require_any_permissions('integrations.manage', 'integrations.sync'))):
    try: return create_review_item(db, payload)
    except ValueError as e: db.rollback(); raise HTTPException(400, str(e))

@router.get('')
def list_items(status: str|None=None, source_app: str|None=None, financial_effect: str|None=None, q: str|None=None, limit: int=Query(200, ge=1, le=1000), db: Session=Depends(get_db), user=Depends(require_any_permissions('integrations.view','approvals.view'))):
    return list_review_items(db, status=status, source_app=source_app, financial_effect=financial_effect, q=q, limit=limit)

@router.get('/summary')
def get_summary(db: Session=Depends(get_db), user=Depends(require_any_permissions('integrations.view','approvals.view'))): return summary(db)

@router.get('/{item_id}')
def detail(item_id:int, db:Session=Depends(get_db), user=Depends(require_any_permissions('integrations.view','approvals.view'))):
    try: return _serialize(get_item(db,item_id))
    except ValueError as e: raise HTTPException(404,str(e))

@router.post('/{item_id}/accept')
def accept(item_id:int, payload:IntegrationReviewDecision, db:Session=Depends(get_db), user=Depends(require_any_permissions('integrations.manage','approvals.act'))):
    try: return accept_item(db,item_id,payload,getattr(user,'username',None))
    except ValueError as e: db.rollback(); raise HTTPException(400,str(e))

@router.post('/{item_id}/reject')
def reject(item_id:int, payload:IntegrationReviewDecision, db:Session=Depends(get_db), user=Depends(require_any_permissions('integrations.manage','approvals.act'))):
    try: return reject_item(db,item_id,payload.reason,getattr(user,'username',None))
    except ValueError as e: db.rollback(); raise HTTPException(400,str(e))

@router.post('/{item_id}/retry')
def retry(item_id:int, payload:IntegrationReviewRetry, db:Session=Depends(get_db), user=Depends(require_permissions('integrations.manage'))):
    try: return retry_item(db,item_id,getattr(user,'username',None))
    except ValueError as e: db.rollback(); raise HTTPException(400,str(e))
