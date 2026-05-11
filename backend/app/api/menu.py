from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_any_permissions, require_permissions
from app.db.database import get_db
from app.models.entities import (
    InventoryItem,
    MenuItem,
    MenuPromotion,
    MenuSKU,
    MenuSKURecipeItem,
    PrepComponent,
    PrepComponentItem,
    RecipeLine,
    SaleOrder,
    SaleVoidEvent,
)
from app.schemas.common import (
    MenuItemCreate,
    MenuItemUpdate,
    MenuPromotionCreate,
    MenuPromotionUpdate,
    MenuSKUCreate,
    MenuSKUUpdate,
    PrepComponentCreate,
    PrepComponentItemPayload,
    PrepComponentUpdate,
    RecipeLineCreate,
    SaleOrderCreate,
    SaleVoidPayload,
    StaffMealCreate,
)
from app.services.hospitality_service import create_staff_meal_log, list_staff_meal_logs
from app.services.restaurant_service import compute_component_costing, compute_sku_costing, create_sale_order, void_sale_order

router = APIRouter()


def _to_line_type(value: str | None) -> str:
    return (value or "inventory").strip().lower()


def _validate_component_items(items: list[PrepComponentItemPayload], db: Session):
    for row in items:
        if float(row.quantity or 0) <= 0:
            raise ValueError('Component item quantity must be greater than zero.')
        inv = db.get(InventoryItem, int(row.inventory_item_id))
        if not inv:
            raise ValueError(f'Inventory item {row.inventory_item_id} not found.')


def _validate_sku_recipe_items(items: list, db: Session):
    for row in items:
        if float(row.quantity or 0) <= 0:
            raise ValueError('SKU recipe quantity must be greater than zero.')
        line_type = _to_line_type(getattr(row, 'line_type', None))
        if line_type == 'component':
            component_id = getattr(row, 'component_id', None)
            if not component_id:
                raise ValueError('Component recipe line requires component_id.')
            component = db.get(PrepComponent, int(component_id))
            if not component:
                raise ValueError(f'Component {component_id} not found.')
        else:
            inventory_item_id = getattr(row, 'inventory_item_id', None)
            if not inventory_item_id:
                raise ValueError('Inventory recipe line requires inventory_item_id.')
            inv = db.get(InventoryItem, int(inventory_item_id))
            if not inv:
                raise ValueError(f'Inventory item {inventory_item_id} not found.')


def _validate_promo_dates(start_date: str | None, end_date: str | None):
    if start_date and end_date and end_date < start_date:
        raise ValueError('Promotion end_date cannot be earlier than start_date.')


def _normalize_promo_fields(
    db: Session,
    applies_to: str,
    sku_id: int | None,
    menu_item_id: int | None,
) -> tuple[str, int | None, int | None]:
    applies_to_norm = (applies_to or 'sku').strip().lower()
    if applies_to_norm not in {'sku', 'menu_item'}:
        raise ValueError('applies_to must be "sku" or "menu_item".')

    if applies_to_norm == 'sku':
        if not sku_id:
            raise ValueError('sku_id is required when applies_to is "sku".')
        sku = db.get(MenuSKU, int(sku_id))
        if not sku:
            raise ValueError(f'SKU {sku_id} not found.')
        return applies_to_norm, sku.id, sku.menu_item_id

    if not menu_item_id:
        raise ValueError('menu_item_id is required when applies_to is "menu_item".')
    menu_item = db.get(MenuItem, int(menu_item_id))
    if not menu_item:
        raise ValueError(f'Menu item {menu_item_id} not found.')
    return applies_to_norm, None, menu_item.id


def _serialize_component(component: PrepComponent, include_items: bool = True) -> dict:
    data = {
        'id': component.id,
        'name': component.name,
        'category_name': component.category_name,
        'yield_quantity': component.yield_quantity,
        'yield_unit': component.yield_unit,
        'is_active': component.is_active,
        'notes': component.notes,
        'created_at': component.created_at,
        'updated_at': component.updated_at,
    }
    if include_items:
        data['items'] = [
            {
                'id': item.id,
                'component_id': item.component_id,
                'inventory_item_id': item.inventory_item_id,
                'quantity': item.quantity,
                'unit': item.unit,
                'wastage_percent': item.wastage_percent,
                'sort_order': item.sort_order,
                'notes': item.notes,
            }
            for item in sorted(component.items or [], key=lambda x: (x.sort_order, x.id))
        ]
    return data


def _serialize_sku(sku: MenuSKU, include_recipe_items: bool = True) -> dict:
    data = {
        'id': sku.id,
        'menu_item_id': sku.menu_item_id,
        'sku_code': sku.sku_code,
        'variant_name': sku.variant_name,
        'size_label': sku.size_label,
        'price': sku.price,
        'packaging_cost': sku.packaging_cost,
        'labor_cost': sku.labor_cost,
        'overhead_cost': sku.overhead_cost,
        'is_active': sku.is_active,
        'notes': sku.notes,
        'created_at': sku.created_at,
        'updated_at': sku.updated_at,
    }
    if include_recipe_items:
        data['recipe_items'] = [
            {
                'id': row.id,
                'sku_id': row.sku_id,
                'line_type': row.line_type,
                'inventory_item_id': row.inventory_item_id,
                'component_id': row.component_id,
                'quantity': row.quantity,
                'unit': row.unit,
                'wastage_percent': row.wastage_percent,
                'sort_order': row.sort_order,
                'notes': row.notes,
            }
            for row in sorted(sku.recipe_items or [], key=lambda x: (x.sort_order, x.id))
        ]
    return data


def _serialize_sale(order: SaleOrder, include_lines: bool = True) -> dict:
    latest_void = None
    if order.void_events:
        latest_void = sorted(order.void_events, key=lambda x: x.id, reverse=True)[0]
    data = {
        'id': order.id,
        'order_no': order.order_no,
        'order_date': order.order_date,
        'status': order.status,
        'payment_method': order.payment_method,
        'channel': order.channel,
        'counterparty': order.counterparty,
        'gross_amount': order.gross_amount,
        'discount_amount': order.discount_amount,
        'net_amount': order.net_amount,
        'cogs_amount': order.cogs_amount,
        'income_record_id': order.income_record_id,
        'cogs_record_id': order.cogs_record_id,
        'notes': order.notes,
        'created_at': order.created_at,
        'updated_at': order.updated_at,
        'line_count': len(order.lines or []),
        'void_event': (
            None if not latest_void else {
                'id': latest_void.id,
                'void_date': latest_void.void_date,
                'reason': latest_void.reason,
                'reverse_inventory': latest_void.reverse_inventory,
                'auto_post_accounting': latest_void.auto_post_accounting,
                'income_reversal_record_id': latest_void.income_reversal_record_id,
                'cogs_reversal_record_id': latest_void.cogs_reversal_record_id,
                'created_by': latest_void.created_by,
                'created_at': latest_void.created_at,
            }
        ),
    }
    if include_lines:
        data['lines'] = [
            {
                'id': line.id,
                'menu_item_id': line.menu_item_id,
                'sku_id': line.sku_id,
                'item_name': line.item_name,
                'quantity': line.quantity,
                'unit_price': line.unit_price,
                'discount_amount': line.discount_amount,
                'line_total': line.line_total,
            }
            for line in (order.lines or [])
        ]
    return data


@router.get('/items')
def items(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(MenuItem).order_by(MenuItem.name.asc()).all()


@router.post('/items')
def create_item(
    payload: MenuItemCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('menu.manage')),
):
    obj = MenuItem(**payload.model_dump())
    try:
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail='Menu item name must be unique.')


@router.put('/items/{item_id}')
def update_item(
    item_id: int,
    payload: MenuItemUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('menu.manage')),
):
    obj = db.get(MenuItem, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail='Menu item not found')
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    try:
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail='Menu item name must be unique.')


@router.delete('/items/{item_id}')
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('menu.manage')),
):
    obj = db.get(MenuItem, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail='Menu item not found')
    db.delete(obj)
    db.commit()
    return {'ok': True}


@router.get('/items/{item_id}/recipe')
def get_recipe(item_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return (
        db.query(RecipeLine)
        .filter(RecipeLine.menu_item_id == item_id)
        .order_by(RecipeLine.id.asc())
        .all()
    )


@router.post('/items/{item_id}/recipe')
def add_recipe_line(
    item_id: int,
    payload: RecipeLineCreate,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('recipes.manage', 'menu.manage')),
):
    menu_item = db.get(MenuItem, item_id)
    if not menu_item:
        raise HTTPException(status_code=404, detail='Menu item not found')

    inv = db.get(InventoryItem, int(payload.inventory_item_id))
    if not inv:
        raise HTTPException(status_code=404, detail='Inventory item not found')

    if float(payload.quantity or 0) <= 0:
        raise HTTPException(status_code=400, detail='Quantity must be greater than zero.')

    obj = RecipeLine(menu_item_id=item_id, **payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete('/recipe/{line_id}')
def delete_recipe_line(
    line_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('recipes.manage', 'menu.manage')),
):
    obj = db.get(RecipeLine, line_id)
    if not obj:
        raise HTTPException(status_code=404, detail='Recipe line not found')
    db.delete(obj)
    db.commit()
    return {'ok': True}


@router.get('/components')
def list_components(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = (
        db.query(PrepComponent)
        .options(selectinload(PrepComponent.items))
        .order_by(PrepComponent.name.asc())
        .all()
    )
    return [_serialize_component(row, include_items=True) for row in rows]


@router.get('/components/{component_id}')
def get_component(component_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = (
        db.query(PrepComponent)
        .options(selectinload(PrepComponent.items))
        .filter(PrepComponent.id == component_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail='Component not found')
    return _serialize_component(row, include_items=True)


@router.post('/components')
def create_component(
    payload: PrepComponentCreate,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('recipes.manage', 'menu.manage')),
):
    if float(payload.yield_quantity or 0) <= 0:
        raise HTTPException(status_code=400, detail='yield_quantity must be greater than zero.')
    try:
        _validate_component_items(payload.items, db)
        obj = PrepComponent(
            name=payload.name,
            category_name=payload.category_name,
            yield_quantity=payload.yield_quantity,
            yield_unit=payload.yield_unit,
            is_active=payload.is_active,
            notes=payload.notes,
        )
        db.add(obj)
        db.flush()

        for row in payload.items:
            db.add(
                PrepComponentItem(
                    component_id=obj.id,
                    inventory_item_id=row.inventory_item_id,
                    quantity=row.quantity,
                    unit=row.unit,
                    wastage_percent=row.wastage_percent,
                    sort_order=row.sort_order,
                    notes=row.notes,
                )
            )

        db.commit()
        db.refresh(obj)
        obj = (
            db.query(PrepComponent)
            .options(selectinload(PrepComponent.items))
            .filter(PrepComponent.id == obj.id)
            .first()
        )
        return _serialize_component(obj, include_items=True)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail='Component name must be unique.')


@router.put('/components/{component_id}')
def update_component(
    component_id: int,
    payload: PrepComponentUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('recipes.manage', 'menu.manage')),
):
    obj = db.get(PrepComponent, component_id)
    if not obj:
        raise HTTPException(status_code=404, detail='Component not found')

    data = payload.model_dump(exclude_unset=True)
    items = data.pop('items', None)

    if 'yield_quantity' in data and float(data['yield_quantity'] or 0) <= 0:
        raise HTTPException(status_code=400, detail='yield_quantity must be greater than zero.')

    try:
        for k, v in data.items():
            setattr(obj, k, v)

        if items is not None:
            _validate_component_items(items, db)
            db.query(PrepComponentItem).filter(PrepComponentItem.component_id == obj.id).delete(synchronize_session=False)
            db.flush()
            for row in items:
                db.add(
                    PrepComponentItem(
                        component_id=obj.id,
                        inventory_item_id=row.inventory_item_id,
                        quantity=row.quantity,
                        unit=row.unit,
                        wastage_percent=row.wastage_percent,
                        sort_order=row.sort_order,
                        notes=row.notes,
                    )
                )

        db.add(obj)
        db.commit()
        db.refresh(obj)
        obj = (
            db.query(PrepComponent)
            .options(selectinload(PrepComponent.items))
            .filter(PrepComponent.id == obj.id)
            .first()
        )
        return _serialize_component(obj, include_items=True)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail='Component name must be unique.')


@router.delete('/components/{component_id}')
def delete_component(
    component_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('recipes.manage', 'menu.manage')),
):
    obj = db.get(PrepComponent, component_id)
    if not obj:
        raise HTTPException(status_code=404, detail='Component not found')
    db.delete(obj)
    db.commit()
    return {'ok': True}


@router.get('/components/{component_id}/costing')
def component_costing(component_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    component = db.get(PrepComponent, component_id)
    if not component:
        raise HTTPException(status_code=404, detail='Component not found')
    return compute_component_costing(db, component)


@router.get('/skus')
def list_skus(
    menu_item_id: int | None = Query(None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    q = db.query(MenuSKU).options(selectinload(MenuSKU.recipe_items))
    if menu_item_id:
        q = q.filter(MenuSKU.menu_item_id == menu_item_id)
    rows = q.order_by(MenuSKU.menu_item_id.asc(), MenuSKU.variant_name.asc(), MenuSKU.id.asc()).all()
    return [_serialize_sku(row, include_recipe_items=True) for row in rows]


@router.get('/items/{item_id}/skus')
def list_item_skus(item_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = (
        db.query(MenuSKU)
        .options(selectinload(MenuSKU.recipe_items))
        .filter(MenuSKU.menu_item_id == item_id)
        .order_by(MenuSKU.variant_name.asc(), MenuSKU.id.asc())
        .all()
    )
    return [_serialize_sku(row, include_recipe_items=True) for row in rows]


@router.get('/skus/{sku_id}')
def get_sku(sku_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = (
        db.query(MenuSKU)
        .options(selectinload(MenuSKU.recipe_items))
        .filter(MenuSKU.id == sku_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail='SKU not found')
    return _serialize_sku(row, include_recipe_items=True)


@router.post('/skus')
def create_sku(
    payload: MenuSKUCreate,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('recipes.manage', 'menu.manage')),
):
    menu_item = db.get(MenuItem, int(payload.menu_item_id))
    if not menu_item:
        raise HTTPException(status_code=404, detail='Menu item not found')

    try:
        _validate_sku_recipe_items(payload.recipe_items, db)
        obj = MenuSKU(
            menu_item_id=payload.menu_item_id,
            sku_code=payload.sku_code,
            variant_name=payload.variant_name,
            size_label=payload.size_label,
            price=payload.price,
            packaging_cost=payload.packaging_cost,
            labor_cost=payload.labor_cost,
            overhead_cost=payload.overhead_cost,
            is_active=payload.is_active,
            notes=payload.notes,
        )
        db.add(obj)
        db.flush()

        for row in payload.recipe_items:
            line_type = _to_line_type(row.line_type)
            db.add(
                MenuSKURecipeItem(
                    sku_id=obj.id,
                    line_type=line_type,
                    inventory_item_id=row.inventory_item_id if line_type != 'component' else None,
                    component_id=row.component_id if line_type == 'component' else None,
                    quantity=row.quantity,
                    unit=row.unit,
                    wastage_percent=row.wastage_percent,
                    sort_order=row.sort_order,
                    notes=row.notes,
                )
            )

        db.commit()
        db.refresh(obj)
        obj = (
            db.query(MenuSKU)
            .options(selectinload(MenuSKU.recipe_items))
            .filter(MenuSKU.id == obj.id)
            .first()
        )
        return _serialize_sku(obj, include_recipe_items=True)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail='SKU code must be unique.')


@router.put('/skus/{sku_id}')
def update_sku(
    sku_id: int,
    payload: MenuSKUUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('recipes.manage', 'menu.manage')),
):
    obj = db.get(MenuSKU, sku_id)
    if not obj:
        raise HTTPException(status_code=404, detail='SKU not found')

    data = payload.model_dump(exclude_unset=True)
    recipe_items = data.pop('recipe_items', None)

    if 'menu_item_id' in data:
        menu_item = db.get(MenuItem, int(data['menu_item_id']))
        if not menu_item:
            raise HTTPException(status_code=404, detail='Menu item not found')

    try:
        for k, v in data.items():
            setattr(obj, k, v)

        if recipe_items is not None:
            _validate_sku_recipe_items(recipe_items, db)
            db.query(MenuSKURecipeItem).filter(MenuSKURecipeItem.sku_id == obj.id).delete(synchronize_session=False)
            db.flush()
            for row in recipe_items:
                line_type = _to_line_type(row.line_type)
                db.add(
                    MenuSKURecipeItem(
                        sku_id=obj.id,
                        line_type=line_type,
                        inventory_item_id=row.inventory_item_id if line_type != 'component' else None,
                        component_id=row.component_id if line_type == 'component' else None,
                        quantity=row.quantity,
                        unit=row.unit,
                        wastage_percent=row.wastage_percent,
                        sort_order=row.sort_order,
                        notes=row.notes,
                    )
                )

        db.add(obj)
        db.commit()
        db.refresh(obj)
        obj = (
            db.query(MenuSKU)
            .options(selectinload(MenuSKU.recipe_items))
            .filter(MenuSKU.id == obj.id)
            .first()
        )
        return _serialize_sku(obj, include_recipe_items=True)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail='SKU code must be unique.')


@router.delete('/skus/{sku_id}')
def delete_sku(
    sku_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('recipes.manage', 'menu.manage')),
):
    obj = db.get(MenuSKU, sku_id)
    if not obj:
        raise HTTPException(status_code=404, detail='SKU not found')
    db.delete(obj)
    db.commit()
    return {'ok': True}


@router.get('/skus/{sku_id}/costing')
def sku_costing(sku_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    sku = db.get(MenuSKU, sku_id)
    if not sku:
        raise HTTPException(status_code=404, detail='SKU not found')
    return compute_sku_costing(db, sku)


@router.get('/promotions')
def list_promotions(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(MenuPromotion).order_by(MenuPromotion.id.desc()).all()


@router.post('/promotions')
def create_promotion(
    payload: MenuPromotionCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('menu.manage')),
):
    try:
        applies_to, sku_id, menu_item_id = _normalize_promo_fields(
            db,
            payload.applies_to,
            payload.sku_id,
            payload.menu_item_id,
        )
        _validate_promo_dates(payload.start_date, payload.end_date)

        obj = MenuPromotion(
            name=payload.name,
            applies_to=applies_to,
            sku_id=sku_id,
            menu_item_id=menu_item_id,
            promo_type=payload.promo_type,
            promo_value=payload.promo_value,
            min_qty=payload.min_qty,
            start_date=payload.start_date,
            end_date=payload.end_date,
            is_active=payload.is_active,
            notes=payload.notes,
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put('/promotions/{promotion_id}')
def update_promotion(
    promotion_id: int,
    payload: MenuPromotionUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('menu.manage')),
):
    obj = db.get(MenuPromotion, promotion_id)
    if not obj:
        raise HTTPException(status_code=404, detail='Promotion not found')

    data = payload.model_dump(exclude_unset=True)
    merged = {
        'applies_to': data.get('applies_to', obj.applies_to),
        'sku_id': data.get('sku_id', obj.sku_id),
        'menu_item_id': data.get('menu_item_id', obj.menu_item_id),
        'start_date': data.get('start_date', obj.start_date),
        'end_date': data.get('end_date', obj.end_date),
    }

    try:
        applies_to, sku_id, menu_item_id = _normalize_promo_fields(
            db,
            merged['applies_to'],
            merged['sku_id'],
            merged['menu_item_id'],
        )
        _validate_promo_dates(merged['start_date'], merged['end_date'])

        for k, v in data.items():
            setattr(obj, k, v)
        obj.applies_to = applies_to
        obj.sku_id = sku_id
        obj.menu_item_id = menu_item_id

        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete('/promotions/{promotion_id}')
def delete_promotion(
    promotion_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('menu.manage')),
):
    obj = db.get(MenuPromotion, promotion_id)
    if not obj:
        raise HTTPException(status_code=404, detail='Promotion not found')
    db.delete(obj)
    db.commit()
    return {'ok': True}


@router.get('/staff-meals')
def staff_meals(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return list_staff_meal_logs(db)


@router.post('/staff-meals')
def add_staff_meal(
    payload: StaffMealCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('staff_meals.manage')),
):
    try:
        return create_staff_meal_log(db, payload, username=getattr(user, 'username', None))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get('/sales')
def list_sales(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    rows = (
        db.query(SaleOrder)
        .options(
            selectinload(SaleOrder.lines),
            selectinload(SaleOrder.void_events)
            .selectinload(SaleVoidEvent.income_reversal_record),
            selectinload(SaleOrder.void_events)
            .selectinload(SaleVoidEvent.cogs_reversal_record),
        )
        .order_by(SaleOrder.id.desc())
        .limit(limit)
        .all()
    )
    return [_serialize_sale(order, include_lines=False) for order in rows]


@router.get('/sales/{sale_id}')
def get_sale(sale_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    order = (
        db.query(SaleOrder)
        .options(
            selectinload(SaleOrder.lines),
            selectinload(SaleOrder.void_events)
            .selectinload(SaleVoidEvent.income_reversal_record),
            selectinload(SaleOrder.void_events)
            .selectinload(SaleVoidEvent.cogs_reversal_record),
        )
        .filter(SaleOrder.id == sale_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail='Sale order not found')
    return _serialize_sale(order, include_lines=True)


@router.post('/sales')
def post_sale(
    payload: SaleOrderCreate,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('menu.manage', 'cashflow.money_in')),
):
    try:
        order = create_sale_order(db, payload, username=getattr(user, 'username', None))
        order = (
            db.query(SaleOrder)
            .options(
                selectinload(SaleOrder.lines),
                selectinload(SaleOrder.void_events)
                .selectinload(SaleVoidEvent.income_reversal_record),
                selectinload(SaleOrder.void_events)
                .selectinload(SaleVoidEvent.cogs_reversal_record),
            )
            .filter(SaleOrder.id == order.id)
            .first()
        )
        return _serialize_sale(order, include_lines=True)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/sales/{sale_id}/void')
def void_sale(
    sale_id: int,
    payload: SaleVoidPayload,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('menu.manage', 'cashflow.money_out', 'approvals.act')),
):
    order = (
        db.query(SaleOrder)
        .options(
            selectinload(SaleOrder.lines),
            selectinload(SaleOrder.void_events),
        )
        .filter(SaleOrder.id == sale_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail='Sale order not found')

    try:
        order = void_sale_order(db, order, payload, username=getattr(user, 'username', None))
        order = (
            db.query(SaleOrder)
            .options(
                selectinload(SaleOrder.lines),
                selectinload(SaleOrder.void_events)
                .selectinload(SaleVoidEvent.income_reversal_record),
                selectinload(SaleOrder.void_events)
                .selectinload(SaleVoidEvent.cogs_reversal_record),
            )
            .filter(SaleOrder.id == order.id)
            .first()
        )
        return _serialize_sale(order, include_lines=True)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
