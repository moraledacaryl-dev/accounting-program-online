from __future__ import annotations

import copy
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import Role, SystemSetting, User, UserRole

DASHBOARD_WIDGET_CATALOG = [
    {'key': 'arrivals_today', 'label': 'Arrivals Today', 'description': 'Expected arrivals for today.', 'type': 'metric'},
    {'key': 'departures_today', 'label': 'Departures Today', 'description': 'Expected departures for today.', 'type': 'metric'},
    {'key': 'in_house_guests', 'label': 'In-house Guests', 'description': 'Bookings currently checked in.', 'type': 'metric'},
    {'key': 'vip_arrivals_today', 'label': 'VIP Arrivals', 'description': 'VIP guests arriving today.', 'type': 'metric'},
    {'key': 'occupancy_rate', 'label': 'Occupancy', 'description': 'Checked-in rooms versus active room count.', 'type': 'metric'},
    {'key': 'revenue_today', 'label': 'Revenue Today', 'description': 'Combined room + F&B revenue snapshot.', 'type': 'metric'},
    {'key': 'cash_in_today', 'label': 'Cash In Today', 'description': 'Total money-in transactions today.', 'type': 'metric'},
    {'key': 'cash_out_today', 'label': 'Cash Out Today', 'description': 'Total money-out transactions today.', 'type': 'metric'},
    {'key': 'pending_approvals', 'label': 'Pending Approvals', 'description': 'Items awaiting action across workflows.', 'type': 'metric'},
    {'key': 'low_stock_count', 'label': 'Low Stock Alerts', 'description': 'Inventory items at or below reorder level.', 'type': 'metric'},
    {'key': 'overdue_receivables', 'label': 'Overdue Receivables', 'description': 'Receivables past due date.', 'type': 'metric'},
    {'key': 'overdue_payables', 'label': 'Overdue Payables', 'description': 'Payables past due date.', 'type': 'metric'},
    {'key': 'fnb_sales_today', 'label': 'F&B Sales Today', 'description': 'Outlet sales total for today.', 'type': 'metric'},
    {'key': 'labor_summary', 'label': 'Labor Summary', 'description': 'Draft/reviewed payroll periods and employee count.', 'type': 'metric'},
    {'key': 'bir_status', 'label': 'BIR Status', 'description': 'Current lock/review posture for BIR periods.', 'type': 'metric'},
    {'key': 'top_channels', 'label': 'Top Channels', 'description': 'Booking volume and revenue by channel.', 'type': 'table'},
    {'key': 'low_stock_items', 'label': 'Low Stock Items', 'description': 'Inventory items that need replenishment.', 'type': 'table'},
    {'key': 'pending_by_workflow', 'label': 'Pending by Workflow', 'description': 'Approval queue grouped by workflow.', 'type': 'table'},
]

DASHBOARD_ROLE_OPTIONS = [
    {'key': 'owner', 'label': 'Owner'},
    {'key': 'manager', 'label': 'Manager'},
    {'key': 'front_desk', 'label': 'Front Desk'},
    {'key': 'restaurant_admin', 'label': 'Restaurant / F&B'},
    {'key': 'accounting_admin', 'label': 'Accounting / Finance'},
    {'key': 'purchasing_admin', 'label': 'Purchasing'},
    {'key': 'payroll_admin', 'label': 'Payroll'},
]

CODE_ENTITY_CATALOG = [
    {'key': 'room_type', 'label': 'Room Types', 'field': 'code'},
    {'key': 'room', 'label': 'Rooms', 'field': 'room_no'},
    {'key': 'rate_plan', 'label': 'Rate Plans', 'field': 'code'},
    {'key': 'booking_channel', 'label': 'Booking Channels', 'field': 'code'},
    {'key': 'supplier', 'label': 'Suppliers', 'field': 'code'},
    {'key': 'purchase_request', 'label': 'Purchase Requests', 'field': 'request_no'},
    {'key': 'purchase_order', 'label': 'Purchase Orders', 'field': 'po_no'},
    {'key': 'receiving', 'label': 'Receiving', 'field': 'receiving_no'},
    {'key': 'chart_account', 'label': 'Chart Accounts', 'field': 'code'},
    {'key': 'financial_account', 'label': 'Financial Accounts', 'field': 'code'},
]

DEFAULT_ROLE_WIDGETS = {
    'owner': [
        'occupancy_rate',
        'arrivals_today',
        'departures_today',
        'in_house_guests',
        'revenue_today',
        'cash_in_today',
        'cash_out_today',
        'pending_approvals',
        'overdue_receivables',
        'overdue_payables',
        'low_stock_count',
        'top_channels',
        'pending_by_workflow',
        'bir_status',
    ],
    'manager': [
        'occupancy_rate',
        'arrivals_today',
        'departures_today',
        'revenue_today',
        'cash_in_today',
        'cash_out_today',
        'pending_approvals',
        'low_stock_count',
        'top_channels',
        'pending_by_workflow',
    ],
    'front_desk': [
        'arrivals_today',
        'departures_today',
        'in_house_guests',
        'vip_arrivals_today',
        'occupancy_rate',
        'cash_in_today',
        'pending_approvals',
    ],
    'restaurant_admin': [
        'fnb_sales_today',
        'revenue_today',
        'low_stock_count',
        'cash_in_today',
        'pending_approvals',
        'low_stock_items',
    ],
    'accounting_admin': [
        'cash_in_today',
        'cash_out_today',
        'pending_approvals',
        'overdue_receivables',
        'overdue_payables',
        'bir_status',
        'pending_by_workflow',
    ],
    'purchasing_admin': [
        'low_stock_count',
        'pending_approvals',
        'overdue_payables',
        'low_stock_items',
        'pending_by_workflow',
    ],
    'payroll_admin': [
        'labor_summary',
        'pending_approvals',
        'cash_out_today',
        'overdue_payables',
    ],
}

DEFAULT_CODE_ENTITIES = {
    'room_type': {'prefix': 'RT', 'digits': 4, 'include_year': False, 'include_month': False, 'separator': '-', 'editable_after_create': True},
    'room': {'prefix': 'RM', 'digits': 4, 'include_year': False, 'include_month': False, 'separator': '-', 'editable_after_create': True},
    'rate_plan': {'prefix': 'RP', 'digits': 4, 'include_year': False, 'include_month': False, 'separator': '-', 'editable_after_create': True},
    'booking_channel': {'prefix': 'CH', 'digits': 4, 'include_year': False, 'include_month': False, 'separator': '-', 'editable_after_create': True},
    'supplier': {'prefix': 'SUP', 'digits': 4, 'include_year': False, 'include_month': False, 'separator': '-', 'editable_after_create': True},
    'purchase_request': {'prefix': 'PR', 'digits': 4, 'include_year': True, 'include_month': False, 'separator': '-', 'editable_after_create': True},
    'purchase_order': {'prefix': 'PO', 'digits': 4, 'include_year': True, 'include_month': False, 'separator': '-', 'editable_after_create': True},
    'receiving': {'prefix': 'RCV', 'digits': 4, 'include_year': True, 'include_month': False, 'separator': '-', 'editable_after_create': True},
    'chart_account': {'prefix': 'ACC', 'digits': 4, 'include_year': False, 'include_month': False, 'separator': '-', 'editable_after_create': True},
    'financial_account': {'prefix': 'FA', 'digits': 4, 'include_year': False, 'include_month': False, 'separator': '-', 'editable_after_create': True},
}

DEFAULT_SYSTEM_SETTINGS = {
    'general': {
        'business_name': 'PrimeSlice Hospitality',
        'property_name': 'PrimeSlice Resort',
        'timezone': 'Asia/Manila',
        'currency': 'PHP',
        'default_language': 'en',
        'date_format': 'YYYY-MM-DD',
        'number_format': '#,##0.00',
    },
    'dashboard': {
        'allow_user_overrides': False,
        'role_widgets': copy.deepcopy(DEFAULT_ROLE_WIDGETS),
        'user_widgets': {},
    },
    'code_generation': {
        'allow_manual_override': True,
        'entities': copy.deepcopy(DEFAULT_CODE_ENTITIES),
    },
    'financial_defaults': {
        'default_cash_account_id': None,
        'default_bank_account_id': None,
        'auto_require_daily_reconciliation': True,
        'default_bir_include': False,
    },
    'workflow': {
        'require_approval_purchase_requests': True,
        'require_approval_purchase_orders': True,
        'require_approval_cashflow': False,
        'require_approval_payroll_posting': True,
        'allow_reopen_locked_periods': True,
    },
    'hospitality': {
        'default_check_in_time': '14:00',
        'default_check_out_time': '12:00',
        'default_booking_status': 'confirmed',
    },
    'payroll': {
        'default_period_name_pattern': 'Payroll {period_start} to {period_end}',
        'require_review_before_post': True,
    },
    'ui': {
        'table_page_size': 20,
        'show_inactive_by_default': False,
        'default_landing_by_role': {},
    },
}

SETTING_SECTIONS = tuple(DEFAULT_SYSTEM_SETTINGS.keys())
WIDGET_KEYS = {row['key'] for row in DASHBOARD_WIDGET_CATALOG}


def _safe_json_load(raw: str | None) -> Any:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _safe_json_dump(value: Any) -> str:
    try:
        return json.dumps(value or {}, ensure_ascii=True, separators=(',', ':'))
    except Exception:
        return '{}'


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _deep_merge(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in (incoming or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _normalize_widget_list(keys: list[Any] | None) -> list[str]:
    ordered: list[str] = []
    seen = set()
    for key in (keys or []):
        text = str(key or '').strip()
        if not text or text not in WIDGET_KEYS or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _normalize_dashboard(settings: dict[str, Any]) -> dict[str, Any]:
    raw = _as_dict(settings)
    role_widgets = _as_dict(raw.get('role_widgets'))
    normalized_role_widgets: dict[str, list[str]] = {}
    for option in DASHBOARD_ROLE_OPTIONS:
        role_key = option['key']
        base = DEFAULT_ROLE_WIDGETS.get(role_key, [])
        chosen = _normalize_widget_list(role_widgets.get(role_key))
        normalized_role_widgets[role_key] = chosen or list(base)

    raw_user_widgets = _as_dict(raw.get('user_widgets'))
    user_widgets: dict[str, list[str]] = {}
    for user_key, widget_keys in raw_user_widgets.items():
        normalized = _normalize_widget_list(widget_keys if isinstance(widget_keys, list) else [])
        if normalized:
            user_widgets[str(user_key)] = normalized

    return {
        'allow_user_overrides': bool(raw.get('allow_user_overrides', False)),
        'role_widgets': normalized_role_widgets,
        'user_widgets': user_widgets,
    }


def _normalize_code_entities(raw_entities: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, defaults in DEFAULT_CODE_ENTITIES.items():
        source = _as_dict(raw_entities.get(key))
        prefix = str(source.get('prefix') if source.get('prefix') is not None else defaults['prefix']).strip().upper()
        if not prefix:
            prefix = defaults['prefix']
        digits = source.get('digits', defaults['digits'])
        try:
            digits = int(digits)
        except Exception:
            digits = int(defaults['digits'])
        digits = max(2, min(8, digits))
        separator = str(source.get('separator') if source.get('separator') is not None else defaults['separator']).strip()
        if not separator:
            separator = '-'
        out[key] = {
            'prefix': prefix,
            'digits': digits,
            'include_year': bool(source.get('include_year', defaults['include_year'])),
            'include_month': bool(source.get('include_month', defaults['include_month'])),
            'separator': separator,
            'editable_after_create': bool(source.get('editable_after_create', defaults['editable_after_create'])),
        }
    return out


def _normalize_code_generation(settings: dict[str, Any]) -> dict[str, Any]:
    raw = _as_dict(settings)
    entities = _normalize_code_entities(_as_dict(raw.get('entities')))
    return {
        'allow_manual_override': bool(raw.get('allow_manual_override', True)),
        'entities': entities,
    }


def normalize_system_settings(settings: dict[str, Any]) -> dict[str, Any]:
    merged = _deep_merge(copy.deepcopy(DEFAULT_SYSTEM_SETTINGS), _as_dict(settings))
    merged['dashboard'] = _normalize_dashboard(merged.get('dashboard'))
    merged['code_generation'] = _normalize_code_generation(merged.get('code_generation'))

    merged['general'] = _as_dict(merged.get('general'))
    merged['financial_defaults'] = _as_dict(merged.get('financial_defaults'))
    merged['workflow'] = _as_dict(merged.get('workflow'))
    merged['hospitality'] = _as_dict(merged.get('hospitality'))
    merged['payroll'] = _as_dict(merged.get('payroll'))
    merged['ui'] = _as_dict(merged.get('ui'))

    table_page_size = merged['ui'].get('table_page_size', 20)
    try:
        table_page_size = int(table_page_size)
    except Exception:
        table_page_size = 20
    merged['ui']['table_page_size'] = max(10, min(200, table_page_size))
    return merged


def load_system_settings(db: Session) -> dict[str, Any]:
    rows = db.query(SystemSetting).filter(SystemSetting.key.in_(SETTING_SECTIONS)).all()
    current: dict[str, Any] = {}
    for row in rows:
        current[row.key] = _safe_json_load(row.value_json)
    return normalize_system_settings(current)


def save_system_settings(db: Session, updates: dict[str, Any], *, updated_by: str | None = None) -> dict[str, Any]:
    existing = load_system_settings(db)
    merged = copy.deepcopy(existing)

    for section in SETTING_SECTIONS:
        if section not in updates:
            continue
        value = updates.get(section)
        if isinstance(value, dict):
            merged[section] = _deep_merge(_as_dict(merged.get(section)), value)

    normalized = normalize_system_settings(merged)

    rows = {row.key: row for row in db.query(SystemSetting).filter(SystemSetting.key.in_(SETTING_SECTIONS)).all()}
    for section in SETTING_SECTIONS:
        row = rows.get(section)
        if not row:
            row = SystemSetting(key=section)
        row.value_json = _safe_json_dump(normalized.get(section) or {})
        row.updated_by = updated_by
        db.add(row)
    db.commit()
    return normalized


def dashboard_widget_catalog() -> list[dict[str, Any]]:
    return copy.deepcopy(DASHBOARD_WIDGET_CATALOG)


def dashboard_role_options() -> list[dict[str, str]]:
    return copy.deepcopy(DASHBOARD_ROLE_OPTIONS)


def code_entity_catalog() -> list[dict[str, str]]:
    return copy.deepcopy(CODE_ENTITY_CATALOG)


def settings_meta() -> dict[str, Any]:
    return {
        'dashboard_roles': dashboard_role_options(),
        'dashboard_widgets': dashboard_widget_catalog(),
        'code_entities': code_entity_catalog(),
    }


def resolve_dashboard_role_for_user(db: Session, user: User) -> str:
    role_codes: set[str] = set()
    legacy = str(getattr(user, 'role', '') or '').strip().lower()
    if legacy:
        role_codes.add(legacy)

    links = (
        db.query(UserRole)
        .join(Role, Role.id == UserRole.role_id)
        .filter(UserRole.user_id == int(user.id), Role.is_active == True)
        .all()
    )
    for link in links:
        if link.role and link.role.code:
            role_codes.add(str(link.role.code).strip().lower())

    ordered = [
        'owner',
        'manager',
        'front_desk',
        'restaurant_admin',
        'accounting_admin',
        'purchasing_admin',
        'payroll_admin',
    ]
    for role_key in ordered:
        if role_key in role_codes:
            return role_key

    if role_codes:
        return sorted(role_codes)[0]
    return 'manager'


def get_effective_dashboard_widgets(db: Session, user: User, *, settings: dict[str, Any] | None = None) -> tuple[str, list[str]]:
    settings = settings or load_system_settings(db)
    dashboard = _as_dict(settings.get('dashboard'))
    role = resolve_dashboard_role_for_user(db, user)
    role_widgets = _as_dict(dashboard.get('role_widgets')).get(role) or DEFAULT_ROLE_WIDGETS.get(role, [])
    widgets = _normalize_widget_list(role_widgets)

    if bool(dashboard.get('allow_user_overrides', False)):
        user_widgets_map = _as_dict(dashboard.get('user_widgets'))
        override = user_widgets_map.get(str(user.id))
        if isinstance(override, list):
            override_keys = _normalize_widget_list(override)
            if override_keys:
                widgets = override_keys

    if not widgets:
        widgets = list(DEFAULT_ROLE_WIDGETS.get('manager', []))
    return role, widgets


def set_user_dashboard_override(
    db: Session,
    *,
    user_id: int,
    widgets: list[str],
    updated_by: str | None = None,
) -> dict[str, Any]:
    settings = load_system_settings(db)
    dashboard = _as_dict(settings.get('dashboard'))
    user_widgets = _as_dict(dashboard.get('user_widgets'))
    normalized = _normalize_widget_list(widgets)
    if normalized:
        user_widgets[str(user_id)] = normalized
    elif str(user_id) in user_widgets:
        user_widgets.pop(str(user_id), None)

    dashboard['user_widgets'] = user_widgets
    return save_system_settings(db, {'dashboard': dashboard}, updated_by=updated_by)


def get_code_rule(settings: dict[str, Any], entity_key: str) -> dict[str, Any]:
    code_settings = _as_dict(_as_dict(settings.get('code_generation')).get('entities'))
    base = DEFAULT_CODE_ENTITIES.get(entity_key, {'prefix': entity_key.upper(), 'digits': 4, 'include_year': False, 'include_month': False, 'separator': '-', 'editable_after_create': True})
    merged = _deep_merge(base, _as_dict(code_settings.get(entity_key)))
    return _normalize_code_entities({entity_key: merged})[entity_key]
