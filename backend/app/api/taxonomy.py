from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.entities import TaxonomyNode
from app.schemas.common import TaxonomyNodeCreate, TaxonomyNodeUpdate
from app.services.taxonomy_service import get_taxonomy, get_module_by_slug
from app.api.deps import get_current_user, require_permissions

router = APIRouter()

@router.get('/')
def all_taxonomy(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return get_taxonomy(db)

@router.get('/nodes')
def list_nodes(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(TaxonomyNode).order_by(TaxonomyNode.module_name, TaxonomyNode.category, TaxonomyNode.bucket, TaxonomyNode.item).all()

@router.post('/nodes')
def create_node(payload: TaxonomyNodeCreate, db: Session = Depends(get_db), user=Depends(require_permissions('taxonomy.manage'))):
    obj = TaxonomyNode(**payload.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@router.put('/nodes/{node_id}')
def update_node(node_id: int, payload: TaxonomyNodeUpdate, db: Session = Depends(get_db), user=Depends(require_permissions('taxonomy.manage'))):
    obj = db.get(TaxonomyNode, node_id)
    if not obj:
        raise HTTPException(status_code=404, detail='Node not found')
    for k,v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@router.delete('/nodes/{node_id}')
def delete_node(node_id: int, db: Session = Depends(get_db), user=Depends(require_permissions('taxonomy.manage'))):
    obj = db.get(TaxonomyNode, node_id)
    if not obj:
        raise HTTPException(status_code=404, detail='Node not found')
    db.delete(obj); db.commit()
    return {'ok': True}

@router.get('/{module_slug}')
def module_taxonomy(module_slug: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return get_module_by_slug(module_slug, db)
