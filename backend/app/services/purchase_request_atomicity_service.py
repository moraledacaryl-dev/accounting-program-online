from __future__ import annotations

from sqlalchemy.orm import Session, selectinload

from app.models.entities import PurchaseRequest, PurchaseRequestLine, Supplier
from app.schemas.procurement import PurchaseRequestCreate
from app.services.procurement_service import (
    PR_STATUSES,
    _apply_pr_lines,
    _norm,
    _serialize_pr,
    _today,
)
from app.services.code_service import generate_code


def create_purchase_request_uncommitted(
    db: Session,
    payload: PurchaseRequestCreate,
    *,
    username: str | None = None,
) -> dict:
    """Create a purchase request without committing.

    The API owns the outer transaction so the PR and its durable Operations
    outbox event are committed or rolled back together.
    """
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
    db.flush()

    stored = (
        db.query(PurchaseRequest)
        .options(
            selectinload(PurchaseRequest.lines).selectinload(PurchaseRequestLine.inventory_item),
            selectinload(PurchaseRequest.supplier),
        )
        .filter(PurchaseRequest.id == row.id)
        .populate_existing()
        .first()
    )
    return _serialize_pr(stored)
