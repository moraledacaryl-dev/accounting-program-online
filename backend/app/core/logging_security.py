from __future__ import annotations

import logging
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


SENSITIVE_QUERY_KEYS = {
    'secret',
    'token',
    'access_token',
    'api_key',
    'apikey',
    'key',
    'password',
    'signature',
    'sig',
}
REDACTED = '[REDACTED]'


def redact_sensitive_query(url: str) -> str:
    """Redact secret-like query parameter values while preserving routing context."""
    text = str(url or '')
    try:
        parsed = urlsplit(text)
        if not parsed.query:
            return text
        pairs = parse_qsl(parsed.query, keep_blank_values=True)
        changed = False
        safe_pairs: list[tuple[str, str]] = []
        for key, value in pairs:
            if key.strip().lower() in SENSITIVE_QUERY_KEYS:
                safe_pairs.append((key, REDACTED))
                changed = True
            else:
                safe_pairs.append((key, value))
        if not changed:
            return text
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(safe_pairs), parsed.fragment))
    except Exception:
        # Logging must never create a new application failure. If parsing fails,
        # suppress the query portion rather than risk emitting credentials.
        return text.split('?', 1)[0]


class SensitiveQueryAccessLogFilter(logging.Filter):
    """Redact sensitive query values from Uvicorn access-log path arguments."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if not isinstance(args, tuple) or len(args) < 3:
            return True
        path = args[2]
        if not isinstance(path, str) or '?' not in path:
            return True
        mutable = list(args)
        mutable[2] = redact_sensitive_query(path)
        record.args = tuple(mutable)
        return True


def install_sensitive_access_log_filter() -> None:
    logger = logging.getLogger('uvicorn.access')
    if any(isinstance(item, SensitiveQueryAccessLogFilter) for item in logger.filters):
        return
    logger.addFilter(SensitiveQueryAccessLogFilter())
