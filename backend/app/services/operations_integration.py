import json
import logging
from datetime import date, datetime, timezone
from typing import Any
from urllib import error, request

from app.core.settings import settings

logger = logging.getLogger(__name__)


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def publish_operations_event(
    *,
    event_id: str,
    event_type: str,
    title: str,
    summary: str,
    payload: dict[str, Any],
    priority: str = 'Normal',
    subject_type: str | None = None,
    subject_id: int | str | None = None,
) -> None:
    if not settings.operations_integration_enabled:
        return
    base = settings.operations_api_base.rstrip('/')
    key = settings.operations_integration_key.strip()
    if not base or not key:
        logger.warning('Operations integration enabled but endpoint or key is missing')
        return

    envelope: dict[str, Any] = {
        'event_id': event_id,
        'event_type': event_type,
        'schema_version': 1,
        'occurred_at': datetime.now(timezone.utc).isoformat(),
        'title': title,
        'summary': summary,
        'priority': priority,
        'payload': _json_value(payload),
        'metadata': {'producer': 'accounting-program-online'},
    }
    if subject_type and subject_id is not None:
        envelope['subject'] = {'type': subject_type, 'id': str(subject_id)}

    body = json.dumps(envelope, separators=(',', ':')).encode('utf-8')
    endpoint = f"{base}/integrations/v2/events/{settings.operations_source_app}"
    outbound = request.Request(
        endpoint,
        data=body,
        method='POST',
        headers={
            'Content-Type': 'application/json',
            'X-Integration-Api-Key': key,
        },
    )
    try:
        with request.urlopen(outbound, timeout=settings.operations_integration_timeout_seconds) as response:
            response.read()
    except (error.HTTPError, error.URLError, TimeoutError, OSError) as exc:
        logger.warning('Operations event delivery failed for %s: %s', event_id, exc)


def is_due_or_overdue(due_date: str | None) -> bool:
    if not due_date:
        return False
    try:
        parsed = date.fromisoformat(due_date[:10])
    except ValueError:
        return False
    return parsed <= date.today()
