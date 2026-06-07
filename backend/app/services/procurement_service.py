from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    InventoryItem,
    Payable,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequest,
    PurchaseRequestLine,
    ReceivingLine,
    ReceivingRecord,
    StockMovement,
    Supplier,
)
from app.schemas.procurement import (
    ProcurementStatusAction,
    PurchaseOrderCreate,
    PurchaseOrderLineInput,
    PurchaseOrderUpdate,
    PurchaseRequestCreate,
    PurchaseRequestLineInput,
    PurchaseRequestUpdate,
    ReceivingCreate,
    ReceivingLineInput,
    ReceivingUpdate,
)
from app.services.code_service import generate_code
from app.services.fifo_service import create_inbound_movement, create_outbound_movement

PR_STATUSES = {'draft', 'submitted', 'approved', 'rejected', 'converted_to_po'}
PO_STATUSES = {'draft', 'issued', 'partially_received', 'fully_received', 'cancelled'}
RECEIVING_STATUSES = {'draft', 'posted', 'reversed'}


def _today() -> str:
    return datetime.utcnow().strftime('%Y-%m-%d')


def _norm(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value if value is not None else default)
    except Exception:
        return float(default)


def _serialize_pr_line(row: PurchaseRequestLine) -> dict:
    item = row.inventory_item
    return {
        'id': row.id,
        'purchase_request_id': row.purchase_request_id,
        'inventory_item_id': row.inventory_item_id,
        'inventory_item_name': item.name if item else None,
        'description': row.description,
        'quantity': float(row.quantity or 0),
        'unit': row.unit,
        'estimated_unit_cost': float(row.estimated_unit_cost or 0),
        'estimated_line_total': round(float(row.quantity or 0) * float(row.estimated_unit_cost or 0), 4),
        'notes': row.notes,
        'sort_order': row.sort_order,
    }


def _serialize_pr(row: PurchaseRequest) -> dict:
    supplier = row.supplier
    lines = sorted(row.lines or [], key=lambda x: (x.sort_order, x.id))
    estimated_total = sum(float(line.quantity or 0) * float(line.estimated_unit_cost or 0) for line in lines)
    return {
        'id': row.id,
        'request_no': row.request_no,
        'request_date': row.request_date,
        'needed_by_date': row.needed_by_date,
        'department': row.department,
        'supplier_id': row.supplier_id,
        'supplier_name': supplier.name if supplier else None,
        'status': row.status,
        'requested_by': row.requested_by,
        'approved_by': row.approved_by,
        'notes': row.notes,
        'estimated_total': round(estimated_total, 4),
        'lines': [_serialize_pr_line(line) for line in lines],
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_po_line(row: PurchaseOrderLine) -> dict:
    item = row.inventory_item
    return {
        'id': row.id,
        'purchase_order_id': row.purchase_order_id,
        'purchase_request_line_id': row.purchase_request_line_id,
        'inventory_item_id': row.inventory_item_id,
        'inventory_item_name': item.name if item else None,
        'description': row.description,
        'quantity_ordered': float(row.quantity_ordered or 0),
        'quantity_received': float(row.quantity_received or 0),
        'unit': row.unit,
        'unit_cost': float(row.unit_cost or 0),
        'line_total': float(row.line_total or 0),
        'notes': row.notes,
        'sort_order': row.sort_order,
    }


def _serialize_po(row: PurchaseOrder) -> dict:
    supplier = row.supplier
    lines = sorted(row.lines or [], key=lambda x: (x.sort_order, x.id))
    received = sum(float(line.quantity_received or 0) for line in lines)
    ordered = sum(float(line.quantity_ordered or 0) for line in lines)
    return {
        'id': row.id,
        'po_no': row.po_no,
        'po_date': row.po_date,
        'supplier_id': row.supplier_id,
        'supplier_name': supplier.name if supplier else None,
        'purchase_request_id': row.purchase_request_id,
        'status': row.status,
        'payment_terms': row.payment_terms,
        'expected_delivery_date': row.expected_delivery_date,
        'total_amount': float(row.total_amount or 0),
        'issued_by': row.issued_by,
        'approved_by': row.approved_by,
        'notes': row.notes,
        'progress_ordered_qty': round(ordered, 4),
        'progress_received_qty': round(received, 4),
        'lines': [_serialize_po_line(line) for line in lines],
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_receiving_line(row: ReceivingLine) -> dict:
    item = row.inventory_item
    return {
        'id': row.id,
        'receiving_record_id': row.receiving_record_id,
        'purchase_order_line_id': row.purchase_order_line_id,
        'inventory_item_id': row.inventory_item_id,
        'inventory_item_name': item.name if item else None,
        'description': row.description,
        'quantity_received': float(row.quantity_received or 0),
        'unit': row.unit,
        'unit_cost': float(row.unit_cost or 0),
        'line_total': float(row.line_total or 0),
        'notes': row.notes,
        'sort_order': row.sort_order,
    }


def _serialize_receiving(row: ReceivingRecord) -> dict:
    lines = sorted(row.lines or [], key=lambda x: (x.sort_order, x.id))
    return {
        'id': row.id,
        'receiving_no': row.receiving_no,
        'receiving_date': row.receiving_date,
        'supplier_id': row.supplier_id,
        'supplier_name': row.supplier.name if row.supplier else None,
        'purchase_order_id': row.purchase_order_id,
        'purchase_order_no': row.purchase_order.po_no if row.purchase_order else None,
        'status': row.status,
        'reference_no': row.reference_no,
        'total_amount': float(row.total_amount or 0),
        'received_by': row.received_by,
        'posted_by': row.posted_by,
        'notes': row.notes,
        'lines': [_serialize_receiving_line(line) for line in lines],
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def _apply_pr_lines(db: Session, row: PurchaseRequest, lines: list[PurchaseRequestLineInput]):
    for old in list(row.lines or []):
        db.delete(old)
    for idx, line in enumerate(lines or []):
        item = db.get(InventoryItem, int(line.inventory_item_id)) if line.inventory_item_id else None
        if line.inventory_item_id and not item:
            raise ValueError(f'inventory_item_id {line.inventory_item_id} not found.')
        db.add(
            PurchaseRequestLine(
                purchase_request_id=row.id,
                inventory_item_id=line.inventory_item_id,
                description=_norm(line.description),
                quantity=max(0.0, _to_float(line.quantity)),
                unit=(item.unit if item else _norm(line.unit)),
                estimated_unit_cost=max(0.0, _to_float(line.estimated_unit_cost)),
                notes=line.notes,
                sort_order=int(line.sort_order if line.sort_order is not None else idx),
            )
        )


def _apply_po_lines(db: Session, row: PurchaseOrder, lines: list[PurchaseOrderLineInput]):
    for old in list(row.lines or []):
        db.delete(old)
    total_amount = 0.0
    for idx, line in enumerate(lines or []):
        item = db.get(InventoryItem, int(line.inventory_item_id)) if line.inventory_item_id else None
        if line.inventory_item_id and not item:
            raise ValueError(f'inventory_item_id {line.inventory_item_id} not found.')
        quantity_ordered = max(0.0, _to_float(line.quantity_ordered))
        unit_cost = max(0.0, _to_float(line.unit_cost))
        line_total = round(quantity_ordered * unit_cost, 4)
        total_amount += line_total
        db.add(
            PurchaseOrderLine(
                purchase_order_id=row.id,
                purchase_request_line_id=line.purchase_request_line_id,
                inventory_item_id=line.inventory_item_id,
                description=_norm(line.description),
                quantity_ordered=quantity_ordered,
                quantity_received=0,
                unit=(item.unit if item else _norm(line.unit)),
                unit_cost=unit_cost,
                line_total=line_total,
                notes=line.notes,
                sort_order=int(line.sort_order if line.sort_order is not None else idx),
            )
        )
    row.total_amount = round(total_amount, 4)
    db.add(row)


def _apply_receiving_lines(db: Session, row: ReceivingRecord, lines: list[ReceivingLineInput]):
    for old in list(row.lines or []):
        db.delete(old)
    total_amount = 0.0
    for idx, line in enumerate(lines or []):
        item = db.get(InventoryItem, int(line.inventory_item_id)) if line.inventory_item_id else None
        if line.inventory_item_id and not item:
            raise ValueError(f'inventory_item_id {line.inventory_item_id} not found.')
        qty = max(0.0, _to_float(line.quantity_received))
        unit_cost = max(0.0, _to_float(line.unit_cost))
        line_total = round(qty * unit_cost, 4)
        total_amount += line_total
        db.add(
            ReceivingLine(
                receiving_record_id=row.id,
                purchase_order_line_id=line.purchase_order_line_id,
                inventory_item_id=line.inventory_item_id,
                description=_norm(line.description),
                quantity_received=qty,
                unit=(item.unit if item else _norm(line.unit)),
                unit_cost=unit_cost,
                line_total=line_total,
                notes=line.notes,
                sort_order=int(line.sort_order if line.sort_order is not None else idx),
            )
        )
    row.total_amount = round(total_amount, 4)
    db.add(row)


def _has_postable_receiving_lines(db: Session, receiving_record_id: int) -> bool:
    return bool(
        db.query(ReceivingLine.id)
        .filter(
            ReceivingLine.receiving_record_id == int(receiving_record_id),
            ReceivingLine.quantity_received > 0,
        )
        .first()
    )


def list_purchase_requests(db: Session, *, status: str | None = None, supplier_id: int | None = None):
    query = db.query(PurchaseRequest).options(selectinload(PurchaseRequest.lines).selectinload(PurchaseRequestLine.inventory_item), selectinload(PurchaseRequest.supplier))
    if status:
        query = query.filter(PurchaseRequest.status == status)
    if supplier_id:
        query = query.filter(PurchaseRequest.supplier_id == int(supplier_id))
    rows = query.order_by(PurchaseRequest.id.desc()).all()
    return [_serialize_pr(row) for row in rows]


def create_purchase_request(db: Session, payload: PurchaseRequestCreate, username: str | None = None):
    status = (payload.status or 'draft').strip()
    if status not in PR_STATUSES:
        raise ValueError(f'Invalid status: {status}.')
    if payload.supplier_id and not db.get(Supplier, int(payload.supplier_id)):
        raise ValueError('supplier_id not found.')
    row = PurchaseRequest(
        request_no=generate_code(db, 'purchase_request', requested_code=payload.request_no),
        request_date=_norm(payload.request_date) or _today(),
        needed_by_date=_norm(payload.needed_by_date),
        department=_norm(payload.department),
        supplier_id=payload.supplier_id,
        status=status,
        requested_by=username,
        approved_by=username if status in {'approved', 'converted_to_po'} else None,
        notes=payload.notes,
    )
    db.add(row)
    db.flush()
    _apply_pr_lines(db, row, payload.lines or [])
    db.commit()
    row = (
        db.query(PurchaseRequest)
        .options(selectinload(PurchaseRequest.lines).selectinload(PurchaseRequestLine.inventory_item), selectinload(PurchaseRequest.supplier))
        .filter(PurchaseRequest.id == row.id)
        .first()
    )
    return _serialize_pr(row)


def update_purchase_request(db: Session, pr_id: int, payload: PurchaseRequestUpdate, username: str | None = None):
    row = db.get(PurchaseRequest, int(pr_id))
    if not row:
        raise ValueError('Purchase request not found.')
    data = payload.model_dump(exclude_unset=True)
    if 'supplier_id' in data:
        supplier_id = data.get('supplier_id')
        if supplier_id and not db.get(Supplier, int(supplier_id)):
            raise ValueError('supplier_id not found.')
        row.supplier_id = supplier_id
    for key in ('request_date', 'needed_by_date', 'department', 'notes'):
        if key in data:
            setattr(row, key, _norm(data.get(key)))
    if 'status' in data:
        status = (data.get('status') or '').strip()
        if status not in PR_STATUSES:
            raise ValueError(f'Invalid status: {status}.')
        row.status = status
        row.approved_by = username if status in {'approved', 'converted_to_po'} else row.approved_by
    db.add(row)
    db.flush()
    if 'lines' in data and data.get('lines') is not None:
        _apply_pr_lines(db, row, data.get('lines') or [])
    db.commit()
    row = (
        db.query(PurchaseRequest)
        .options(selectinload(PurchaseRequest.lines).selectinload(PurchaseRequestLine.inventory_item), selectinload(PurchaseRequest.supplier))
        .filter(PurchaseRequest.id == row.id)
        .first()
    )
    return _serialize_pr(row)


def delete_purchase_request(db: Session, pr_id: int):
    row = db.get(PurchaseRequest, int(pr_id))
    if not row:
        raise ValueError('Purchase request not found.')
    db.delete(row)
    db.commit()
    return {'ok': True}


def set_purchase_request_status(db: Session, pr_id: int, payload: ProcurementStatusAction, username: str | None = None):
    row = db.get(PurchaseRequest, int(pr_id))
    if not row:
        raise ValueError('Purchase request not found.')
    status = (payload.status or '').strip()
    if status not in PR_STATUSES:
        raise ValueError(f'Invalid status: {status}.')
    row.status = status
    if payload.notes:
        row.notes = f'{row.notes or ""}\n{payload.notes}'.strip()
    if status in {'approved', 'converted_to_po'}:
        row.approved_by = username
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_pr(
        db.query(PurchaseRequest)
        .options(selectinload(PurchaseRequest.lines).selectinload(PurchaseRequestLine.inventory_item), selectinload(PurchaseRequest.supplier))
        .filter(PurchaseRequest.id == row.id)
        .first()
    )


def list_purchase_orders(db: Session, *, status: str | None = None, supplier_id: int | None = None):
    query = db.query(PurchaseOrder).options(
        selectinload(PurchaseOrder.lines).selectinload(PurchaseOrderLine.inventory_item),
        selectinload(PurchaseOrder.supplier),
        selectinload(PurchaseOrder.purchase_request),
    )
    if status:
        query = query.filter(PurchaseOrder.status == status)
    if supplier_id:
        query = query.filter(PurchaseOrder.supplier_id == int(supplier_id))
    rows = query.order_by(PurchaseOrder.id.desc()).all()
    return [_serialize_po(row) for row in rows]


def create_purchase_order(db: Session, payload: PurchaseOrderCreate, username: str | None = None):
    status = (payload.status or 'draft').strip()
    if status not in PO_STATUSES:
        raise ValueError(f'Invalid status: {status}.')
    if status in {'issued', 'partially_received', 'fully_received'} and not payload.supplier_id:
        raise ValueError('supplier_id is required before issuing or receiving a PO.')
    if payload.supplier_id and not db.get(Supplier, int(payload.supplier_id)):
        raise ValueError('supplier_id not found.')
    if payload.purchase_request_id and not db.get(PurchaseRequest, int(payload.purchase_request_id)):
        raise ValueError('purchase_request_id not found.')
    row = PurchaseOrder(
        po_no=generate_code(db, 'purchase_order', requested_code=payload.po_no),
        po_date=_norm(payload.po_date) or _today(),
        supplier_id=payload.supplier_id,
        purchase_request_id=payload.purchase_request_id,
        status=status,
        payment_terms=_norm(payload.payment_terms),
        expected_delivery_date=_norm(payload.expected_delivery_date),
        total_amount=0,
        issued_by=username if status in {'issued', 'partially_received', 'fully_received'} else None,
        approved_by=username if status in {'issued', 'partially_received', 'fully_received'} else None,
        notes=payload.notes,
    )
    db.add(row)
    db.flush()
    _apply_po_lines(db, row, payload.lines or [])
    if payload.purchase_request_id:
        pr = db.get(PurchaseRequest, int(payload.purchase_request_id))
        if pr and pr.status != 'converted_to_po':
            pr.status = 'converted_to_po'
            pr.approved_by = username if username else pr.approved_by
            db.add(pr)
    db.commit()
    row = (
        db.query(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.lines).selectinload(PurchaseOrderLine.inventory_item),
            selectinload(PurchaseOrder.supplier),
            selectinload(PurchaseOrder.purchase_request),
        )
        .filter(PurchaseOrder.id == row.id)
        .first()
    )
    return _serialize_po(row)


def update_purchase_order(db: Session, po_id: int, payload: PurchaseOrderUpdate, username: str | None = None):
    row = db.get(PurchaseOrder, int(po_id))
    if not row:
        raise ValueError('Purchase order not found.')
    data = payload.model_dump(exclude_unset=True)
    if 'supplier_id' in data:
        supplier_id = data.get('supplier_id')
        if supplier_id and not db.get(Supplier, int(supplier_id)):
            raise ValueError('supplier_id not found.')
        row.supplier_id = supplier_id
    if 'purchase_request_id' in data:
        pr_id = data.get('purchase_request_id')
        if pr_id and not db.get(PurchaseRequest, int(pr_id)):
            raise ValueError('purchase_request_id not found.')
        row.purchase_request_id = pr_id
    for key in ('po_date', 'payment_terms', 'expected_delivery_date', 'notes'):
        if key in data:
            setattr(row, key, _norm(data.get(key)))
    if 'status' in data:
        status = (data.get('status') or '').strip()
        if status not in PO_STATUSES:
            raise ValueError(f'Invalid status: {status}.')
        if status in {'issued', 'partially_received', 'fully_received'} and not row.supplier_id:
            raise ValueError('supplier_id is required before issuing or receiving a PO.')
        row.status = status
        if status in {'issued', 'partially_received', 'fully_received'}:
            row.issued_by = username if username else row.issued_by
            row.approved_by = username if username else row.approved_by
    db.add(row)
    db.flush()
    if 'lines' in data and data.get('lines') is not None:
        _apply_po_lines(db, row, data.get('lines') or [])
    db.commit()
    row = (
        db.query(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.lines).selectinload(PurchaseOrderLine.inventory_item),
            selectinload(PurchaseOrder.supplier),
            selectinload(PurchaseOrder.purchase_request),
        )
        .filter(PurchaseOrder.id == row.id)
        .first()
    )
    return _serialize_po(row)


def delete_purchase_order(db: Session, po_id: int):
    row = db.get(PurchaseOrder, int(po_id))
    if not row:
        raise ValueError('Purchase order not found.')
    if row.status != 'draft' or any(float(line.quantity_received or 0) > 0 for line in (row.lines or [])):
        raise ValueError('Only draft purchase orders without receiving activity can be deleted.')
    db.delete(row)
    db.commit()
    return {'ok': True}


def set_purchase_order_status(db: Session, po_id: int, payload: ProcurementStatusAction, username: str | None = None):
    row = db.get(PurchaseOrder, int(po_id))
    if not row:
        raise ValueError('Purchase order not found.')
    status = (payload.status or '').strip()
    if status not in PO_STATUSES:
        raise ValueError(f'Invalid status: {status}.')
    if status in {'issued', 'partially_received', 'fully_received'} and not row.supplier_id:
        raise ValueError('supplier_id is required before issuing or receiving a PO.')
    row.status = status
    if payload.notes:
        row.notes = f'{row.notes or ""}\n{payload.notes}'.strip()
    if status in {'issued', 'partially_received', 'fully_received'}:
        row.issued_by = username if username else row.issued_by
        row.approved_by = username if username else row.approved_by
    db.add(row)
    db.commit()
    return _serialize_po(
        db.query(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.lines).selectinload(PurchaseOrderLine.inventory_item),
            selectinload(PurchaseOrder.supplier),
            selectinload(PurchaseOrder.purchase_request),
        )
        .filter(PurchaseOrder.id == row.id)
        .first()
    )


def list_receiving_records(db: Session, *, status: str | None = None, supplier_id: int | None = None):
    query = db.query(ReceivingRecord).options(
        selectinload(ReceivingRecord.lines).selectinload(ReceivingLine.inventory_item),
        selectinload(ReceivingRecord.supplier),
        selectinload(ReceivingRecord.purchase_order),
    )
    if status:
        query = query.filter(ReceivingRecord.status == status)
    if supplier_id:
        query = query.filter(ReceivingRecord.supplier_id == int(supplier_id))
    rows = query.order_by(ReceivingRecord.id.desc()).all()
    return [_serialize_receiving(row) for row in rows]


def _post_receiving_to_stock(db: Session, receiving: ReceivingRecord):
    lines = (
        db.query(ReceivingLine)
        .filter(ReceivingLine.receiving_record_id == int(receiving.id))
        .order_by(ReceivingLine.sort_order.asc(), ReceivingLine.id.asc())
        .all()
    )
    for line in lines:
        if not line.inventory_item_id:
            continue
        item = db.get(InventoryItem, int(line.inventory_item_id))
        if not item:
            continue
        qty = float(line.quantity_received or 0)
        if qty <= 0:
            continue
        create_inbound_movement(
            db,
            item,
            qty,
            float(line.unit_cost or 0),
            None,
            0,
            0,
            reason='receiving',
            module_slug='procurement',
            reference_no=receiving.receiving_no or receiving.reference_no,
            notes=receiving.notes,
            movement_date=receiving.receiving_date,
            supplier=receiving.supplier.name if receiving.supplier else None,
            receiving_record_id=receiving.id,
            commit=False,
        )
        if line.purchase_order_line_id:
            po_line = db.get(PurchaseOrderLine, int(line.purchase_order_line_id))
            if po_line:
                po_line.quantity_received = round(float(po_line.quantity_received or 0) + qty, 4)
                db.add(po_line)
    _recalculate_purchase_order_receiving_status(db, receiving.purchase_order_id)


def _recalculate_purchase_order_receiving_status(db: Session, purchase_order_id: int | None):
    if not purchase_order_id:
        return
    po = db.get(PurchaseOrder, int(purchase_order_id))
    if not po:
        return
    ordered = sum(float(line.quantity_ordered or 0) for line in po.lines or [])
    received = sum(float(line.quantity_received or 0) for line in po.lines or [])
    if ordered > 0 and received >= ordered:
        po.status = 'fully_received'
    elif received > 0:
        po.status = 'partially_received'
    else:
        po.status = 'issued'
    db.add(po)


def _reverse_receiving_effects(db: Session, receiving: ReceivingRecord):
    if receiving.status != 'posted':
        raise ValueError('Only posted receiving records can be reversed.')

    payable = db.query(Payable).filter(
        Payable.source_type == 'receiving',
        Payable.source_id == int(receiving.id),
    ).first()
    if payable and float(payable.amount_paid or 0) > 0.0001:
        raise ValueError('Receiving cannot be reversed after its supplier bill has payments.')

    if receiving.posted_by:
        movements = db.query(StockMovement).filter(
            StockMovement.receiving_record_id == int(receiving.id),
            StockMovement.movement_type == 'in',
        ).order_by(StockMovement.id.asc()).all()
        if not movements:
            movements = db.query(StockMovement).filter(
                StockMovement.movement_type == 'in',
                StockMovement.reason == 'receiving',
                StockMovement.module_slug == 'procurement',
                StockMovement.reference_no == (receiving.receiving_no or receiving.reference_no),
            ).order_by(StockMovement.id.asc()).all()
        for movement in movements:
            item = db.get(InventoryItem, int(movement.item_id))
            if not item:
                raise ValueError(f'Inventory item {movement.item_id} for receiving reversal was not found.')
            create_outbound_movement(
                db,
                item,
                float(movement.quantity or 0),
                reason='receiving_reversal',
                module_slug='procurement',
                reference_no=f'REV-{receiving.receiving_no}',
                notes=f'Reversal of receiving {receiving.receiving_no}',
                movement_date=_today(),
                commit=False,
            )

        for line in receiving.lines or []:
            if not line.purchase_order_line_id:
                continue
            po_line = db.get(PurchaseOrderLine, int(line.purchase_order_line_id))
            if po_line:
                po_line.quantity_received = round(max(float(po_line.quantity_received or 0) - float(line.quantity_received or 0), 0), 4)
                db.add(po_line)
        _recalculate_purchase_order_receiving_status(db, receiving.purchase_order_id)

    if payable:
        payable.gross_amount = 0
        payable.balance_due = 0
        payable.status = 'cancelled'
        payable.closed_at = _today()
        payable.notes = f'{payable.notes or ""}\nCancelled by reversal of receiving {receiving.receiving_no}'.strip()
        db.add(payable)


def _maybe_create_payable_from_receiving(db: Session, receiving: ReceivingRecord):
    if receiving.total_amount <= 0:
        return None
    existing = (
        db.query(Payable)
        .filter(Payable.source_type == 'receiving', Payable.source_id == int(receiving.id))
        .first()
    )
    if existing:
        return existing
    from app.schemas.cashflow import PayableCreate
    from app.services.cashflow_service import create_payable

    supplier_name = receiving.supplier.name if receiving.supplier else 'Unknown Supplier'
    return create_payable(
        db,
        PayableCreate(
            source_type='receiving',
            source_id=receiving.id,
            supplier_name=supplier_name,
            payable_type='supplier_bill',
            bill_date=receiving.receiving_date,
            due_date=receiving.receiving_date,
            gross_amount=float(receiving.total_amount or 0),
            amount_paid=0,
            status='open',
            notes=f'Auto-created from receiving {receiving.receiving_no}',
            bir_include=True,
        ),
    )


def create_receiving_record(db: Session, payload: ReceivingCreate, username: str | None = None):
    status = (payload.status or 'draft').strip()
    if status not in RECEIVING_STATUSES:
        raise ValueError(f'Invalid status: {status}.')
    if status == 'reversed':
        raise ValueError('Create the receiving as draft or posted. Use the reversal action after posting.')
    if payload.supplier_id and not db.get(Supplier, int(payload.supplier_id)):
        raise ValueError('supplier_id not found.')
    if payload.purchase_order_id and not db.get(PurchaseOrder, int(payload.purchase_order_id)):
        raise ValueError('purchase_order_id not found.')
    row = ReceivingRecord(
        receiving_no=generate_code(db, 'receiving', requested_code=payload.receiving_no),
        receiving_date=_norm(payload.receiving_date) or _today(),
        supplier_id=payload.supplier_id,
        purchase_order_id=payload.purchase_order_id,
        status=status,
        reference_no=_norm(payload.reference_no),
        total_amount=0,
        received_by=username,
        notes=payload.notes,
    )
    db.add(row)
    db.flush()
    _apply_receiving_lines(db, row, payload.lines or [])
    db.flush()
    if row.status == 'posted':
        if not _has_postable_receiving_lines(db, row.id):
            raise ValueError('Receiving cannot be posted without at least one line with quantity.')
    if payload.post_to_stock and row.status == 'posted':
        _post_receiving_to_stock(db, row)
        row.posted_by = username
        db.add(row)
    if payload.auto_create_payable and row.status == 'posted':
        _maybe_create_payable_from_receiving(db, row)
    db.commit()
    row = (
        db.query(ReceivingRecord)
        .options(
            selectinload(ReceivingRecord.lines).selectinload(ReceivingLine.inventory_item),
            selectinload(ReceivingRecord.supplier),
            selectinload(ReceivingRecord.purchase_order),
        )
        .filter(ReceivingRecord.id == row.id)
        .first()
    )
    return _serialize_receiving(row)


def update_receiving_record(db: Session, receiving_id: int, payload: ReceivingUpdate, username: str | None = None):
    row = db.get(ReceivingRecord, int(receiving_id))
    if not row:
        raise ValueError('Receiving record not found.')
    if row.status != 'draft':
        raise ValueError('Posted or reversed receiving records are locked. Reverse a posted record instead of editing it.')
    data = payload.model_dump(exclude_unset=True)
    if 'supplier_id' in data:
        supplier_id = data.get('supplier_id')
        if supplier_id and not db.get(Supplier, int(supplier_id)):
            raise ValueError('supplier_id not found.')
        row.supplier_id = supplier_id
    if 'purchase_order_id' in data:
        po_id = data.get('purchase_order_id')
        if po_id and not db.get(PurchaseOrder, int(po_id)):
            raise ValueError('purchase_order_id not found.')
        row.purchase_order_id = po_id
    for key in ('receiving_date', 'reference_no', 'notes'):
        if key in data:
            setattr(row, key, _norm(data.get(key)))
    if 'status' in data:
        status = (data.get('status') or '').strip()
        if status not in RECEIVING_STATUSES:
            raise ValueError(f'Invalid status: {status}.')
        if status == 'reversed':
            raise ValueError('Use the reversal action to reverse a receiving record.')
        row.status = status
    db.add(row)
    db.flush()
    if 'lines' in data and data.get('lines') is not None:
        _apply_receiving_lines(db, row, data.get('lines') or [])
    db.flush()
    if row.status == 'posted':
        if not _has_postable_receiving_lines(db, row.id):
            raise ValueError('Receiving cannot be posted without at least one line with quantity.')
    if bool(data.get('post_to_stock', payload.post_to_stock)) and row.status == 'posted' and not row.posted_by:
        _post_receiving_to_stock(db, row)
        row.posted_by = username
        db.add(row)
    if bool(data.get('auto_create_payable', payload.auto_create_payable)) and row.status == 'posted':
        _maybe_create_payable_from_receiving(db, row)
    db.commit()
    row = (
        db.query(ReceivingRecord)
        .options(
            selectinload(ReceivingRecord.lines).selectinload(ReceivingLine.inventory_item),
            selectinload(ReceivingRecord.supplier),
            selectinload(ReceivingRecord.purchase_order),
        )
        .filter(ReceivingRecord.id == row.id)
        .first()
    )
    return _serialize_receiving(row)


def delete_receiving_record(db: Session, receiving_id: int):
    row = db.get(ReceivingRecord, int(receiving_id))
    if not row:
        raise ValueError('Receiving record not found.')
    if row.status != 'draft':
        raise ValueError('Only draft receiving records can be deleted.')
    db.delete(row)
    db.commit()
    return {'ok': True}


def set_receiving_status(db: Session, receiving_id: int, payload: ProcurementStatusAction, username: str | None = None):
    row = db.get(ReceivingRecord, int(receiving_id))
    if not row:
        raise ValueError('Receiving record not found.')
    status = (payload.status or '').strip()
    if status not in RECEIVING_STATUSES:
        raise ValueError(f'Invalid status: {status}.')
    if row.status == 'reversed':
        raise ValueError('Reversed receiving records cannot change status.')
    if status == 'reversed':
        _reverse_receiving_effects(db, row)
        row.status = 'reversed'
        row.notes = f'{row.notes or ""}\n{payload.notes or "Receiving reversed."}'.strip()
        db.add(row)
        db.commit()
        return _serialize_receiving(
            db.query(ReceivingRecord)
            .options(
                selectinload(ReceivingRecord.lines).selectinload(ReceivingLine.inventory_item),
                selectinload(ReceivingRecord.supplier),
                selectinload(ReceivingRecord.purchase_order),
            )
            .filter(ReceivingRecord.id == row.id)
            .first()
        )
    if row.status != 'draft':
        raise ValueError('Posted receiving records can only be reversed.')
    if status == 'posted':
        if not _has_postable_receiving_lines(db, row.id):
            raise ValueError('Receiving cannot be posted without at least one line with quantity.')
    row.status = status
    if payload.notes:
        row.notes = f'{row.notes or ""}\n{payload.notes}'.strip()
    if status == 'posted' and not row.posted_by:
        _post_receiving_to_stock(db, row)
        row.posted_by = username or 'system'
    if status == 'posted' and getattr(payload, 'auto_create_payable', True):
        _maybe_create_payable_from_receiving(db, row)
    db.add(row)
    db.commit()
    return _serialize_receiving(
        db.query(ReceivingRecord)
        .options(
            selectinload(ReceivingRecord.lines).selectinload(ReceivingLine.inventory_item),
            selectinload(ReceivingRecord.supplier),
            selectinload(ReceivingRecord.purchase_order),
        )
        .filter(ReceivingRecord.id == row.id)
        .first()
    )


def create_purchase_order_from_request(db: Session, pr_id: int, username: str | None = None):
    pr = (
        db.query(PurchaseRequest)
        .options(selectinload(PurchaseRequest.lines))
        .filter(PurchaseRequest.id == int(pr_id))
        .first()
    )
    if not pr:
        raise ValueError('Purchase request not found.')
    if not (pr.lines or []):
        raise ValueError('Purchase request has no lines.')
    po_payload = PurchaseOrderCreate(
        po_date=pr.request_date,
        supplier_id=pr.supplier_id,
        purchase_request_id=pr.id,
        status='issued',
        payment_terms=pr.supplier.payment_terms if pr.supplier else None,
        expected_delivery_date=pr.needed_by_date,
        notes=f'Auto-created from {pr.request_no}',
        lines=[
            PurchaseOrderLineInput(
                purchase_request_line_id=line.id,
                inventory_item_id=line.inventory_item_id,
                description=line.description,
                quantity_ordered=float(line.quantity or 0),
                unit=line.unit,
                unit_cost=float(line.estimated_unit_cost or 0),
                notes=line.notes,
                sort_order=line.sort_order,
            )
            for line in sorted(pr.lines or [], key=lambda x: (x.sort_order, x.id))
        ],
    )
    po = create_purchase_order(db, po_payload, username=username)
    pr.status = 'converted_to_po'
    pr.approved_by = username if username else pr.approved_by
    db.add(pr)
    db.commit()
    return po
