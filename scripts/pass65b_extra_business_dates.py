from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / 'backend/app/services/event_service.py'
text = path.read_text(encoding='utf-8')

if 'from app.core.business_clock import business_today\n' not in text:
    marker = '\nfrom app.'
    if marker not in text:
        raise SystemExit('event_service.py: app import anchor not found')
    text = text.replace(marker, '\nfrom app.core.business_clock import business_today\nfrom app.', 1)

old = "return datetime.utcnow().strftime('%Y-%m-%d')"
if text.count(old) != 1:
    raise SystemExit(f'event_service.py: expected one UTC business-date fallback, found {text.count(old)}')
text = text.replace(old, 'return business_today()', 1)
path.write_text(text, encoding='utf-8')
print('Event business-date fallback moved to Manila clock.')
