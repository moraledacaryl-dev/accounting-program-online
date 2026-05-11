from __future__ import annotations
from sqlalchemy.orm import Session
from app.models.entities import InventoryItem, InventoryBatch, StockMovement, BatchAllocation

def recalc_average_cost(db: Session, item: InventoryItem):
    open_batches = db.query(InventoryBatch).filter(
        InventoryBatch.item_id == item.id,
        InventoryBatch.is_closed == False,
        InventoryBatch.quantity_remaining > 0
    ).all()
    total_qty = sum(float(b.quantity_remaining) for b in open_batches)
    total_val = sum(float(b.quantity_remaining) * float(b.unit_cost) for b in open_batches)
    item.quantity_on_hand = total_qty
    item.average_cost = (total_val / total_qty) if total_qty > 0 else 0

def create_inbound_movement(
    db: Session,
    item: InventoryItem,
    qty: float,
    unit_cost: float,
    total_item_cost: float | None,
    delivery_cost: float,
    other_cost: float,
    reason: str | None,
    module_slug: str | None,
    reference_no: str | None,
    notes: str | None,
    movement_date: str | None,
    supplier: str | None = None,
    commit: bool = True,
):
    total_item_cost = float(total_item_cost) if total_item_cost is not None else qty * unit_cost
    landed_total = total_item_cost + float(delivery_cost or 0) + float(other_cost or 0)
    landed_unit_cost = (landed_total / qty) if qty > 0 else 0.0
    mv = StockMovement(
        item_id=item.id,
        movement_type='in',
        quantity=qty,
        unit_cost=landed_unit_cost,
        total_cost=landed_total,
        reason=reason,
        module_slug=module_slug,
        reference_no=reference_no,
        notes=notes,
        movement_date=movement_date,
    )
    db.add(mv)
    db.flush()
    batch = InventoryBatch(
        item_id=item.id,
        batch_code=f"B{item.id}-{mv.id}",
        received_date=movement_date,
        reference_no=reference_no,
        supplier=supplier,
        quantity_in=qty,
        quantity_remaining=qty,
        unit_cost=landed_unit_cost,
        is_closed=False,
    )
    db.add(batch)
    db.flush()
    recalc_average_cost(db, item)
    db.add(item)
    db.add(mv)
    db.add(batch)
    if commit:
        db.commit()
        db.refresh(mv)
    else:
        db.flush()
    return mv

def create_outbound_movement(
    db: Session,
    item: InventoryItem,
    qty: float,
    reason: str | None,
    module_slug: str | None,
    reference_no: str | None,
    notes: str | None,
    movement_date: str | None,
    commit: bool = True,
):
    open_batches = db.query(InventoryBatch).filter(
        InventoryBatch.item_id == item.id,
        InventoryBatch.is_closed == False,
        InventoryBatch.quantity_remaining > 0
    ).order_by(InventoryBatch.received_date.asc().nulls_last(), InventoryBatch.id.asc()).all()
    available = sum(float(b.quantity_remaining) for b in open_batches)
    if qty > available:
        raise ValueError(f'Cannot move out {qty}. Only {available} available.')
    mv = StockMovement(
        item_id=item.id, movement_type='out', quantity=qty, unit_cost=0, total_cost=0,
        reason=reason, module_slug=module_slug, reference_no=reference_no, notes=notes, movement_date=movement_date
    )
    db.add(mv)
    db.flush()
    remaining = qty
    total_cost = 0.0
    first_cost = 0.0
    for batch in open_batches:
        if remaining <= 0:
            break
        take = min(float(batch.quantity_remaining), remaining)
        if take <= 0:
            continue
        batch.quantity_remaining = float(batch.quantity_remaining) - take
        if batch.quantity_remaining <= 0.000001:
            batch.quantity_remaining = 0
            batch.is_closed = True
        cost = take * float(batch.unit_cost)
        if first_cost == 0.0:
            first_cost = float(batch.unit_cost)
        total_cost += cost
        remaining -= take
        db.add(BatchAllocation(batch_id=batch.id, stock_movement_id=mv.id, quantity=take, unit_cost=batch.unit_cost, total_cost=cost))
        db.add(batch)
    mv.unit_cost = first_cost if qty > 0 else 0
    mv.total_cost = total_cost
    recalc_average_cost(db, item)
    db.add(item)
    db.add(mv)
    if commit:
        db.commit()
        db.refresh(mv)
    else:
        db.flush()
    return mv
