import zipfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import require_any_permissions
from app.db.database import get_db
from app.services.setup_excel_service import XLSX_MIME, build_setup_import_template, import_setup_workbook

router = APIRouter()
MAX_WORKBOOK_BYTES = 10 * 1024 * 1024


@router.get('/template')
def download_template(
    scope: str = Query('all', pattern='^(all|menu)$'),
    user=Depends(require_any_permissions('inventory.view', 'menu.view', 'recipes.manage')),
):
    content = build_setup_import_template(scope=scope)
    filename = 'accounting-menu-import-template.xlsx' if scope == 'menu' else 'accounting-inventory-menu-import-template.xlsx'
    return Response(
        content=content,
        media_type=XLSX_MIME,
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@router.post('/import')
async def import_workbook(
    file: UploadFile = File(...),
    dry_run: bool = Form(False),
    replace_recipe_lines: bool = Form(True),
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('inventory.manage', 'menu.manage', 'recipes.manage', 'master_data.manage')),
):
    filename = (file.filename or '').lower()
    if not filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail='Upload an .xlsx workbook using the downloaded template.')
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail='Uploaded workbook is empty.')
    if len(content) > MAX_WORKBOOK_BYTES:
        raise HTTPException(status_code=413, detail='Workbook is too large. Keep the .xlsx file under 10 MB.')
    try:
        result = import_setup_workbook(
            db,
            content,
            dry_run=dry_run,
            replace_recipe_lines=replace_recipe_lines,
        )
        if dry_run:
            db.rollback()
        elif (result.get('counts') or {}).get('errors', 0):
            db.rollback()
            result['rolled_back'] = True
        else:
            db.commit()
        return result
    except zipfile.BadZipFile:  # type: ignore[name-defined]
        db.rollback()
        raise HTTPException(status_code=400, detail='The uploaded file is not a readable .xlsx workbook.')
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc) or 'Failed to import setup workbook.')
