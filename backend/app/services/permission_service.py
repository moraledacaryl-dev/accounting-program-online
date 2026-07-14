from __future__ import annotations

from sqlalchemy.orm import Session, selectinload

from app.models.entities import Permission, Role, RolePermission, User, UserPermissionOverride, UserRole
from app.schemas.permissions import RoleCreate, RoleUpdate


DEFAULT_PERMISSION_DEFS = [
    ('dashboard.view', 'View Dashboard', 'Dashboard'),
    ('bookings.view', 'View Bookings', 'Rooms & Guests'),
    ('bookings.create', 'Create Booking', 'Rooms & Guests'),
    ('bookings.edit', 'Edit Booking', 'Rooms & Guests'),
    ('bookings.cancel', 'Cancel Booking', 'Rooms & Guests'),
    ('folios.view', 'View Folios', 'Rooms & Guests'),
    ('folios.manage', 'Manage Folios', 'Rooms & Guests'),
    ('guests.view', 'View Guests', 'Rooms & Guests'),
    ('guests.create', 'Create Guests', 'Rooms & Guests'),
    ('guests.edit', 'Edit Guests', 'Rooms & Guests'),
    ('room_setup.view', 'View Room Setup', 'Rooms & Guests'),
    ('room_setup.manage', 'Manage Room Setup', 'Rooms & Guests'),
    ('restaurant.view', 'View Restaurant', 'Restaurant & F&B'),
    ('menu.view', 'View Menu', 'Restaurant & F&B'),
    ('menu.manage', 'Manage Menu', 'Restaurant & F&B'),
    ('recipes.manage', 'Manage Recipes', 'Restaurant & F&B'),
    ('staff_meals.view', 'View Staff Meals', 'Restaurant & F&B'),
    ('staff_meals.manage', 'Manage Staff Meals', 'Restaurant & F&B'),
    ('inventory.view', 'View Inventory', 'Inventory & Purchasing'),
    ('inventory.manage', 'Manage Inventory', 'Inventory & Purchasing'),
    ('stock_movements.create', 'Create Stock Movements', 'Inventory & Purchasing'),
    ('inventory_reconciliation.manage', 'Manage Inventory Reconciliation', 'Inventory & Purchasing'),
    ('suppliers.view', 'View Suppliers', 'Inventory & Purchasing'),
    ('suppliers.manage', 'Manage Suppliers', 'Inventory & Purchasing'),
    ('purchase_requests.view', 'View Purchase Requests', 'Inventory & Purchasing'),
    ('purchase_requests.create', 'Create Purchase Requests', 'Inventory & Purchasing'),
    ('purchase_requests.approve', 'Approve Purchase Requests', 'Inventory & Purchasing'),
    ('purchase_orders.view', 'View Purchase Orders', 'Inventory & Purchasing'),
    ('purchase_orders.create', 'Create Purchase Orders', 'Inventory & Purchasing'),
    ('purchase_orders.approve', 'Approve Purchase Orders', 'Inventory & Purchasing'),
    ('receiving.view', 'View Receiving', 'Inventory & Purchasing'),
    ('receiving.post', 'Post Receiving', 'Inventory & Purchasing'),
    ('employees.view', 'View Employees', 'People & Payroll'),
    ('employees.manage', 'Manage Employees', 'People & Payroll'),
    ('attendance.view', 'View Attendance', 'People & Payroll'),
    ('attendance.manage', 'Manage Attendance', 'People & Payroll'),
    ('payroll_periods.view', 'View Payroll Periods', 'People & Payroll'),
    ('payroll_periods.manage', 'Manage Payroll Periods', 'People & Payroll'),
    ('approvals.view', 'View Approvals', 'People & Payroll'),
    ('approvals.act', 'Act on Approvals', 'People & Payroll'),
    ('review_inbox.view', 'View Review Inbox', 'Main'),
    ('review_inbox.act', 'Accept or Reject Review Items', 'Main'),
    ('hotel.view', 'View Hotel Operations', 'Hotel Operations'),
    ('events.view', 'View Events', 'Hotel Operations'),
    ('cash_treasury.view', 'View Cash & Treasury', 'Finance & Accounting'),
    ('daily_close.count', 'Count Assigned Cash', 'Finance & Accounting'),
    ('daily_close.approve', 'Approve Daily Close', 'Finance & Accounting'),
    ('money.reverse', 'Reverse Posted Money Transactions', 'Finance & Accounting'),
    ('account_access.manage', 'Manage Financial Account Access', 'Settings'),
    ('cashflow.view', 'View Cashflow', 'Finance & Accounting'),
    ('cashflow.money_in', 'Create Money In', 'Finance & Accounting'),
    ('cashflow.money_out', 'Create Money Out', 'Finance & Accounting'),
    ('cashflow.transfers', 'Manage Transfers', 'Finance & Accounting'),
    ('cashflow.reconcile', 'Manage Reconciliation', 'Finance & Accounting'),
    ('journals.view', 'View Journals', 'Finance & Accounting'),
    ('journals.post', 'Post Journals', 'Finance & Accounting'),
    ('reports.view', 'View Reports', 'Finance & Accounting'),
    ('assets.view', 'View Assets', 'Finance & Accounting'),
    ('assets.manage', 'Manage Assets', 'Finance & Accounting'),
    ('bir.view', 'View BIR', 'Finance & Accounting'),
    ('bir.manage', 'Manage BIR', 'Finance & Accounting'),
    ('users.manage', 'Manage Users', 'Settings'),
    ('roles.manage', 'Manage Roles', 'Settings'),
    ('taxonomy.manage', 'Manage Taxonomy', 'Settings'),
    ('master_data.manage', 'Manage Master Data', 'Settings'),
    ('chart_of_accounts.manage', 'Manage Chart of Accounts', 'Settings'),
    ('account_mapping.manage', 'Manage Account Mapping', 'Settings'),
    ('system_settings.manage', 'Manage System Settings', 'Settings'),
    ('integrations.view', 'View Integrations', 'Settings'),
    ('integrations.manage', 'Manage Integrations', 'Settings'),
    ('integrations.sync', 'Run Integration Sync', 'Settings'),
    ('integrations.logs.view', 'View Integration Logs', 'Settings'),
]


DEFAULT_ROLES = [
    ('owner', 'Owner', 'Full access to all modules.'),
    ('manager', 'Manager', 'Operational and approval access.'),
    ('front_desk', 'Front Desk', 'Bookings, guests, and folios.'),
    ('restaurant_admin', 'Restaurant Admin', 'Restaurant and inventory usage.'),
    ('purchasing_admin', 'Purchasing Admin', 'Suppliers and procurement workflows.'),
    ('payroll_admin', 'Payroll Admin', 'People and payroll period workflows.'),
    ('accounting_admin', 'Accounting Admin', 'Cashflow, journals, reports, and BIR.'),
    ('cashier', 'Cashier', 'Assigned drawer and POS-linked financial work.'),
    ('auditor', 'Auditor', 'Read-only accounting and hotel review.'),
    (
        'pos_integration',
        'POS Integration',
        'Limited service access for POS to Accounting posting and lookup.',
    ),
]


ROLE_PERMISSION_PRESETS = {
    'owner': {key for key, _label, _group in DEFAULT_PERMISSION_DEFS},
    'manager': {
        key for key, _label, _group in DEFAULT_PERMISSION_DEFS
        if key not in {'users.manage', 'roles.manage', 'system_settings.manage'}
    },
    'front_desk': {
        'dashboard.view',
        'bookings.view', 'bookings.create', 'bookings.edit', 'bookings.cancel',
        'folios.view', 'folios.manage',
        'guests.view', 'guests.create', 'guests.edit',
        'room_setup.view',
        'cashflow.view', 'cashflow.money_in', 'cashflow.reconcile',
    },
    'restaurant_admin': {
        'dashboard.view', 'restaurant.view', 'menu.view', 'menu.manage', 'recipes.manage',
        'staff_meals.view', 'staff_meals.manage',
        'inventory.view', 'inventory.manage', 'stock_movements.create',
        'cashflow.view', 'cashflow.money_in',
    },
    'purchasing_admin': {
        'dashboard.view', 'inventory.view', 'inventory.manage', 'stock_movements.create',
        'suppliers.view', 'suppliers.manage',
        'purchase_requests.view', 'purchase_requests.create', 'purchase_requests.approve',
        'purchase_orders.view', 'purchase_orders.create', 'purchase_orders.approve',
        'receiving.view', 'receiving.post',
        'cashflow.view', 'cashflow.money_out',
    },
    'payroll_admin': {
        'dashboard.view', 'employees.view', 'employees.manage',
        'attendance.view', 'attendance.manage',
        'payroll_periods.view', 'payroll_periods.manage',
        'approvals.view', 'approvals.act',
        'cashflow.view', 'cashflow.money_out',
        'journals.view',
    },
    'accounting_admin': {
        'dashboard.view', 'review_inbox.view', 'review_inbox.act', 'hotel.view', 'events.view',
        'cash_treasury.view', 'daily_close.count', 'daily_close.approve', 'money.reverse',
        'cashflow.view', 'cashflow.money_in', 'cashflow.money_out', 'cashflow.transfers', 'cashflow.reconcile',
        'journals.view', 'journals.post', 'reports.view', 'assets.view', 'assets.manage',
        'bir.view', 'bir.manage',
        'chart_of_accounts.manage', 'account_mapping.manage',
        'master_data.manage', 'taxonomy.manage',
        'integrations.view', 'integrations.manage', 'integrations.sync', 'integrations.logs.view',
    },
    'cashier': {
        'dashboard.view', 'review_inbox.view',
        'folios.view', 'cashflow.view', 'cashflow.money_in', 'cashflow.reconcile',
        'cash_treasury.view', 'daily_close.count',
    },
    'auditor': {
        'dashboard.view', 'review_inbox.view', 'hotel.view', 'events.view',
        'bookings.view', 'guests.view', 'folios.view', 'cashflow.view',
        'cash_treasury.view', 'journals.view', 'reports.view', 'assets.view', 'bir.view',
        'integrations.view', 'integrations.logs.view',
    },
    'pos_integration': {
        'restaurant.view',
        'menu.view',
        'bookings.view',
        'guests.view',
        'folios.view',
        'folios.manage',
        'cashflow.view',
        'cashflow.money_in',
        'cashflow.money_out',
        'cashflow.transfers',
        'cashflow.reconcile',
        'inventory.view',
    },
}


def _norm(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _code(value: str | None) -> str:
    return (value or '').strip().lower().replace(' ', '_')


def _serialize_permission(row: Permission) -> dict:
    return {
        'id': row.id,
        'key': row.key,
        'label': row.label,
        'group_name': row.group_name,
        'description': row.description,
        'is_active': bool(row.is_active),
    }


def _serialize_role(row: Role) -> dict:
    permission_keys = sorted([
        link.permission.key
        for link in (row.permissions or [])
        if link.allowed and link.permission and link.permission.is_active
    ])
    return {
        'id': row.id,
        'code': row.code,
        'name': row.name,
        'description': row.description,
        'is_active': bool(row.is_active),
        'permission_keys': permission_keys,
        'permission_count': len(permission_keys),
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def ensure_permissions_seed(db: Session):
    existing_permissions = {row.key: row for row in db.query(Permission).all()}
    touched = 0
    for key, label, group_name in DEFAULT_PERMISSION_DEFS:
        row = existing_permissions.get(key)
        if row:
            changed = False
            if row.label != label:
                row.label = label
                changed = True
            if row.group_name != group_name:
                row.group_name = group_name
                changed = True
            if not row.is_active:
                row.is_active = True
                changed = True
            if changed:
                db.add(row)
                touched += 1
            continue
        db.add(Permission(key=key, label=label, group_name=group_name, is_active=True))
        touched += 1

    existing_roles = {row.code: row for row in db.query(Role).all()}
    for code, name, description in DEFAULT_ROLES:
        role = existing_roles.get(code)
        if role:
            changed = False
            if role.name != name:
                role.name = name
                changed = True
            if role.description != description:
                role.description = description
                changed = True
            if not role.is_active:
                role.is_active = True
                changed = True
            if changed:
                db.add(role)
                touched += 1
            continue
        db.add(Role(code=code, name=name, description=description, is_active=True))
        touched += 1

    if touched:
        db.commit()

    permission_by_key = {row.key: row for row in db.query(Permission).all()}
    roles = {row.code: row for row in db.query(Role).all()}

    for role_code, permission_keys in ROLE_PERMISSION_PRESETS.items():
        role = roles.get(role_code)
        if not role:
            continue
        current_links = {
            link.permission.key: link
            for link in db.query(RolePermission).options(selectinload(RolePermission.permission)).filter(RolePermission.role_id == role.id).all()
            if link.permission
        }
        for key in permission_keys:
            permission = permission_by_key.get(key)
            if not permission:
                continue
            link = current_links.get(key)
            if link:
                if not link.allowed:
                    link.allowed = True
                    db.add(link)
                continue
            db.add(RolePermission(role_id=role.id, permission_id=permission.id, allowed=True))
    db.commit()


def list_permissions(db: Session):
    ensure_permissions_seed(db)
    rows = db.query(Permission).filter(Permission.is_active == True).order_by(Permission.group_name.asc(), Permission.key.asc()).all()
    return [_serialize_permission(row) for row in rows]


def list_roles(db: Session, *, active_only: bool = False):
    ensure_permissions_seed(db)
    query = db.query(Role).options(selectinload(Role.permissions).selectinload(RolePermission.permission))
    if active_only:
        query = query.filter(Role.is_active == True)
    rows = query.order_by(Role.name.asc()).all()
    return [_serialize_role(row) for row in rows]


def create_role(db: Session, payload: RoleCreate):
    ensure_permissions_seed(db)
    code = _code(payload.code)
    name = _norm(payload.name)
    if not code:
        raise ValueError('code is required.')
    if not name:
        raise ValueError('name is required.')
    if db.query(Role).filter(Role.code == code).first():
        raise ValueError(f'Role code {code} already exists.')
    if db.query(Role).filter(Role.name == name).first():
        raise ValueError(f'Role name {name} already exists.')
    row = Role(
        code=code,
        name=name,
        description=payload.description,
        is_active=bool(payload.is_active),
    )
    db.add(row)
    db.commit()
    row = db.query(Role).options(selectinload(Role.permissions).selectinload(RolePermission.permission)).filter(Role.id == row.id).first()
    return _serialize_role(row)


def update_role(db: Session, role_id: int, payload: RoleUpdate):
    row = db.get(Role, int(role_id))
    if not row:
        raise ValueError('Role not found.')
    data = payload.model_dump(exclude_unset=True)
    if 'code' in data:
        code = _code(data.get('code'))
        if not code:
            raise ValueError('code cannot be blank.')
        dup = db.query(Role).filter(Role.code == code, Role.id != row.id).first()
        if dup:
            raise ValueError(f'Role code {code} already exists.')
        row.code = code
    if 'name' in data:
        name = _norm(data.get('name'))
        if not name:
            raise ValueError('name cannot be blank.')
        dup = db.query(Role).filter(Role.name == name, Role.id != row.id).first()
        if dup:
            raise ValueError(f'Role name {name} already exists.')
        row.name = name
    for key in ('description', 'is_active'):
        if key in data:
            setattr(row, key, data.get(key))
    db.add(row)
    db.commit()
    row = db.query(Role).options(selectinload(Role.permissions).selectinload(RolePermission.permission)).filter(Role.id == row.id).first()
    return _serialize_role(row)


def delete_role(db: Session, role_id: int):
    row = db.get(Role, int(role_id))
    if not row:
        raise ValueError('Role not found.')
    if row.code in {'owner'}:
        raise ValueError('Default owner role cannot be deleted.')
    db.query(UserRole).filter(UserRole.role_id == row.id).delete()
    db.query(RolePermission).filter(RolePermission.role_id == row.id).delete()
    db.delete(row)
    db.commit()
    return {'ok': True}


def set_role_permissions(db: Session, role_id: int, permission_keys: list[str]):
    role = db.get(Role, int(role_id))
    if not role:
        raise ValueError('Role not found.')
    ensure_permissions_seed(db)

    wanted = {k.strip() for k in permission_keys if k and k.strip()}
    permissions = {row.key: row for row in db.query(Permission).filter(Permission.is_active == True).all()}

    db.query(RolePermission).filter(RolePermission.role_id == role.id).delete()
    for key in sorted(wanted):
        permission = permissions.get(key)
        if not permission:
            continue
        db.add(RolePermission(role_id=role.id, permission_id=permission.id, allowed=True))
    db.commit()
    return list_roles(db)


def assign_user_roles(db: Session, user_id: int, role_ids: list[int]):
    user = db.get(User, int(user_id))
    if not user:
        raise ValueError('User not found.')

    valid_roles = {row.id for row in db.query(Role).filter(Role.id.in_(list({int(x) for x in role_ids if x}))).all()}
    db.query(UserRole).filter(UserRole.user_id == user.id).delete()
    for role_id in sorted(valid_roles):
        db.add(UserRole(user_id=user.id, role_id=role_id))
    db.commit()
    return get_user_roles(db, user.id)


def get_user_roles(db: Session, user_id: int):
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise ValueError('User not found.')
    links = db.query(UserRole).options(selectinload(UserRole.role)).filter(UserRole.user_id == user.id).all()
    return {
        'user_id': user.id,
        'username': user.username,
        'legacy_role': user.role,
        'role_ids': [link.role_id for link in links],
        'roles': [
            {
                'id': link.role.id,
                'code': link.role.code,
                'name': link.role.name,
            }
            for link in links
            if link.role
        ],
    }


def set_user_permission_overrides(db: Session, user_id: int, overrides: list[dict]):
    user = db.get(User, int(user_id))
    if not user:
        raise ValueError('User not found.')
    ensure_permissions_seed(db)
    permission_by_key = {row.key: row for row in db.query(Permission).all()}

    db.query(UserPermissionOverride).filter(UserPermissionOverride.user_id == user.id).delete()
    for item in overrides:
        key = (item.get('permission_key') or '').strip()
        permission = permission_by_key.get(key)
        if not permission:
            continue
        db.add(
            UserPermissionOverride(
                user_id=user.id,
                permission_id=permission.id,
                is_allowed=bool(item.get('is_allowed', True)),
            )
        )
    db.commit()
    return get_user_effective_permissions(db, user.id)


def get_user_effective_permissions(db: Session, user_id: int):
    ensure_permissions_seed(db)
    user = db.get(User, int(user_id))
    if not user:
        raise ValueError('User not found.')

    links = db.query(UserRole).filter(UserRole.user_id == user.id).all()
    role_ids = [link.role_id for link in links]
    if not role_ids and user.role:
        fallback = db.query(Role).filter(Role.code == _code(user.role)).first()
        if fallback:
            role_ids = [fallback.id]

    allowed_by_role = set()
    if role_ids:
        rows = (
            db.query(RolePermission)
            .options(selectinload(RolePermission.permission))
            .filter(RolePermission.role_id.in_(role_ids), RolePermission.allowed == True)
            .all()
        )
        for row in rows:
            if row.permission and row.permission.is_active:
                allowed_by_role.add(row.permission.key)

    overrides = (
        db.query(UserPermissionOverride)
        .options(selectinload(UserPermissionOverride.permission))
        .filter(UserPermissionOverride.user_id == user.id)
        .all()
    )
    for row in overrides:
        if not row.permission:
            continue
        if row.is_allowed:
            allowed_by_role.add(row.permission.key)
        elif row.permission.key in allowed_by_role:
            allowed_by_role.remove(row.permission.key)

    return {
        'user_id': user.id,
        'permissions': sorted(allowed_by_role),
        'roles': get_user_roles(db, user.id),
    }


def get_user_permission_keys(db: Session, user: User) -> set[str]:
    data = get_user_effective_permissions(db, user.id)
    return set(data.get('permissions') or [])
