from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_any_permissions, require_permissions
from app.db.database import get_db
from app.models.entities import BatchAllocation, InventoryBatch, InventoryItem, StockMovement
from app.schemas.common import InventoryItemCreate, InventoryItemUpdate, StockMovementCreate
from app.services.fifo_service import create_inbound_movement, create_outbound_movement
from app.services.restaurant_service import create_restock_expense_record, create_stockout_expense_record

router = APIRouter()


@router.get('/items')
def items(db: Session = Depends(get_db), user=Depends(require_permissions('inventory.view'))):
    return db.query(InventoryItem).order_by(InventoryItem.name.asc()).all()


@router.post('/items')
def add_item(
    payload: InventoryItemCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('inventory.manage')),
):
    obj = InventoryItem(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put('/items/{item_id}')
def update_item(
    item_id: int,
    payload: InventoryItemUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('inventory.manage')),
):
    obj = db.get(InventoryItem, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail='Inventory item not found')
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete('/items/{item_id}')
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('inventory.manage')),
):
    obj = db.get(InventoryItem, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail='Inventory item not found')
    db.delete(obj)
    db.commit()
    return {'ok': True}


@router.get('/movements')
def movements(db: Session = Depends(get_db), user=Depends(require_permissions('inventory.view'))):
    return db.query(StockMovement).order_by(StockMovement.id.desc()).limit(500).all()


@router.post('/movements')
def add_movement(
    payload: StockMovementCreate,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('stock_movements.create', 'inventory.manage')),
):
    item = db.get(InventoryItem, payload.item_id)
    if not item:
        raise HTTPException(status_code=404, detail='Inventory item not found')
    if payload.movement_type not in {'in', 'out'}:
        raise HTTPException(status_code=400, detail='movement_type must be \"in\" or \"out\".')
    if float(payload.quantity or 0) <= 0:
        raise HTTPException(status_code=400, detail='Quantity must be greater than zero.')
    if payload.movement_type == 'in' and float(payload.unit_cost or 0) < 0:
        raise HTTPException(status_code=400, detail='Unit cost cannot be negative.')
    if payload.movement_type == 'in' and float(payload.total_item_cost or 0) < 0:
        raise HTTPException(status_code=400, detail='Total item cost cannot be negative.')
    if payload.movement_type == 'in' and float(payload.delivery_cost or 0) < 0:
        raise HTTPException(status_code=400, detail='Delivery cost cannot be negative.')
    if payload.movement_type == 'in' and float(payload.other_cost or 0) < 0:
        raise HTTPException(status_code=400, detail='Other cost cannot be negative.')

    try:
        if payload.movement_type == 'in':
            movement = create_inbound_movement(
                db,
                item,
                float(payload.quantity),
                float(payload.unit_cost or 0),
                float(payload.total_item_cost) if payload.total_item_cost is not None else None,
                float(payload.delivery_cost or 0),
                float(payload.other_cost or 0),
                payload.reason,
                payload.module_slug,
                payload.reference_no,
                payload.notes,
                payload.movement_date,
                payload.supplier,
                commit=False,
            )

            if payload.log_expense:
                create_restock_expense_record(
                    db,
                    movement=movement,
                    payment_method=payload.expense_payment_method,
                    counterparty=payload.expense_counterparty or payload.supplier,
                    notes=payload.expense_notes or payload.notes,
                    module_slug=payload.expense_module_slug or 'procurement',
                    created_by=getattr(user, 'username', None),
                )

            db.commit()
            db.refresh(movement)
            return movement

        movement = create_outbound_movement(
            db,
            item,
            float(payload.quantity),
            payload.reason,
            payload.module_slug,
            payload.reference_no,
            payload.notes,
            payload.movement_date,
            commit=False,
        )

        if payload.log_expense:
            create_stockout_expense_record(
                db,
                movement=movement,
                counterparty=payload.expense_counterparty,
                notes=payload.expense_notes or payload.notes,
                module_slug=payload.expense_module_slug or 'inventory',
                created_by=getattr(user, 'username', None),
            )

        db.commit()
        db.refresh(movement)
        return movement
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        db.rollback()
        raise


@router.get('/batches')
def batches(db: Session = Depends(get_db), user=Depends(require_permissions('inventory.view'))):
    return db.query(InventoryBatch).order_by(InventoryBatch.id.desc()).all()


@router.get('/allocations/{movement_id}')
def allocations(movement_id: int, db: Session = Depends(get_db), user=Depends(require_permissions('inventory.view'))):
    return db.query(BatchAllocation).filter(BatchAllocation.stock_movement_id == movement_id).all()


@router.get('/summary')
def summary(db: Session = Depends(get_db), user=Depends(require_permissions('inventory.view'))):
    items = db.query(InventoryItem).order_by(InventoryItem.name.asc()).all()
    return [
        {
            'id': i.id,
            'name': i.name,
            'quantity_on_hand': i.quantity_on_hand,
            'unit': i.unit,
            'reorder_level': i.reorder_level,
            'average_cost': i.average_cost,
        }
        for i in items
    ]
