from __future__ import annotations
import json
from pathlib import Path
from sqlalchemy.orm import Session
from app.models.entities import TaxonomyNode

ROOT = Path(__file__).resolve().parents[3]
TAXONOMY_PATH = ROOT / 'shared' / 'taxonomy.json'
MODULE_INDEX_PATH = ROOT / 'shared' / 'module_index.json'

def load_taxonomy_file():
    return json.loads(TAXONOMY_PATH.read_text(encoding='utf-8'))

def load_module_index():
    return json.loads(MODULE_INDEX_PATH.read_text(encoding='utf-8'))

def get_module_name(module_slug: str) -> str:
    return load_module_index().get(module_slug, module_slug)

def build_taxonomy_from_db(db: Session):
    rows = db.query(TaxonomyNode).filter(TaxonomyNode.is_active == True).order_by(TaxonomyNode.module_name, TaxonomyNode.category, TaxonomyNode.bucket, TaxonomyNode.item).all()
    out = {}
    for r in rows:
        out.setdefault(r.module_name, {}).setdefault(r.category, {}).setdefault(r.bucket, [])
        if r.item not in out[r.module_name][r.category][r.bucket]:
            out[r.module_name][r.category][r.bucket].append(r.item)
    return out

def get_taxonomy(db: Session | None = None):
    if db is not None:
        built = build_taxonomy_from_db(db)
        if built:
            return built
    return load_taxonomy_file()

def get_module_by_slug(module_slug: str, db: Session | None = None):
    module_name = get_module_name(module_slug)
    return get_taxonomy(db).get(module_name, {})

def validate_record(module_slug: str, category: str, bucket: str, item: str, db: Session | None = None):
    module = get_module_by_slug(module_slug, db)
    if category not in module:
        return False, f'Invalid category for {module_slug}: {category}'
    if bucket not in module[category]:
        return False, f'Invalid subcategory for {module_slug}/{category}: {bucket}'
    if item not in module[category][bucket]:
        return False, f'Invalid level-3 item for {module_slug}/{category}/{bucket}: {item}'
    return True, None
