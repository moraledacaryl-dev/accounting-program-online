from calendar import monthrange
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.entities import Asset, AssetDepreciationLog, AssetDisposalLog, AssetMaintenanceLog
from app.schemas.common import (
    AssetCreate,
    AssetDepreciationCreate,
    AssetDisposalCreate,
    AssetMaintenanceCreate,
    AssetUpdate,
)
from app.api.deps import require_permissions
from app.services.restaurant_service import create_approved_record

router = APIRouter()


def _monthly_depreciation(asset: Asset) -> float:
    cost = float(asset.acquisition_cost or 0)
    salvage = float(asset.salvage_value or 0)
    life = int(asset.useful_life_months or 0)
    depreciable = max(cost - salvage, 0.0)
    if life <= 0:
        return 0.0
    return round(depreciable / life, 4)


def _period_end(period_key: str) -> str:
    try:
        year, month = period_key.split('-', 1)
        y = int(year)
        m = int(month)
    except Exception as exc:
        raise ValueError('period_key must be in YYYY-MM format.') from exc
    if m < 1 or m > 12:
        raise ValueError('period_key month must be between 01 and 12.')
    end_day = monthrange(y, m)[1]
    return f'{y:04d}-{m:02d}-{end_day:02d}'


def _serialize_dep(log: AssetDepreciationLog) -> dict:
    return {
        'id': log.id,
        'asset_id': log.asset_id,
        'period_key': log.period_key,
        'depreciation_date': log.depreciation_date,
        'amount': log.amount,
        'record_id': log.record_id,
        'notes': log.notes,
        'created_by': log.created_by,
        'created_at': log.created_at,
    }


def _serialize_maintenance(log: AssetMaintenanceLog) -> dict:
    return {
        'id': log.id,
        'asset_id': log.asset_id,
        'service_date': log.service_date,
        'vendor': log.vendor,
        'amount': log.amount,
        'record_id': log.record_id,
        'notes': log.notes,
        'created_by': log.created_by,
        'created_at': log.created_at,
    }


def _serialize_disposal(log: AssetDisposalLog) -> dict:
    return {
        'id': log.id,
        'asset_id': log.asset_id,
        'disposal_date': log.disposal_date,
        'proceeds_amount': log.proceeds_amount,
        'writeoff_amount': log.writeoff_amount,
        'income_record_id': log.income_record_id,
        'expense_record_id': log.expense_record_id,
        'notes': log.notes,
        'created_by': log.created_by,
        'created_at': log.created_at,
    }


@router.get('/assets')
def assets(db: Session = Depends(get_db), user=Depends(require_permissions('assets.view'))):
    return db.query(Asset).order_by(Asset.id.desc()).all()

@router.post('/assets')
def add_asset(payload: AssetCreate, db: Session = Depends(get_db), user=Depends(require_permissions('assets.manage'))):
    try:
        obj = Asset(**payload.model_dump(exclude={'acquisition_date', 'payment_method', 'counterparty', 'auto_post_accounting'}))
        db.add(obj)
        db.flush()

        if payload.auto_post_accounting and float(payload.acquisition_cost or 0) > 0:
            create_approved_record(
                db,
                module_slug='assets',
                direction='asset',
                amount=float(payload.acquisition_cost or 0),
                name=f'Asset acquisition {obj.name}',
                transaction_date=payload.acquisition_date,
                payment_method=payload.payment_method,
                counterparty=payload.counterparty,
                notes='Auto-generated from asset registry create',
                document_ref=f'ASSET-{obj.id}',
                created_by=getattr(user, 'username', None),
                preferred_paths=[
                    ('Asset Acquisition', 'Purchase', 'New Purchase'),
                    ('Asset Acquisition', 'Capitalization', 'Initial Recognition'),
                    ('Asset Classes', 'Equipment', 'Freezer'),
                ],
            )

        db.commit()
        db.refresh(obj)
        return obj
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.put('/assets/{asset_id}')
def update_asset(asset_id: int, payload: AssetUpdate, db: Session = Depends(get_db), user=Depends(require_permissions('assets.manage'))):
    obj = db.get(Asset, asset_id)
    if not obj:
        raise HTTPException(status_code=404, detail='Asset not found')
    for k,v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.get('/depreciation-logs')
def depreciation_logs(asset_id: int | None = None, db: Session = Depends(get_db), user=Depends(require_permissions('assets.view'))):
    q = db.query(AssetDepreciationLog)
    if asset_id:
        q = q.filter(AssetDepreciationLog.asset_id == asset_id)
    rows = q.order_by(AssetDepreciationLog.id.desc()).limit(500).all()
    return [_serialize_dep(x) for x in rows]


@router.post('/assets/{asset_id}/depreciate')
def depreciate_asset(
    asset_id: int,
    payload: AssetDepreciationCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('assets.manage')),
):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail='Asset not found')

    existing = db.query(AssetDepreciationLog).filter(
        AssetDepreciationLog.asset_id == asset.id,
        AssetDepreciationLog.period_key == payload.period_key,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f'Asset already has depreciation for {payload.period_key}.')

    try:
        tx_date = payload.depreciation_date or _period_end(payload.period_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    amount = float(payload.amount if payload.amount is not None else _monthly_depreciation(asset))
    if amount <= 0:
        raise HTTPException(status_code=400, detail='Depreciation amount must be greater than zero.')

    record = None
    try:
        if payload.auto_post_accounting:
            record = create_approved_record(
                db,
                module_slug='assets',
                direction='expense',
                amount=amount,
                name=f'Depreciation {asset.name} {payload.period_key}',
                transaction_date=tx_date,
                payment_method='accumulated_depreciation',
                counterparty=asset.name,
                notes='Auto-generated asset depreciation entry',
                document_ref=f'ASSET-DEP-{asset.id}-{payload.period_key}',
                created_by=getattr(user, 'username', None),
                preferred_paths=[
                    ('Depreciation', 'Monthly', 'Straight-Line'),
                    ('Asset Classes', 'Equipment', 'Freezer'),
                ],
            )

        log = AssetDepreciationLog(
            asset_id=asset.id,
            period_key=payload.period_key,
            depreciation_date=tx_date,
            amount=amount,
            record_id=record.id if record else None,
            notes=payload.notes,
            created_by=getattr(user, 'username', None),
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return _serialize_dep(log)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/assets/depreciate-batch')
def depreciate_batch(
    payload: AssetDepreciationCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('assets.manage')),
):
    try:
        tx_date = payload.depreciation_date or _period_end(payload.period_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    assets = db.query(Asset).filter(Asset.operational_status != 'Disposed').order_by(Asset.id.asc()).all()
    created = []
    skipped = []
    for asset in assets:
        already = db.query(AssetDepreciationLog).filter(
            AssetDepreciationLog.asset_id == asset.id,
            AssetDepreciationLog.period_key == payload.period_key,
        ).first()
        if already:
            skipped.append({'asset_id': asset.id, 'reason': 'already_depreciated'})
            continue
        amount = float(payload.amount if payload.amount is not None else _monthly_depreciation(asset))
        if amount <= 0:
            skipped.append({'asset_id': asset.id, 'reason': 'no_depreciable_amount'})
            continue

        record = None
        if payload.auto_post_accounting:
            record = create_approved_record(
                db,
                module_slug='assets',
                direction='expense',
                amount=amount,
                name=f'Depreciation {asset.name} {payload.period_key}',
                transaction_date=tx_date,
                payment_method='accumulated_depreciation',
                counterparty=asset.name,
                notes='Auto-generated asset depreciation entry (batch)',
                document_ref=f'ASSET-DEP-{asset.id}-{payload.period_key}',
                created_by=getattr(user, 'username', None),
                preferred_paths=[
                    ('Depreciation', 'Monthly', 'Straight-Line'),
                    ('Asset Classes', 'Equipment', 'Freezer'),
                ],
            )
        log = AssetDepreciationLog(
            asset_id=asset.id,
            period_key=payload.period_key,
            depreciation_date=tx_date,
            amount=amount,
            record_id=record.id if record else None,
            notes=payload.notes,
            created_by=getattr(user, 'username', None),
        )
        db.add(log)
        db.flush()
        created.append(_serialize_dep(log))

    db.commit()
    return {'created': created, 'skipped': skipped, 'period_key': payload.period_key}


@router.get('/maintenance-logs')
def maintenance_logs(asset_id: int | None = None, db: Session = Depends(get_db), user=Depends(require_permissions('assets.view'))):
    q = db.query(AssetMaintenanceLog)
    if asset_id:
        q = q.filter(AssetMaintenanceLog.asset_id == asset_id)
    rows = q.order_by(AssetMaintenanceLog.id.desc()).limit(500).all()
    return [_serialize_maintenance(x) for x in rows]


@router.post('/assets/{asset_id}/maintenance')
def add_maintenance(
    asset_id: int,
    payload: AssetMaintenanceCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('assets.manage')),
):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail='Asset not found')
    if float(payload.amount or 0) <= 0:
        raise HTTPException(status_code=400, detail='Maintenance amount must be greater than zero.')

    tx_date = payload.service_date or datetime.utcnow().strftime('%Y-%m-%d')
    record = None
    try:
        if payload.auto_post_accounting:
            record = create_approved_record(
                db,
                module_slug='assets',
                direction='expense',
                amount=float(payload.amount or 0),
                name=f'Asset maintenance {asset.name}',
                transaction_date=tx_date,
                payment_method=payload.payment_method,
                counterparty=payload.vendor,
                notes='Auto-generated asset maintenance expense',
                document_ref=f'ASSET-MAINT-{asset.id}-{tx_date}',
                created_by=getattr(user, 'username', None),
                preferred_paths=[
                    ('Maintenance', 'Preventive', 'Scheduled Maintenance'),
                    ('Maintenance', 'Corrective', 'Repairs'),
                ],
            )

        log = AssetMaintenanceLog(
            asset_id=asset.id,
            service_date=tx_date,
            vendor=payload.vendor,
            amount=float(payload.amount or 0),
            record_id=record.id if record else None,
            notes=payload.notes,
            created_by=getattr(user, 'username', None),
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return _serialize_maintenance(log)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get('/disposal-logs')
def disposal_logs(asset_id: int | None = None, db: Session = Depends(get_db), user=Depends(require_permissions('assets.view'))):
    q = db.query(AssetDisposalLog)
    if asset_id:
        q = q.filter(AssetDisposalLog.asset_id == asset_id)
    rows = q.order_by(AssetDisposalLog.id.desc()).limit(500).all()
    return [_serialize_disposal(x) for x in rows]


@router.post('/assets/{asset_id}/dispose')
def dispose_asset(
    asset_id: int,
    payload: AssetDisposalCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('assets.manage')),
):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail='Asset not found')

    tx_date = payload.disposal_date or datetime.utcnow().strftime('%Y-%m-%d')
    income_record = None
    expense_record = None
    try:
        if payload.auto_post_accounting and float(payload.proceeds_amount or 0) > 0:
            income_record = create_approved_record(
                db,
                module_slug='assets',
                direction='income',
                amount=float(payload.proceeds_amount or 0),
                name=f'Asset disposal proceeds {asset.name}',
                transaction_date=tx_date,
                payment_method=payload.payment_method,
                counterparty=asset.name,
                notes='Auto-generated asset disposal proceeds',
                document_ref=f'ASSET-DISPOSE-{asset.id}-{tx_date}',
                created_by=getattr(user, 'username', None),
                preferred_paths=[
                    ('Disposal', 'Sale', 'Asset Sale Proceeds'),
                    ('Asset Classes', 'Equipment', 'Freezer'),
                ],
            )

        if payload.auto_post_accounting and float(payload.writeoff_amount or 0) > 0:
            expense_record = create_approved_record(
                db,
                module_slug='assets',
                direction='expense',
                amount=float(payload.writeoff_amount or 0),
                name=f'Asset disposal writeoff {asset.name}',
                transaction_date=tx_date,
                payment_method='accumulated_depreciation',
                counterparty=asset.name,
                notes='Auto-generated asset disposal writeoff',
                document_ref=f'ASSET-DISPOSE-{asset.id}-{tx_date}',
                created_by=getattr(user, 'username', None),
                preferred_paths=[
                    ('Disposal', 'Writeoff', 'Loss on Disposal'),
                    ('Asset Classes', 'Equipment', 'Freezer'),
                ],
            )

        asset.operational_status = 'Disposed'
        db.add(asset)
        log = AssetDisposalLog(
            asset_id=asset.id,
            disposal_date=tx_date,
            proceeds_amount=float(payload.proceeds_amount or 0),
            writeoff_amount=float(payload.writeoff_amount or 0),
            income_record_id=income_record.id if income_record else None,
            expense_record_id=expense_record.id if expense_record else None,
            notes=payload.notes,
            created_by=getattr(user, 'username', None),
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return _serialize_disposal(log)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
