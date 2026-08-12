from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import Receivable
from app.services import cashflow_service, restaurant_service


DEDICATED_POS_SOURCE = 'dedicated_pos_cloud'
POS_RECEIVABLE_SOURCE_TYPES = {'pos_room_charge', 'pos_room_charge_reversal'}
_pos_inventory_external: ContextVar[bool] = ContextVar('pos_inventory_external', default=False)
_installed = False

# Capture the stable base implementations once. The API modules import these
# functions by name, so install_pos_accounting_boundary() replaces those API
# globals while this module retains the original business implementations.
_base_consume_inventory = restaurant_service.consume_inventory_requirements
_base_create_sale = restaurant_service.create_sale_order
_base_void_sale = restaurant_service.void_sale_order
_base_create_receivable = cashflow_service.create_receivable


def _source(value: Any) -> str:
    return str(value or '').strip().lower()


def _guarded_consume_inventory(*args, **kwargs) -> float:
    """Never mutate Accounting's legacy stock ledger for dedicated POS sales.

    Inventory & Procurement is the physical-stock authority. Accounting keeps
    the financial sale mirror, while the dedicated Inventory app owns recipe
    consumption, FIFO/valuation, and reversal.
    """
    if _pos_inventory_external.get():
        return 0.0
    return float(_base_consume_inventory(*args, **kwargs) or 0)


def create_sale_order_with_pos_boundary(db: Session, payload, username: str | None = None):
    is_pos = _source(getattr(payload, 'external_source', None)) == DEDICATED_POS_SOURCE
    token = _pos_inventory_external.set(is_pos)
    try:
        return _base_create_sale(db, payload, username=username)
    finally:
        _pos_inventory_external.reset(token)


def void_sale_order_with_pos_boundary(db: Session, order, payload, username: str | None = None):
    if _source(getattr(order, 'external_source', None)) == DEDICATED_POS_SOURCE:
        # A POS void is already emitted to Inventory & Procurement as the
        # authoritative stock reversal. Accounting must never restore its
        # legacy inventory copy for the same business event.
        if hasattr(payload, 'model_copy'):
            payload = payload.model_copy(update={'reverse_inventory': False})
        else:
            try:
                payload.reverse_inventory = False
            except Exception:
                pass
    return _base_void_sale(db, order, payload, username=username)


def create_receivable_with_pos_idempotency(db: Session, payload):
    """Make POS room-charge delivery replay-safe at the Accounting receiver.

    POS outbox retries can repeat after a timeout where Accounting committed but
    the response was lost. source_type + source_id is the stable source key.
    """
    source_type = _source(getattr(payload, 'source_type', None))
    source_id = getattr(payload, 'source_id', None)
    if source_type in POS_RECEIVABLE_SOURCE_TYPES and source_id is not None:
        existing = (
            db.query(Receivable)
            .filter(Receivable.source_type == source_type, Receivable.source_id == int(source_id))
            .order_by(Receivable.id.asc())
            .first()
        )
        if existing:
            return cashflow_service._serialize_receivable(existing)
    return _base_create_receivable(db, payload)


def install_pos_accounting_boundary() -> None:
    """Install the dedicated POS receiver policy exactly once per process."""
    global _installed
    if _installed:
        return

    from app.api import menu as menu_api
    from app.api import receivables as receivables_api

    restaurant_service.consume_inventory_requirements = _guarded_consume_inventory
    menu_api.create_sale_order = create_sale_order_with_pos_boundary
    menu_api.void_sale_order = void_sale_order_with_pos_boundary
    receivables_api.create_receivable = create_receivable_with_pos_idempotency
    _installed = True
