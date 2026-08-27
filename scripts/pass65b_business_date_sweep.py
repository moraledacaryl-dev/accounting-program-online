from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_exact(path: str, old: str, new: str, *, count: int | None = 1) -> None:
    target = ROOT / path
    text = target.read_text(encoding='utf-8')
    found = text.count(old)
    if count is not None and found != count:
        raise SystemExit(f'{path}: expected {count} occurrence(s) of {old!r}, found {found}')
    if count is None and found < 1:
        raise SystemExit(f'{path}: expected at least one occurrence of {old!r}')
    target.write_text(text.replace(old, new), encoding='utf-8')


def ensure_import(path: str, anchor: str, import_line: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding='utf-8')
    if import_line in text:
        return
    if anchor not in text:
        raise SystemExit(f'{path}: import anchor not found: {anchor!r}')
    target.write_text(text.replace(anchor, f'{anchor}{import_line}', 1), encoding='utf-8')


# Backend: business-calendar semantics only. Technical timestamps remain UTC.
backend_helpers = [
    'backend/app/services/cashflow_service.py',
    'backend/app/services/procurement_service.py',
    'backend/app/services/hospitality_service.py',
    'backend/app/services/guest_service.py',
    'backend/app/services/room_setup_service.py',
]
for path in backend_helpers:
    target = ROOT / path
    text = target.read_text(encoding='utf-8')
    if 'from app.core.business_clock import business_today\n' not in text:
        marker = '\nfrom app.'
        if marker not in text:
            raise SystemExit(f'{path}: app import anchor not found')
        text = text.replace(marker, '\nfrom app.core.business_clock import business_today\nfrom app.', 1)
    old = "return datetime.utcnow().strftime('%Y-%m-%d')"
    if old not in text:
        raise SystemExit(f'{path}: expected legacy _today UTC fallback not found')
    text = text.replace(old, 'return business_today()', 1)
    target.write_text(text, encoding='utf-8')

# Restaurant operational business dates.
path = 'backend/app/services/restaurant_service.py'
target = ROOT / path
text = target.read_text(encoding='utf-8')
if 'from app.core.business_clock import business_today\n' not in text:
    marker = '\nfrom app.'
    if marker not in text:
        raise SystemExit(f'{path}: app import anchor not found')
    text = text.replace(marker, '\nfrom app.core.business_clock import business_today\nfrom app.', 1)
for old, new in [
    ("payload.order_date or datetime.utcnow().strftime('%Y-%m-%d')", 'payload.order_date or business_today()'),
    ("payload.void_date or datetime.utcnow().strftime('%Y-%m-%d')", 'payload.void_date or business_today()'),
]:
    if text.count(old) != 1:
        raise SystemExit(f'{path}: expected one occurrence of {old!r}, found {text.count(old)}')
    text = text.replace(old, new, 1)
target.write_text(text, encoding='utf-8')

# Asset service/disposal business dates.
path = 'backend/app/api/asset_registry.py'
target = ROOT / path
text = target.read_text(encoding='utf-8')
if 'from app.core.business_clock import business_today\n' not in text:
    marker = '\nfrom app.'
    if marker not in text:
        raise SystemExit(f'{path}: app import anchor not found')
    text = text.replace(marker, '\nfrom app.core.business_clock import business_today\nfrom app.', 1)
for old, new in [
    ("payload.service_date or datetime.utcnow().strftime('%Y-%m-%d')", 'payload.service_date or business_today()'),
    ("payload.disposal_date or datetime.utcnow().strftime('%Y-%m-%d')", 'payload.disposal_date or business_today()'),
]:
    if text.count(old) != 1:
        raise SystemExit(f'{path}: expected one occurrence of {old!r}, found {text.count(old)}')
    text = text.replace(old, new, 1)
target.write_text(text, encoding='utf-8')

# Reports: defaults, aging, close/as-of calculations all use Manila business date.
path = 'backend/app/api/reports.py'
target = ROOT / path
text = target.read_text(encoding='utf-8')
if 'from app.core.business_clock import business_today\n' not in text:
    marker = 'from app.api.deps import require_any_permissions, require_permissions\n'
    if marker not in text:
        raise SystemExit(f'{path}: import anchor not found')
    text = text.replace(marker, marker + 'from app.core.business_clock import business_today\n', 1)
old = "def _today() -> str:\n    return datetime.utcnow().strftime('%Y-%m-%d')"
new = "def _today() -> str:\n    return business_today()"
if text.count(old) != 1:
    raise SystemExit(f'{path}: report _today legacy fallback not found exactly once')
text = text.replace(old, new, 1)
old = 'as_of = _parse_iso_date(as_of_date) or datetime.utcnow()'
new = "as_of = _parse_iso_date(as_of_date) or datetime.strptime(business_today(), '%Y-%m-%d')"
if text.count(old) != 1:
    raise SystemExit(f'{path}: aging UTC fallback not found exactly once')
text = text.replace(old, new, 1)
target.write_text(text, encoding='utf-8')

# Frontend simple business-today helpers.
frontend_today = {
    'frontend/app/staff-meals/page.js': '../../lib/businessDate',
    'frontend/app/bookings/page.js': '../../lib/businessDate',
    'frontend/app/integrations/beds24/page.js': '../../../lib/businessDate',
    'frontend/app/reports/page.js': '../../lib/businessDate',
    'frontend/app/assets/page.js': '../../lib/businessDate',
    'frontend/app/room-folios/[id]/page.js': '../../../lib/businessDate',
    'frontend/app/channel-payouts/page.js': '../../lib/businessDate',
    'frontend/app/restaurant-ops/page.js': '../../lib/businessDate',
}
for path, import_path in frontend_today.items():
    target = ROOT / path
    text = target.read_text(encoding='utf-8')
    import_line = f"import {{ businessDateISO }} from '{import_path}';\n"
    if import_line not in text:
        marker = "'use client';\n"
        if marker not in text:
            raise SystemExit(f'{path}: client import anchor not found')
        text = text.replace(marker, marker + import_line, 1)
    old = 'return new Date().toISOString().slice(0, 10);'
    if old not in text:
        raise SystemExit(f'{path}: expected direct UTC today helper not found')
    text = text.replace(old, 'return businessDateISO();', 1)
    target.write_text(text, encoding='utf-8')

# Beds24 future date: base the month shift on the Manila calendar day, not browser-local/UTC date.
path = 'frontend/app/integrations/beds24/page.js'
target = ROOT / path
text = target.read_text(encoding='utf-8')
old = "function addMonthsISO(months) {\n  const date = new Date();\n  date.setMonth(date.getMonth() + months);\n  return date.toISOString().slice(0, 10);\n}"
new = "function addMonthsISO(months) {\n  const [year, month, day] = businessDateISO().split('-').map(Number);\n  const date = new Date(Date.UTC(year, month - 1 + months, day, 12, 0, 0));\n  return businessDateISO(date);\n}"
if text.count(old) != 1:
    raise SystemExit(f'{path}: expected addMonthsISO UTC implementation not found exactly once')
text = text.replace(old, new, 1)
target.write_text(text, encoding='utf-8')

# Reports month-start default must follow the Manila month even when the browser is in UTC/another zone.
path = 'frontend/app/reports/page.js'
target = ROOT / path
text = target.read_text(encoding='utf-8')
old = "function monthStartISO() {\n  const d = new Date();\n  d.setDate(1);\n  return d.toISOString().slice(0, 10);\n}"
new = "function monthStartISO() {\n  return `${businessDateISO().slice(0, 7)}-01`;\n}"
if text.count(old) != 1:
    raise SystemExit(f'{path}: expected monthStartISO UTC implementation not found exactly once')
text = text.replace(old, new, 1)
target.write_text(text, encoding='utf-8')

# Booking calendar initializes from the Manila business date rather than the viewer machine's calendar date.
path = 'frontend/app/bookings/calendar/page.js'
target = ROOT / path
text = target.read_text(encoding='utf-8')
import_line = "import { businessDateISO } from '../../../lib/businessDate';\n"
if import_line not in text:
    marker = "'use client';\n"
    if marker not in text:
        raise SystemExit(f'{path}: client import anchor not found')
    text = text.replace(marker, marker + import_line, 1)
old = 'const [monthDate, setMonthDate] = useState(startOfCalendarMonth(new Date()));'
new = "const [monthDate, setMonthDate] = useState(() => {\n    const [year, month, day] = businessDateISO().split('-').map(Number);\n    return startOfCalendarMonth(new Date(year, month - 1, day, 12, 0, 0));\n  });"
if text.count(old) != 1:
    raise SystemExit(f'{path}: expected local calendar initialization not found exactly once')
text = text.replace(old, new, 1)
target.write_text(text, encoding='utf-8')

# Guard: no remaining date-only UTC conversion in known business UI pages.
for path in list(frontend_today) + ['frontend/app/bookings/calendar/page.js']:
    text = (ROOT / path).read_text(encoding='utf-8')
    if 'toISOString().slice(0, 10)' in text:
        raise SystemExit(f'{path}: residual date-only UTC conversion remains')

# Guard: no legacy date-only UTC fallbacks remain anywhere in backend application code.
backend_residuals = []
for target in (ROOT / 'backend/app').rglob('*.py'):
    text = target.read_text(encoding='utf-8')
    if "datetime.utcnow().strftime('%Y-%m-%d')" in text:
        backend_residuals.append(str(target.relative_to(ROOT)))
if backend_residuals:
    raise SystemExit('Residual backend UTC business-date fallbacks: ' + ', '.join(sorted(backend_residuals)))

print('Pass 65b guarded business-date sweep applied successfully.')
