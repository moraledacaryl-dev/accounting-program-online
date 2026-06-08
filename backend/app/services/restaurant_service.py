from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.entities import (
    Booking,
    BookingFolio,
    BookingFolioLine,
    InventoryItem,
    MenuItem,
    MenuPromotion,
    MenuSKU,
    MenuSKURecipeItem,
    PrepComponent,
    Record,
    SaleAccountingLink,
    SaleOrder,
    SaleOrderLine,
    SaleVoidEvent,
    StockMovement,
    StockMovementAccountingLink,
)
from app.services.accounting_service import autopost_record
from app.services.fifo_service import create_inbound_movement, create_outbound_movement
from app.services.guest_service import ensure_booking_folio
from app.services.taxonomy_service import get_module_by_slug, get_module_name


def _norm(value: str | None) -> str:
    return (value or '').strip().lower()


def _first_path(module_taxonomy: dict) -> tuple[str, str, str]:
    for category, buckets in module_taxonomy.items():
        if not isinstance(buckets, dict):
            continue
        for bucket, items in buckets.items():
            if isinstance(items, list) and items:
                return category, bucket, str(items[0])
    raise ValueError('No taxonomy path configured for module')


def _pick_path(module_taxonomy: dict, preferred_paths: Iterable[tuple[str, str, str]]) -> tuple[str, str, str]:
    by_norm_category = {str(k).strip().lower(): str(k) for k in module_taxonomy.keys()}
    for category_hint, bucket_hint, item_hint in preferred_paths:
        category_key = by_norm_category.get(_norm(category_hint))
        if not category_key:
            continue
        buckets = module_taxonomy.get(category_key) or {}
        by_norm_bucket = {str(k).strip().lower(): str(k) for k in buckets.keys()}
        bucket_key = by_norm_bucket.get(_norm(bucket_hint))
        if not bucket_key:
            continue
        items = buckets.get(bucket_key) or []
        by_norm_item = {str(x).strip().lower(): str(x) for x in items}
        item_key = by_norm_item.get(_norm(item_hint))
        if not item_key:
            continue
        return category_key, bucket_key, item_key
    return _first_path(module_taxonomy)


def create_approved_record(
    db: Session,
    *,
    module_slug: str,
    direction: str,
    amount: float,
    name: str,
    transaction_date: str | None,
    payment_method: str | None = None,
    counterparty: str | None = None,
    notes: str | None = None,
    document_ref: str | None = None,
    created_by: str | None = None,
    preferred_paths: Iterable[tuple[str, str, str]] = (),
) -> Record:
    module_taxonomy = get_module_by_slug(module_slug, db)
    category, bucket, item = _pick_path(module_taxonomy, preferred_paths)

    record = Record(
        module_slug=module_slug,
        module_name=get_module_name(module_slug),
        category=category,
        bucket=bucket,
        item=item,
        name=name,
        amount=float(amount or 0),
        direction=direction,
        payment_method=payment_method,
        counterparty=counterparty,
        transaction_date=transaction_date,
        workflow_status='approved',
        bir_status='internal_only',
        notes=notes,
        document_ref=document_ref,
        created_by=created_by,
        approved_by=created_by,
    )
    db.add(record)
    db.flush()
    autopost_record(db, record, commit=False)
    return record


def _component_batch_and_unit_cost(db: Session, component: PrepComponent) -> tuple[float, float]:
    total_batch_cost = 0.0
    for item in sorted(component.items, key=lambda x: (x.sort_order, x.id)):
        inv = db.get(InventoryItem, item.inventory_item_id)
        if not inv:
            continue
        qty = float(item.quantity or 0)
        wastage = max(float(item.wastage_percent or 0), 0.0)
        total_batch_cost += qty * float(inv.average_cost or 0) * (1 + (wastage / 100.0))
    unit_cost = (total_batch_cost / float(component.yield_quantity or 0)) if float(component.yield_quantity or 0) > 0 else 0.0
    return total_batch_cost, unit_cost


def compute_component_costing(db: Session, component: PrepComponent) -> dict:
    batch_cost, unit_cost = _component_batch_and_unit_cost(db, component)
    return {
        'component_id': component.id,
        'total_batch_cost': round(batch_cost, 4),
        'unit_cost': round(unit_cost, 4),
        'yield_quantity': float(component.yield_quantity or 0),
        'yield_unit': component.yield_unit,
    }


def compute_sku_costing(db: Session, sku: MenuSKU) -> dict:
    requirements = _expand_sku_recipe_to_inventory(db, sku, 1.0, strict_inventory=False)
    recipe_cost = 0.0
    for inventory_item_id, qty in requirements.items():
        item = db.get(InventoryItem, inventory_item_id)
        if not item:
            continue
        recipe_cost += float(qty or 0) * float(item.average_cost or 0)
    total_cost = recipe_cost + float(sku.packaging_cost or 0) + float(sku.labor_cost or 0) + float(sku.overhead_cost or 0)
    price = float(sku.price or 0)
    margin = ((price - total_cost) / price * 100.0) if price > 0 else None
    warning_status = 'no_price' if price <= 0 else ('danger' if (margin or 0) < 25 else ('warning' if (margin or 0) < 40 else 'ok'))
    return {
        'sku_id': sku.id,
        'recipe_cost': round(recipe_cost, 4),
        'total_cost': round(total_cost, 4),
        'price': round(price, 4),
        'margin_percent': round(margin, 4) if margin is not None else None,
        'warning_status': warning_status,
    }


def _expand_sku_recipe_to_inventory(db: Session, sku: MenuSKU, qty_multiplier: float, strict_inventory: bool) -> dict[int, float]:
    requirements: dict[int, float] = {}
    items = sorted(sku.recipe_items, key=lambda x: (x.sort_order, x.id))
    if strict_inventory and not items:
        raise ValueError(f'SKU "{sku.variant_name or sku.sku_code or sku.id}" has no recipe items.')

    for line in items:
        line_qty = float(line.quantity or 0) * qty_multiplier
        line_qty *= (1 + (max(float(line.wastage_percent or 0), 0.0) / 100.0))
        if line_qty <= 0:
            continue

        if _norm(line.line_type) == 'component':
            if not line.component_id:
                if strict_inventory:
                    raise ValueError('Component recipe line is missing component_id.')
                continue
            component = db.get(PrepComponent, line.component_id)
            if not component:
                if strict_inventory:
                    raise ValueError(f'Component {line.component_id} not found.')
                continue
            yield_qty = float(component.yield_quantity or 0)
            if yield_qty <= 0:
                if strict_inventory:
                    raise ValueError(f'Component "{component.name}" has invalid yield quantity.')
                continue
            for comp_item in component.items:
                expanded_qty = line_qty * (float(comp_item.quantity or 0) / yield_qty)
                expanded_qty *= (1 + (max(float(comp_item.wastage_percent or 0), 0.0) / 100.0))
                if expanded_qty <= 0:
                    continue
                requirements[comp_item.inventory_item_id] = requirements.get(comp_item.inventory_item_id, 0.0) + expanded_qty
        else:
            if not line.inventory_item_id:
                if strict_inventory:
                    raise ValueError('Inventory recipe line is missing inventory_item_id.')
                continue
            requirements[line.inventory_item_id] = requirements.get(line.inventory_item_id, 0.0) + line_qty

    return requirements


def _expand_menu_recipe_to_inventory(menu_item: MenuItem, qty_multiplier: float, strict_inventory: bool) -> dict[int, float]:
    requirements: dict[int, float] = {}
    if strict_inventory and not menu_item.recipe_lines:
        raise ValueError(f'Menu item "{menu_item.name}" has no recipe lines.')
    for line in menu_item.recipe_lines:
        line_qty = float(line.quantity or 0) * qty_multiplier
        if line_qty <= 0:
            continue
        requirements[line.inventory_item_id] = requirements.get(line.inventory_item_id, 0.0) + line_qty
    return requirements


def merge_inventory_requirements(base: dict[int, float], extra: dict[int, float]) -> dict[int, float]:
    merged = dict(base or {})
    for inventory_item_id, qty in (extra or {}).items():
        if float(qty or 0) <= 0:
            continue
        merged[inventory_item_id] = merged.get(inventory_item_id, 0.0) + float(qty)
    return merged


def expand_menu_or_sku_to_inventory_requirements(
    db: Session,
    *,
    menu_item: MenuItem,
    sku: MenuSKU | None,
    quantity: float,
    strict_inventory: bool,
) -> dict[int, float]:
    if sku:
        return _expand_sku_recipe_to_inventory(db, sku, quantity, strict_inventory)
    return _expand_menu_recipe_to_inventory(menu_item, quantity, strict_inventory)


def consume_inventory_requirements(
    db: Session,
    requirements: dict[int, float],
    *,
    reason: str,
    module_slug: str,
    reference_no: str | None,
    movement_date: str | None,
    notes_prefix: str,
    commit: bool = False,
) -> float:
    total_cost = 0.0
    for inventory_item_id, required_qty in (requirements or {}).items():
        if required_qty <= 0:
            continue
        inv_item = db.get(InventoryItem, inventory_item_id)
        if not inv_item:
            raise ValueError(f'Inventory item {inventory_item_id} referenced by recipe was not found.')
        movement = create_outbound_movement(
            db,
            inv_item,
            float(required_qty),
            reason=reason,
            module_slug=module_slug,
            reference_no=reference_no,
            notes=f'{notes_prefix} - {inv_item.name}',
            movement_date=movement_date,
            commit=False,
        )
        total_cost += float(movement.total_cost or 0)
    if commit:
        db.commit()
    return total_cost


def _promo_active_for_date(promo: MenuPromotion, order_date: str | None) -> bool:
    if not promo.is_active:
        return False
    if not order_date:
        return True
    if promo.start_date and order_date < promo.start_date:
        return False
    if promo.end_date and order_date > promo.end_date:
        return False
    return True


def _apply_promotion(base_unit_price: float, qty: float, promotions: list[MenuPromotion]) -> tuple[float, float, int | None]:
    best_price = base_unit_price
    best_promo_id = None
    for promo in promotions:
        min_qty = float(promo.min_qty or 0)
        if min_qty and qty < min_qty:
            continue
        promo_type = _norm(promo.promo_type)
        value = float(promo.promo_value or 0)
        if promo_type == 'percent_off':
            candidate = base_unit_price * (1 - (value / 100.0))
        elif promo_type == 'fixed_discount':
            candidate = max(base_unit_price - value, 0.0)
        elif promo_type == 'set_price':
            candidate = max(value, 0.0)
        else:
            continue
        if candidate < best_price:
            best_price = candidate
            best_promo_id = promo.id
    discount_amount = max((base_unit_price - best_price) * qty, 0.0)
    return best_price, discount_amount, best_promo_id


def generate_sale_order_no(db: Session) -> str:
    base = datetime.utcnow().strftime('SO-%Y%m%d-%H%M%S')
    suffix = int(db.query(func.count(SaleOrder.id)).scalar() or 0) + 1
    return f'{base}-{suffix}'


def _resolve_room_charge_folio(db: Session, payload, username: str | None = None) -> BookingFolio:
    folio_id = getattr(payload, 'folio_id', None)
    if folio_id:
        folio = db.get(BookingFolio, int(folio_id))
        if not folio:
            raise ValueError('Selected room folio was not found.')
        if _norm(folio.status) in {'closed', 'cancelled'}:
            raise ValueError('Selected room folio is already closed or cancelled.')
        return folio

    booking_id = getattr(payload, 'booking_id', None)
    if not booking_id:
        raise ValueError('Room charge sales need a selected in-house booking or open folio.')
    booking = db.get(Booking, int(booking_id))
    if not booking:
        raise ValueError('Selected booking was not found.')
    return ensure_booking_folio(db, booking, username=username or 'restaurant_ops')


def _upsert_sale_room_charge_line(
    db: Session,
    *,
    folio: BookingFolio,
    order: SaleOrder,
    amount: float,
    order_date: str | None,
    notes: str | None,
    username: str | None,
) -> BookingFolioLine | None:
    if amount <= 0:
        return None
    external_key = f'restaurant:sale_order:{order.order_no}:room_charge'
    line = (
        db.query(BookingFolioLine)
        .filter(
            BookingFolioLine.external_source == 'restaurant',
            BookingFolioLine.external_line_key == external_key,
        )
        .first()
    )
    if not line:
        line = BookingFolioLine(
            folio_id=folio.id,
            external_source='restaurant',
            external_line_key=external_key,
            created_by=username or 'restaurant_ops',
        )
    line.line_type = 'cafe_room_charge'
    line.description = f'Cafe / restaurant room charge {order.order_no}'
    line.quantity = 1
    line.unit_price = round(float(amount or 0), 4)
    line.amount = round(float(amount or 0), 4)
    line.transaction_date = order_date
    line.reference_no = order.order_no
    line.notes = notes or 'Posted from restaurant sale as a room charge'
    db.add(line)
    return line


def _add_sale_room_charge_void_line(
    db: Session,
    *,
    order: SaleOrder,
    void_date: str | None,
    reason: str,
    username: str | None,
) -> BookingFolioLine | None:
    original_key = f'restaurant:sale_order:{order.order_no}:room_charge'
    original = (
        db.query(BookingFolioLine)
        .filter(
            BookingFolioLine.external_source == 'restaurant',
            BookingFolioLine.external_line_key == original_key,
        )
        .first()
    )
    if not original:
        return None

    void_key = f'restaurant:sale_order:{order.order_no}:void'
    existing_void = (
        db.query(BookingFolioLine)
        .filter(
            BookingFolioLine.external_source == 'restaurant',
            BookingFolioLine.external_line_key == void_key,
        )
        .first()
    )
    if existing_void:
        return existing_void

    amount = abs(float(original.amount or order.net_amount or 0))
    if amount <= 0:
        return None
    line = BookingFolioLine(
        folio_id=original.folio_id,
        line_type='cafe_room_charge',
        description=f'Void cafe / restaurant room charge {order.order_no}',
        quantity=1,
        unit_price=round(-amount, 4),
        amount=round(-amount, 4),
        transaction_date=void_date,
        reference_no=f'{order.order_no}-VOID',
        external_source='restaurant',
        external_line_key=void_key,
        notes=f'Voided restaurant sale. Reason: {reason}',
        created_by=username or 'restaurant_ops',
    )
    db.add(line)
    return line


def create_sale_order(db: Session, payload, username: str | None = None) -> SaleOrder:
    lines = list(payload.lines or [])
    if not lines:
        raise ValueError('Sale order must contain at least one line.')

    order_date = payload.order_date or datetime.utcnow().strftime('%Y-%m-%d')
    order_no = (payload.order_no or '').strip() or generate_sale_order_no(db)
    external_source = (getattr(payload, 'external_source', None) or '').strip() or None
    external_id = (getattr(payload, 'external_id', None) or '').strip() or None
    if external_source != 'dedicated_pos_cloud' and not bool(getattr(payload, 'manual_fallback_confirmed', False)):
        raise ValueError('Manual Accounting sales are an outage fallback. Confirm POS is unavailable before posting.')

    if external_source and external_id:
        imported = db.query(SaleOrder).filter(
            SaleOrder.external_source == external_source,
            SaleOrder.external_id == external_id,
        ).first()
        if imported:
            return imported

    existing = db.query(SaleOrder).filter(SaleOrder.order_no == order_no).first()
    if existing:
        if external_source and existing.external_source == external_source:
            return existing
        raise ValueError(f'Order number {order_no} already exists.')

    room_charge_folio = None
    if _norm(payload.payment_method) == 'room_charge':
        room_charge_folio = _resolve_room_charge_folio(db, payload, username=username)

    order = SaleOrder(
        order_no=order_no,
        order_date=order_date,
        status='posted',
        payment_method=payload.payment_method,
        channel=payload.channel,
        counterparty=payload.counterparty,
        notes=payload.notes,
        external_source=external_source,
        external_id=external_id,
    )
    db.add(order)
    db.flush()

    gross_amount = 0.0
    total_discount = 0.0
    cogs_amount = 0.0

    for idx, line in enumerate(lines):
        menu_item = db.get(MenuItem, int(line.menu_item_id))
        if not menu_item:
            raise ValueError(f'Menu item {line.menu_item_id} not found.')

        sku = None
        if line.sku_id:
            sku = db.get(MenuSKU, int(line.sku_id))
            if not sku:
                raise ValueError(f'SKU {line.sku_id} not found.')
            if sku.menu_item_id != menu_item.id:
                raise ValueError('SKU does not belong to the selected menu item.')

        qty = float(line.quantity or 0)
        if qty <= 0:
            raise ValueError('Line quantity must be greater than zero.')

        base_unit_price = float(line.unit_price if line.unit_price is not None else (sku.price if sku else menu_item.price or 0))
        if external_source == 'dedicated_pos_cloud':
            promo_rows = []
        elif sku:
            promo_rows = db.query(MenuPromotion).filter(
                MenuPromotion.is_active == True,
                ((MenuPromotion.sku_id == sku.id) | (MenuPromotion.menu_item_id == menu_item.id))
            ).all()
        else:
            promo_rows = db.query(MenuPromotion).filter(
                MenuPromotion.is_active == True,
                MenuPromotion.menu_item_id == menu_item.id
            ).all()
        active_promos = [p for p in promo_rows if _promo_active_for_date(p, order_date)]

        promo_unit_price, promo_discount, _promo_id = _apply_promotion(base_unit_price, qty, active_promos)
        manual_discount = max(float(line.discount_amount or 0), 0.0)
        line_discount = promo_discount + manual_discount

        gross_line_amount = base_unit_price * qty
        net_line_amount = max(gross_line_amount - line_discount, 0.0)

        db.add(SaleOrderLine(
            sale_order_id=order.id,
            menu_item_id=menu_item.id,
            sku_id=sku.id if sku else None,
            item_name=(sku.variant_name if sku and sku.variant_name else menu_item.name),
            quantity=qty,
            unit_price=base_unit_price,
            discount_amount=round(line_discount, 4),
            line_total=round(net_line_amount, 4),
        ))

        requirements = expand_menu_or_sku_to_inventory_requirements(
            db,
            menu_item=menu_item,
            sku=sku,
            quantity=qty,
            strict_inventory=payload.strict_inventory,
        )
        cogs_amount += consume_inventory_requirements(
            db,
            requirements,
            reason='Orders',
            module_slug='inventory',
            reference_no=order_no,
            movement_date=order_date,
            notes_prefix=f'Auto deduction from sale order {order_no} line {idx + 1}',
        )

        gross_amount += gross_line_amount
        total_discount += line_discount

    net_amount = max(gross_amount - total_discount, 0.0)

    if room_charge_folio:
        _upsert_sale_room_charge_line(
            db,
            folio=room_charge_folio,
            order=order,
            amount=net_amount,
            order_date=order_date,
            notes=payload.notes,
            username=username,
        )

    auto_post = bool(getattr(payload, 'auto_post_accounting', False))
    income_record = None
    cogs_record = None
    if auto_post:
        income_record = create_approved_record(
            db,
            module_slug='restaurant',
            direction='income',
            amount=net_amount,
            name=f'Restaurant sale {order_no}',
            transaction_date=order_date,
            payment_method=payload.payment_method,
            counterparty=payload.counterparty,
            notes='Auto-generated from sale order',
            document_ref=order_no,
            created_by=username,
            preferred_paths=[
                ('Manual / Custom Income', 'Misc Income', 'Manual Sale Entry'),
                ('Sales', 'Food Sales', 'Pasta'),
            ],
        )

        cogs_record = create_approved_record(
            db,
            module_slug='inventory',
            direction='expense',
            amount=cogs_amount,
            name=f'COGS for sale {order_no}',
            transaction_date=order_date,
            payment_method='inventory',
            counterparty=None,
            notes='Auto-generated COGS from sale order inventory deduction',
            document_ref=order_no,
            created_by=username,
            preferred_paths=[
                ('Inventory Movements', 'Subtract (Stock Out)', 'Orders'),
                ('Adjustments', 'Negative Adjustment', 'Count Loss'),
            ],
        )

    order.gross_amount = round(gross_amount, 4)
    order.discount_amount = round(total_discount, 4)
    order.net_amount = round(net_amount, 4)
    order.cogs_amount = round(cogs_amount, 4)
    order.income_record_id = income_record.id if income_record else None
    order.cogs_record_id = cogs_record.id if cogs_record else None

    db.add(order)
    if income_record:
        db.add(SaleAccountingLink(sale_order_id=order.id, record_id=income_record.id, link_type='income'))
    if cogs_record:
        db.add(SaleAccountingLink(sale_order_id=order.id, record_id=cogs_record.id, link_type='cogs'))
    db.commit()
    db.refresh(order)
    return order


def void_sale_order(db: Session, order: SaleOrder, payload, username: str | None = None) -> SaleOrder:
    if not order:
        raise ValueError('Sale order not found.')
    if _norm(order.status) == 'voided':
        raise ValueError(f'Sale order {order.order_no} is already voided.')

    existing = db.query(SaleVoidEvent).filter(SaleVoidEvent.sale_order_id == order.id).first()
    if existing:
        raise ValueError(f'Sale order {order.order_no} already has a void event.')

    reason = (payload.reason or '').strip()
    if not reason:
        raise ValueError('Void reason is required.')
    void_date = payload.void_date or datetime.utcnow().strftime('%Y-%m-%d')
    reverse_inventory = bool(getattr(payload, 'reverse_inventory', True))
    auto_post_accounting = bool(getattr(payload, 'auto_post_accounting', False))

    reversal_ref = f'{order.order_no}-VOID'
    if reverse_inventory:
        for idx, line in enumerate(order.lines or []):
            menu_item = db.get(MenuItem, int(line.menu_item_id)) if line.menu_item_id else None
            if not menu_item:
                continue
            sku = db.get(MenuSKU, int(line.sku_id)) if line.sku_id else None
            requirements = expand_menu_or_sku_to_inventory_requirements(
                db,
                menu_item=menu_item,
                sku=sku,
                quantity=float(line.quantity or 0),
                strict_inventory=False,
            )
            for inventory_item_id, qty in requirements.items():
                if float(qty or 0) <= 0:
                    continue
                inv_item = db.get(InventoryItem, int(inventory_item_id))
                if not inv_item:
                    continue
                unit_cost = float(inv_item.average_cost or 0)
                create_inbound_movement(
                    db,
                    inv_item,
                    float(qty),
                    unit_cost,
                    None,
                    0,
                    0,
                    reason='Sale Void',
                    module_slug='inventory',
                    reference_no=reversal_ref,
                    notes=f'Inventory reversal from voided sale {order.order_no} line {idx + 1}',
                    movement_date=void_date,
                    commit=False,
                )

    income_reversal = None
    cogs_reversal = None
    if auto_post_accounting:
        net_amount = float(order.net_amount or 0)
        if net_amount != 0:
            income_reversal = create_approved_record(
                db,
                module_slug='restaurant',
                direction='income',
                amount=-net_amount,
                name=f'Reversal for voided sale {order.order_no}',
                transaction_date=void_date,
                payment_method=order.payment_method or 'cash',
                counterparty=order.counterparty,
                notes=f'Auto-generated income reversal for voided sale. Reason: {reason}',
                document_ref=reversal_ref,
                created_by=username,
                preferred_paths=[
                    ('Sales', 'Food Sales', 'Pasta'),
                    ('Manual / Custom Income', 'Misc Income', 'Manual Sale Entry'),
                ],
            )
            db.add(SaleAccountingLink(sale_order_id=order.id, record_id=income_reversal.id, link_type='income_reversal'))

        cogs_amount = float(order.cogs_amount or 0)
        if cogs_amount != 0:
            cogs_reversal = create_approved_record(
                db,
                module_slug='inventory',
                direction='expense',
                amount=-cogs_amount,
                name=f'COGS reversal for voided sale {order.order_no}',
                transaction_date=void_date,
                payment_method='inventory',
                counterparty=None,
                notes=f'Auto-generated COGS reversal for voided sale. Reason: {reason}',
                document_ref=reversal_ref,
                created_by=username,
                preferred_paths=[
                    ('Inventory Movements', 'Subtract (Stock Out)', 'Orders'),
                    ('Adjustments', 'Negative Adjustment', 'Count Loss'),
                ],
            )
            db.add(SaleAccountingLink(sale_order_id=order.id, record_id=cogs_reversal.id, link_type='cogs_reversal'))

    order.status = 'voided'
    order.notes = f'{(order.notes or "").strip()}\nVOID {void_date}: {reason}'.strip()
    db.add(order)
    db.flush()

    if _norm(order.payment_method) == 'room_charge':
        _add_sale_room_charge_void_line(
            db,
            order=order,
            void_date=void_date,
            reason=reason,
            username=username,
        )

    db.add(SaleVoidEvent(
        sale_order_id=order.id,
        void_date=void_date,
        reason=reason,
        reverse_inventory=reverse_inventory,
        auto_post_accounting=auto_post_accounting,
        income_reversal_record_id=income_reversal.id if income_reversal else None,
        cogs_reversal_record_id=cogs_reversal.id if cogs_reversal else None,
        created_by=username,
    ))

    db.commit()
    db.refresh(order)
    return order


def create_restock_expense_record(
    db: Session,
    *,
    movement: StockMovement,
    payment_method: str | None,
    counterparty: str | None,
    notes: str | None,
    module_slug: str = 'procurement',
    created_by: str | None = None,
) -> Record | None:
    amount = float(movement.total_cost or 0)
    if amount <= 0:
        return None

    existing = db.query(StockMovementAccountingLink).filter(
        StockMovementAccountingLink.stock_movement_id == movement.id,
        StockMovementAccountingLink.link_type == 'expense',
    ).first()
    if existing:
        return db.get(Record, existing.record_id)

    record = create_approved_record(
        db,
        module_slug=module_slug,
        direction='expense',
        amount=amount,
        name=f'Restocking {movement.reference_no or movement.id}',
        transaction_date=movement.movement_date,
        payment_method=payment_method,
        counterparty=counterparty,
        notes=notes or 'Auto-generated from stock in movement',
        document_ref=movement.reference_no,
        created_by=created_by,
        preferred_paths=[
            ('Purchase Orders', 'Food PO', 'Fresh Goods'),
            ('Receiving', 'Inventory Receiving', 'Accepted'),
            ('Inventory Movements', 'Add (Stock In)', 'Purchase'),
        ],
    )

    db.add(StockMovementAccountingLink(
        stock_movement_id=movement.id,
        record_id=record.id,
        link_type='expense',
    ))
    return record


def create_stockout_expense_record(
    db: Session,
    *,
    movement: StockMovement,
    counterparty: str | None,
    notes: str | None,
    module_slug: str = 'inventory',
    created_by: str | None = None,
) -> Record | None:
    amount = float(movement.total_cost or 0)
    if amount <= 0:
        return None

    existing = db.query(StockMovementAccountingLink).filter(
        StockMovementAccountingLink.stock_movement_id == movement.id,
        StockMovementAccountingLink.link_type == 'expense',
    ).first()
    if existing:
        return db.get(Record, existing.record_id)

    reason_label = (movement.reason or '').strip() or 'Stock Usage'
    record = create_approved_record(
        db,
        module_slug=module_slug or 'inventory',
        direction='expense',
        amount=amount,
        name=f'Inventory usage {movement.reference_no or movement.id}',
        transaction_date=movement.movement_date,
        payment_method='inventory',
        counterparty=counterparty,
        notes=notes or 'Auto-generated from stock out movement',
        document_ref=movement.reference_no,
        created_by=created_by,
        preferred_paths=[
            ('Inventory Movements', 'Subtract (Stock Out)', reason_label),
            ('Inventory Movements', 'Subtract (Stock Out)', 'Orders'),
            ('Adjustments', 'Negative Adjustment', 'Count Loss'),
        ],
    )

    db.add(StockMovementAccountingLink(
        stock_movement_id=movement.id,
        record_id=record.id,
        link_type='expense',
    ))
    return record
