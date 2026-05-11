from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session, selectinload

from app.models.entities import BookingChannel, RatePlan, Room, RoomPackageRule, RoomType
from app.schemas.rooms import (
    BookingChannelCreate,
    BookingChannelUpdate,
    RatePlanCreate,
    RatePlanUpdate,
    RoomCreate,
    RoomPackageRuleCreate,
    RoomPackageRuleUpdate,
    RoomTypeCreate,
    RoomTypeUpdate,
    RoomUpdate,
)
from app.services.code_service import ensure_editable_after_create, generate_code


def _today() -> str:
    return datetime.utcnow().strftime('%Y-%m-%d')


def _norm(text: str | None) -> str | None:
    if text is None:
        return None
    value = text.strip()
    return value or None


def _serialize_room_type(row: RoomType) -> dict:
    return {
        'id': row.id,
        'code': row.code,
        'name': row.name,
        'description': row.description,
        'base_capacity': row.base_capacity,
        'max_capacity': row.max_capacity,
        'is_active': bool(row.is_active),
        'notes': row.notes,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_room(row: Room) -> dict:
    room_type = row.room_type
    return {
        'id': row.id,
        'room_no': row.room_no,
        'name': row.name,
        'room_type_id': row.room_type_id,
        'room_type_code': room_type.code if room_type else None,
        'room_type_name': room_type.name if room_type else None,
        'floor_zone': row.floor_zone,
        'view_name': row.view_name,
        'status': row.status,
        'is_active': bool(row.is_active),
        'notes': row.notes,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_rate_plan(row: RatePlan) -> dict:
    room_type = row.room_type
    return {
        'id': row.id,
        'code': row.code,
        'name': row.name,
        'room_type_id': row.room_type_id,
        'room_type_name': room_type.name if room_type else None,
        'base_rate': float(row.base_rate or 0),
        'breakfast_included': int(row.breakfast_included or 0),
        'pax_included': int(row.pax_included or 0),
        'is_active': bool(row.is_active),
        'notes': row.notes,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_channel(row: BookingChannel) -> dict:
    return {
        'id': row.id,
        'code': row.code,
        'name': row.name,
        'channel_class': row.channel_class,
        'settlement_mode': row.settlement_mode,
        'default_commission_rate': float(row.default_commission_rate or 0),
        'is_prepaid': bool(row.is_prepaid),
        'is_active': bool(row.is_active),
        'notes': row.notes,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_package_rule(row: RoomPackageRule) -> dict:
    return {
        'id': row.id,
        'name': row.name,
        'room_type_id': row.room_type_id,
        'room_type_name': row.room_type.name if row.room_type else None,
        'rate_plan_id': row.rate_plan_id,
        'rate_plan_name': row.rate_plan.name if row.rate_plan else None,
        'included_breakfast': int(row.included_breakfast or 0),
        'included_pax': int(row.included_pax or 0),
        'extra_pax_rate': float(row.extra_pax_rate or 0),
        'is_active': bool(row.is_active),
        'notes': row.notes,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def list_room_types(db: Session, *, active_only: bool = False):
    query = db.query(RoomType)
    if active_only:
        query = query.filter(RoomType.is_active == True)
    rows = query.order_by(RoomType.name.asc()).all()
    return [_serialize_room_type(row) for row in rows]


def create_room_type(db: Session, payload: RoomTypeCreate):
    code = generate_code(db, 'room_type', requested_code=payload.code)
    name = _norm(payload.name)
    if not name:
        raise ValueError('name is required.')
    if db.query(RoomType).filter(RoomType.name == name).first():
        raise ValueError(f'Room type {name} already exists.')
    row = RoomType(
        code=code,
        name=name,
        description=_norm(payload.description),
        base_capacity=max(1, int(payload.base_capacity or 1)),
        max_capacity=max(1, int(payload.max_capacity or 1)),
        is_active=bool(payload.is_active),
        notes=payload.notes,
    )
    if row.max_capacity < row.base_capacity:
        row.max_capacity = row.base_capacity
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_room_type(row)


def update_room_type(db: Session, room_type_id: int, payload: RoomTypeUpdate):
    row = db.get(RoomType, int(room_type_id))
    if not row:
        raise ValueError('Room type not found.')
    data = payload.model_dump(exclude_unset=True)
    if 'code' in data:
        code = ensure_editable_after_create(
            db,
            'room_type',
            row.code,
            data.get('code'),
            exclude_id=row.id,
        )
        row.code = code
    if 'name' in data:
        name = _norm(data.get('name'))
        if not name:
            raise ValueError('name cannot be blank.')
        dup = db.query(RoomType).filter(RoomType.name == name, RoomType.id != row.id).first()
        if dup:
            raise ValueError(f'Room type {name} already exists.')
        row.name = name
    if 'description' in data:
        row.description = _norm(data.get('description'))
    if 'base_capacity' in data:
        row.base_capacity = max(1, int(data.get('base_capacity') or 1))
    if 'max_capacity' in data:
        row.max_capacity = max(1, int(data.get('max_capacity') or 1))
    if row.max_capacity < row.base_capacity:
        row.max_capacity = row.base_capacity
    for key in ('is_active', 'notes'):
        if key in data:
            setattr(row, key, data.get(key))
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_room_type(row)


def delete_room_type(db: Session, room_type_id: int):
    row = db.get(RoomType, int(room_type_id))
    if not row:
        raise ValueError('Room type not found.')
    db.delete(row)
    db.commit()
    return {'ok': True}


def list_rooms(db: Session, *, active_only: bool = False):
    query = db.query(Room).options(selectinload(Room.room_type))
    if active_only:
        query = query.filter(Room.is_active == True)
    rows = query.order_by(Room.room_no.asc(), Room.name.asc()).all()
    return [_serialize_room(row) for row in rows]


def create_room(db: Session, payload: RoomCreate):
    room_no = generate_code(db, 'room', requested_code=payload.room_no)
    name = _norm(payload.name)
    if not name:
        raise ValueError('name is required.')
    room_type_id = payload.room_type_id
    if room_type_id and not db.get(RoomType, int(room_type_id)):
        raise ValueError('room_type_id not found.')
    row = Room(
        room_no=room_no,
        name=name,
        room_type_id=room_type_id,
        floor_zone=_norm(payload.floor_zone),
        view_name=_norm(payload.view_name),
        status=_norm(payload.status) or 'available',
        is_active=bool(payload.is_active),
        notes=payload.notes,
    )
    db.add(row)
    db.commit()
    row = db.query(Room).options(selectinload(Room.room_type)).filter(Room.id == row.id).first()
    return _serialize_room(row)


def update_room(db: Session, room_id: int, payload: RoomUpdate):
    row = db.get(Room, int(room_id))
    if not row:
        raise ValueError('Room not found.')
    data = payload.model_dump(exclude_unset=True)
    if 'room_no' in data:
        room_no = ensure_editable_after_create(
            db,
            'room',
            row.room_no,
            data.get('room_no'),
            exclude_id=row.id,
        )
        row.room_no = room_no
    if 'name' in data:
        name = _norm(data.get('name'))
        if not name:
            raise ValueError('name cannot be blank.')
        row.name = name
    if 'room_type_id' in data:
        room_type_id = data.get('room_type_id')
        if room_type_id and not db.get(RoomType, int(room_type_id)):
            raise ValueError('room_type_id not found.')
        row.room_type_id = room_type_id
    for key in ('floor_zone', 'view_name', 'status', 'is_active', 'notes'):
        if key in data:
            value = data.get(key)
            if key in {'floor_zone', 'view_name', 'status'}:
                value = _norm(value)
            setattr(row, key, value)
    db.add(row)
    db.commit()
    row = db.query(Room).options(selectinload(Room.room_type)).filter(Room.id == row.id).first()
    return _serialize_room(row)


def delete_room(db: Session, room_id: int):
    row = db.get(Room, int(room_id))
    if not row:
        raise ValueError('Room not found.')
    db.delete(row)
    db.commit()
    return {'ok': True}


def list_rate_plans(db: Session, *, active_only: bool = False):
    query = db.query(RatePlan).options(selectinload(RatePlan.room_type))
    if active_only:
        query = query.filter(RatePlan.is_active == True)
    rows = query.order_by(RatePlan.name.asc()).all()
    return [_serialize_rate_plan(row) for row in rows]


def create_rate_plan(db: Session, payload: RatePlanCreate):
    code = generate_code(db, 'rate_plan', requested_code=payload.code)
    name = _norm(payload.name)
    if not name:
        raise ValueError('name is required.')
    if payload.room_type_id and not db.get(RoomType, int(payload.room_type_id)):
        raise ValueError('room_type_id not found.')
    row = RatePlan(
        code=code,
        name=name,
        room_type_id=payload.room_type_id,
        base_rate=float(payload.base_rate or 0),
        breakfast_included=max(0, int(payload.breakfast_included or 0)),
        pax_included=max(1, int(payload.pax_included or 1)),
        is_active=bool(payload.is_active),
        notes=payload.notes,
    )
    db.add(row)
    db.commit()
    row = db.query(RatePlan).options(selectinload(RatePlan.room_type)).filter(RatePlan.id == row.id).first()
    return _serialize_rate_plan(row)


def update_rate_plan(db: Session, rate_plan_id: int, payload: RatePlanUpdate):
    row = db.get(RatePlan, int(rate_plan_id))
    if not row:
        raise ValueError('Rate plan not found.')
    data = payload.model_dump(exclude_unset=True)
    if 'code' in data:
        code = ensure_editable_after_create(
            db,
            'rate_plan',
            row.code,
            data.get('code'),
            exclude_id=row.id,
        )
        row.code = code
    if 'name' in data:
        name = _norm(data.get('name'))
        if not name:
            raise ValueError('name cannot be blank.')
        row.name = name
    if 'room_type_id' in data:
        room_type_id = data.get('room_type_id')
        if room_type_id and not db.get(RoomType, int(room_type_id)):
            raise ValueError('room_type_id not found.')
        row.room_type_id = room_type_id
    for key in ('base_rate', 'breakfast_included', 'pax_included', 'is_active', 'notes'):
        if key in data:
            setattr(row, key, data.get(key))
    db.add(row)
    db.commit()
    row = db.query(RatePlan).options(selectinload(RatePlan.room_type)).filter(RatePlan.id == row.id).first()
    return _serialize_rate_plan(row)


def delete_rate_plan(db: Session, rate_plan_id: int):
    row = db.get(RatePlan, int(rate_plan_id))
    if not row:
        raise ValueError('Rate plan not found.')
    db.delete(row)
    db.commit()
    return {'ok': True}


def list_booking_channels(db: Session, *, active_only: bool = False):
    query = db.query(BookingChannel)
    if active_only:
        query = query.filter(BookingChannel.is_active == True)
    rows = query.order_by(BookingChannel.name.asc()).all()
    return [_serialize_channel(row) for row in rows]


def create_booking_channel(db: Session, payload: BookingChannelCreate):
    code = generate_code(db, 'booking_channel', requested_code=payload.code)
    name = _norm(payload.name)
    if not name:
        raise ValueError('name is required.')
    if db.query(BookingChannel).filter(BookingChannel.name == name).first():
        raise ValueError(f'Booking channel name {name} already exists.')
    row = BookingChannel(
        code=code,
        name=name,
        channel_class=_norm(payload.channel_class),
        settlement_mode=_norm(payload.settlement_mode),
        default_commission_rate=float(payload.default_commission_rate or 0),
        is_prepaid=bool(payload.is_prepaid),
        is_active=bool(payload.is_active),
        notes=payload.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_channel(row)


def update_booking_channel(db: Session, channel_id: int, payload: BookingChannelUpdate):
    row = db.get(BookingChannel, int(channel_id))
    if not row:
        raise ValueError('Booking channel not found.')
    data = payload.model_dump(exclude_unset=True)
    if 'code' in data:
        code = ensure_editable_after_create(
            db,
            'booking_channel',
            row.code,
            data.get('code'),
            exclude_id=row.id,
        )
        row.code = code
    if 'name' in data:
        name = _norm(data.get('name'))
        if not name:
            raise ValueError('name cannot be blank.')
        dup = db.query(BookingChannel).filter(BookingChannel.name == name, BookingChannel.id != row.id).first()
        if dup:
            raise ValueError(f'Booking channel name {name} already exists.')
        row.name = name
    for key in ('channel_class', 'settlement_mode', 'default_commission_rate', 'is_prepaid', 'is_active', 'notes'):
        if key in data:
            value = data.get(key)
            if key in {'channel_class', 'settlement_mode'}:
                value = _norm(value)
            setattr(row, key, value)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_channel(row)


def delete_booking_channel(db: Session, channel_id: int):
    row = db.get(BookingChannel, int(channel_id))
    if not row:
        raise ValueError('Booking channel not found.')
    db.delete(row)
    db.commit()
    return {'ok': True}


def list_package_rules(db: Session, *, active_only: bool = False):
    query = db.query(RoomPackageRule).options(selectinload(RoomPackageRule.room_type), selectinload(RoomPackageRule.rate_plan))
    if active_only:
        query = query.filter(RoomPackageRule.is_active == True)
    rows = query.order_by(RoomPackageRule.name.asc()).all()
    return [_serialize_package_rule(row) for row in rows]


def create_package_rule(db: Session, payload: RoomPackageRuleCreate):
    room_type_id = payload.room_type_id
    rate_plan_id = payload.rate_plan_id
    if room_type_id and not db.get(RoomType, int(room_type_id)):
        raise ValueError('room_type_id not found.')
    if rate_plan_id and not db.get(RatePlan, int(rate_plan_id)):
        raise ValueError('rate_plan_id not found.')
    name = _norm(payload.name)
    if not name:
        raise ValueError('name is required.')
    row = RoomPackageRule(
        name=name,
        room_type_id=room_type_id,
        rate_plan_id=rate_plan_id,
        included_breakfast=max(0, int(payload.included_breakfast or 0)),
        included_pax=max(1, int(payload.included_pax or 1)),
        extra_pax_rate=float(payload.extra_pax_rate or 0),
        is_active=bool(payload.is_active),
        notes=payload.notes,
    )
    db.add(row)
    db.commit()
    row = db.query(RoomPackageRule).options(selectinload(RoomPackageRule.room_type), selectinload(RoomPackageRule.rate_plan)).filter(RoomPackageRule.id == row.id).first()
    return _serialize_package_rule(row)


def update_package_rule(db: Session, package_rule_id: int, payload: RoomPackageRuleUpdate):
    row = db.get(RoomPackageRule, int(package_rule_id))
    if not row:
        raise ValueError('Package rule not found.')
    data = payload.model_dump(exclude_unset=True)
    if 'name' in data:
        name = _norm(data.get('name'))
        if not name:
            raise ValueError('name cannot be blank.')
        row.name = name
    if 'room_type_id' in data:
        room_type_id = data.get('room_type_id')
        if room_type_id and not db.get(RoomType, int(room_type_id)):
            raise ValueError('room_type_id not found.')
        row.room_type_id = room_type_id
    if 'rate_plan_id' in data:
        rate_plan_id = data.get('rate_plan_id')
        if rate_plan_id and not db.get(RatePlan, int(rate_plan_id)):
            raise ValueError('rate_plan_id not found.')
        row.rate_plan_id = rate_plan_id
    for key in ('included_breakfast', 'included_pax', 'extra_pax_rate', 'is_active', 'notes'):
        if key in data:
            setattr(row, key, data.get(key))
    db.add(row)
    db.commit()
    row = db.query(RoomPackageRule).options(selectinload(RoomPackageRule.room_type), selectinload(RoomPackageRule.rate_plan)).filter(RoomPackageRule.id == row.id).first()
    return _serialize_package_rule(row)


def delete_package_rule(db: Session, package_rule_id: int):
    row = db.get(RoomPackageRule, int(package_rule_id))
    if not row:
        raise ValueError('Package rule not found.')
    db.delete(row)
    db.commit()
    return {'ok': True}
