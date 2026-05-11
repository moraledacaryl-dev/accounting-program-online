
from sqlalchemy.orm import Session
from app.models.entities import InventoryItem, StockMovement
from app.schemas.common import StockMovementCreate


def apply_stock_movement(db: Session, payload: StockMovementCreate):
    item = db.get(InventoryItem, payload.item_id)
    if not item:
        raise ValueError('Inventory item not found')

    qty = float(payload.quantity)
    unit_cost = float(payload.unit_cost or 0)
    if payload.movement_type not in {'in', 'out'}:
        raise ValueError('movement_type must be in or out')

    if payload.movement_type == 'in':
        old_total_value = float(item.quantity_on_hand or 0) * float(item.average_cost or 0)
        new_total_value = qty * unit_cost
        new_qty = float(item.quantity_on_hand or 0) + qty
        item.quantity_on_hand = new_qty
        item.average_cost = ((old_total_value + new_total_value) / new_qty) if new_qty > 0 else unit_cost
        total_cost = new_total_value
    else:
        if qty > float(item.quantity_on_hand or 0):
            raise ValueError('Cannot move out more stock than quantity_on_hand')
        item.quantity_on_hand = float(item.quantity_on_hand or 0) - qty
        total_cost = qty * float(item.average_cost or 0)

    mv = StockMovement(
        item_id=item.id,
        movement_type=payload.movement_type,
        quantity=qty,
        unit_cost=unit_cost if payload.movement_type == 'in' else float(item.average_cost or 0),
        total_cost=total_cost,
        reason=payload.reason,
        module_slug=payload.module_slug,
        reference_no=payload.reference_no,
        notes=payload.notes,
        movement_date=payload.movement_date,
    )
    db.add(item)
    db.add(mv)
    db.commit()
    db.refresh(mv)
    return mv
