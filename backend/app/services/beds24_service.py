from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from app.models.entities import SystemSetting


INTEGRATIONS_SETTING_KEY = 'integrations'

DEFAULT_BEDS24_SETTINGS: dict[str, Any] = {
    'enabled': False,
    'api_base_url': 'https://beds24.com/api/v2',
    'access_token': '',
    'refresh_token': '',
    'invite_code': '',
    'webhook_enabled': False,
    'webhook_secret': '',
    'webhook_require_secret': True,
    'manual_sync_only': True,
    'auto_create_guest': True,
    'auto_create_folio_mirror': False,
    'auto_create_receivable_mirror': False,
    'auto_link_room': True,
    'auto_link_channel': True,
    'auto_link_property': False,
    'fallback_unknown_room_behavior': 'leave_unlinked',
    'fallback_unknown_channel_behavior': 'leave_unlinked',
    'include_invoice_items': True,
    'log_verbosity': 'normal',
    'room_map_by_room_id': {},
    'room_map_by_unit_id': {},
    'channel_map_by_source': {},
    'property_map_by_id': {},
}


class Beds24ApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def _safe_json_load(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return {}


def _safe_json_dump(data: dict[str, Any]) -> str:
    try:
        return json.dumps(data or {}, ensure_ascii=True, separators=(',', ':'))
    except Exception:
        return '{}'


def _as_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        low = value.strip().lower()
        if low in {'1', 'true', 'yes', 'on'}:
            return True
        if low in {'0', 'false', 'no', 'off'}:
            return False
    return fallback


def _normalize_str(value: Any, fallback: str = '') -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _normalize_int_map(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, int] = {}
    for key, item in value.items():
        source_key = _normalize_str(key)
        if not source_key:
            continue
        try:
            out[source_key] = int(item)
        except Exception:
            continue
    return out


def _normalize_str_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, str] = {}
    for key, item in value.items():
        source_key = _normalize_str(key)
        source_value = _normalize_str(item)
        if not source_key or not source_value:
            continue
        out[source_key] = source_value
    return out


def normalize_beds24_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
    raw = settings if isinstance(settings, dict) else {}
    out = dict(DEFAULT_BEDS24_SETTINGS)
    out['enabled'] = _as_bool(raw.get('enabled'), DEFAULT_BEDS24_SETTINGS['enabled'])
    out['api_base_url'] = _normalize_str(raw.get('api_base_url'), DEFAULT_BEDS24_SETTINGS['api_base_url']).rstrip('/')
    out['access_token'] = _normalize_str(raw.get('access_token'))
    out['refresh_token'] = _normalize_str(raw.get('refresh_token'))
    out['invite_code'] = _normalize_str(raw.get('invite_code'))
    out['webhook_enabled'] = _as_bool(raw.get('webhook_enabled'), DEFAULT_BEDS24_SETTINGS['webhook_enabled'])
    out['webhook_secret'] = _normalize_str(raw.get('webhook_secret'))
    out['webhook_require_secret'] = _as_bool(raw.get('webhook_require_secret'), DEFAULT_BEDS24_SETTINGS['webhook_require_secret'])
    out['manual_sync_only'] = _as_bool(raw.get('manual_sync_only'), DEFAULT_BEDS24_SETTINGS['manual_sync_only'])
    out['auto_create_guest'] = _as_bool(raw.get('auto_create_guest'), DEFAULT_BEDS24_SETTINGS['auto_create_guest'])
    out['auto_create_folio_mirror'] = _as_bool(raw.get('auto_create_folio_mirror'), DEFAULT_BEDS24_SETTINGS['auto_create_folio_mirror'])
    out['auto_create_receivable_mirror'] = _as_bool(raw.get('auto_create_receivable_mirror'), DEFAULT_BEDS24_SETTINGS['auto_create_receivable_mirror'])
    out['auto_link_room'] = _as_bool(raw.get('auto_link_room'), DEFAULT_BEDS24_SETTINGS['auto_link_room'])
    out['auto_link_channel'] = _as_bool(raw.get('auto_link_channel'), DEFAULT_BEDS24_SETTINGS['auto_link_channel'])
    out['auto_link_property'] = _as_bool(raw.get('auto_link_property'), DEFAULT_BEDS24_SETTINGS['auto_link_property'])
    out['fallback_unknown_room_behavior'] = _normalize_str(raw.get('fallback_unknown_room_behavior'), DEFAULT_BEDS24_SETTINGS['fallback_unknown_room_behavior'])
    out['fallback_unknown_channel_behavior'] = _normalize_str(raw.get('fallback_unknown_channel_behavior'), DEFAULT_BEDS24_SETTINGS['fallback_unknown_channel_behavior'])
    out['include_invoice_items'] = _as_bool(raw.get('include_invoice_items'), DEFAULT_BEDS24_SETTINGS['include_invoice_items'])
    out['log_verbosity'] = _normalize_str(raw.get('log_verbosity'), DEFAULT_BEDS24_SETTINGS['log_verbosity'])
    out['room_map_by_room_id'] = _normalize_int_map(raw.get('room_map_by_room_id'))
    out['room_map_by_unit_id'] = _normalize_int_map(raw.get('room_map_by_unit_id'))
    out['channel_map_by_source'] = _normalize_int_map(raw.get('channel_map_by_source'))
    out['property_map_by_id'] = _normalize_str_map(raw.get('property_map_by_id'))
    return out


def _load_integrations_raw(db: Session) -> dict[str, Any]:
    row = db.query(SystemSetting).filter(SystemSetting.key == INTEGRATIONS_SETTING_KEY).first()
    return _safe_json_load(row.value_json if row else '{}')


def load_beds24_settings(db: Session) -> dict[str, Any]:
    all_settings = _load_integrations_raw(db)
    return normalize_beds24_settings(all_settings.get('beds24'))


def save_beds24_settings(db: Session, updates: dict[str, Any], *, updated_by: str | None = None) -> dict[str, Any]:
    current = load_beds24_settings(db)
    merged = dict(current)
    for key, value in (updates or {}).items():
        if key not in DEFAULT_BEDS24_SETTINGS:
            continue
        merged[key] = value
    normalized = normalize_beds24_settings(merged)

    row = db.query(SystemSetting).filter(SystemSetting.key == INTEGRATIONS_SETTING_KEY).first()
    all_settings = _safe_json_load(row.value_json if row else '{}')
    all_settings['beds24'] = normalized

    if not row:
        row = SystemSetting(key=INTEGRATIONS_SETTING_KEY)
    row.value_json = _safe_json_dump(all_settings)
    row.updated_by = updated_by
    db.add(row)
    db.commit()
    return normalized


def _api_get(base_url: str, path: str, *, headers: dict[str, str] | None = None, params: dict[str, Any] | None = None) -> Any:
    query = urlencode([(k, v) for k, v in (params or {}).items() if v is not None and str(v) != ''], doseq=True)
    url = f'{base_url}{path}'
    if query:
        url = f'{url}?{query}'
    req = Request(url, method='GET', headers={'accept': 'application/json', **(headers or {})})
    try:
        with urlopen(req, timeout=30) as response:
            raw = response.read().decode('utf-8')
            if not raw:
                return {}
            return json.loads(raw)
    except HTTPError as exc:
        try:
            detail_raw = exc.read().decode('utf-8')
            detail = json.loads(detail_raw) if detail_raw else None
        except Exception:
            detail = None
        message = f'Beds24 request failed ({exc.code})'
        if isinstance(detail, dict):
            detail_message = detail.get('message') or detail.get('detail') or detail.get('error')
            if detail_message:
                message = f'{message}: {detail_message}'
        raise Beds24ApiError(message, status_code=exc.code, payload=detail) from exc
    except URLError as exc:
        raise Beds24ApiError(f'Beds24 connection failed: {exc.reason}') from exc
    except Exception as exc:
        raise Beds24ApiError(f'Beds24 request failed: {exc}') from exc


def _extract_token_payload(payload: Any) -> tuple[str, str]:
    if not isinstance(payload, dict):
        raise Beds24ApiError('Beds24 token response is invalid.')
    access = _normalize_str(payload.get('token'))
    refresh = _normalize_str(payload.get('refreshToken'))
    if not access:
        raise Beds24ApiError('Beds24 token response does not contain token.')
    return access, refresh


def _refresh_token(base_url: str, refresh_token: str) -> tuple[str, str]:
    payload = _api_get(
        base_url,
        '/authentication/token',
        headers={'refreshToken': refresh_token},
    )
    access, refreshed = _extract_token_payload(payload)
    return access, (refreshed or refresh_token)


def _setup_with_invite(base_url: str, invite_code: str) -> tuple[str, str]:
    payload = _api_get(
        base_url,
        '/authentication/setup',
        headers={'code': invite_code},
    )
    access, refresh = _extract_token_payload(payload)
    if not refresh:
        raise Beds24ApiError('Beds24 setup response does not contain refreshToken.')
    return access, refresh


def ensure_beds24_access_token(db: Session, settings: dict[str, Any], *, force_refresh: bool = False) -> tuple[str, dict[str, Any]]:
    base_url = _normalize_str(settings.get('api_base_url'), DEFAULT_BEDS24_SETTINGS['api_base_url']).rstrip('/')
    access_token = _normalize_str(settings.get('access_token'))
    refresh_token = _normalize_str(settings.get('refresh_token'))
    invite_code = _normalize_str(settings.get('invite_code'))

    if access_token and not force_refresh:
        return access_token, settings

    if refresh_token:
        access_token, refresh_token = _refresh_token(base_url, refresh_token)
        updated = save_beds24_settings(
            db,
            {
                'access_token': access_token,
                'refresh_token': refresh_token,
            },
        )
        return access_token, updated

    if invite_code:
        access_token, refresh_token = _setup_with_invite(base_url, invite_code)
        updated = save_beds24_settings(
            db,
            {
                'access_token': access_token,
                'refresh_token': refresh_token,
            },
        )
        return access_token, updated

    raise Beds24ApiError('Beds24 access token is missing. Configure refresh token or invite code first.')


def extract_bookings_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ('bookings', 'data', 'result', 'items'):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if payload.get('id') is not None:
            return [payload]
    return []


def fetch_beds24_bookings(
    db: Session,
    *,
    booking_id: str | None = None,
    status: str | None = None,
    filter_value: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    arrival_from: str | None = None,
    arrival_to: str | None = None,
    property_id: str | None = None,
    include_invoice_items: bool | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    settings = load_beds24_settings(db)
    if not settings.get('enabled'):
        raise Beds24ApiError('Beds24 integration is disabled.')

    token, settings = ensure_beds24_access_token(db, settings)
    base_url = _normalize_str(settings.get('api_base_url'), DEFAULT_BEDS24_SETTINGS['api_base_url']).rstrip('/')

    params: dict[str, Any] = {}
    if booking_id:
        params['id'] = _normalize_str(booking_id)
    if status:
        params['status'] = _normalize_str(status)
    if filter_value:
        params['filter'] = _normalize_str(filter_value)
    if limit and int(limit) > 0:
        params['limit'] = int(limit)
    if offset and int(offset) > 0:
        params['offset'] = int(offset)
    if arrival_from:
        params['arrivalFrom'] = _normalize_str(arrival_from)
    if arrival_to:
        params['arrivalTo'] = _normalize_str(arrival_to)
    if property_id:
        params['propertyId'] = _normalize_str(property_id)

    use_invoice_items = settings.get('include_invoice_items', True) if include_invoice_items is None else bool(include_invoice_items)
    if use_invoice_items:
        params['includeInvoiceItems'] = 'true'

    try:
        payload = _api_get(base_url, '/bookings', headers={'token': token}, params=params)
    except Beds24ApiError as exc:
        if exc.status_code == 401:
            token, settings = ensure_beds24_access_token(db, settings, force_refresh=True)
            payload = _api_get(base_url, '/bookings', headers={'token': token}, params=params)
        else:
            raise

    bookings = extract_bookings_from_payload(payload)
    return bookings, payload, settings


def test_beds24_connection(db: Session) -> dict[str, Any]:
    settings = load_beds24_settings(db)
    if not settings.get('enabled'):
        raise Beds24ApiError('Beds24 integration is disabled.')
    bookings, payload, updated_settings = fetch_beds24_bookings(db, limit=1, include_invoice_items=False)
    return {
        'ok': True,
        'checked_at': _now_iso(),
        'api_base_url': updated_settings.get('api_base_url'),
        'booking_count': len(bookings),
        'sample_booking_id': str(bookings[0].get('id')) if bookings else None,
        'response_keys': sorted(list(payload.keys())) if isinstance(payload, dict) else [],
    }
