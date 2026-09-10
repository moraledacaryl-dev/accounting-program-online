import json
import os
from pathlib import Path

os.environ.setdefault('ENVIRONMENT', 'test')
os.environ.setdefault('DATABASE_URL', 'sqlite:///./screenshot-audit-openapi.db')
os.environ.setdefault('SECRET_KEY', 'c' * 64)
os.environ.setdefault('STARTUP_REQUIRE_MIGRATIONS', 'false')
os.environ.setdefault('ALLOW_DEFAULT_ADMIN_BOOTSTRAP', 'false')
os.environ.setdefault('ALLOW_DEMO_SEED', 'false')

from app.main import app

spec = app.openapi()
rows = []
for route, methods in sorted(spec.get('paths', {}).items()):
    for method, meta in sorted(methods.items()):
        if method.lower() not in {'get', 'post', 'put', 'patch', 'delete', 'head', 'options'}:
            continue
        rows.append({
            'method': method.upper(),
            'route': route,
            'operation_id': meta.get('operationId'),
            'tags': meta.get('tags', []),
            'summary': meta.get('summary'),
        })

out = Path(os.environ.get('AUDIT_ENDPOINT_OUTPUT', 'audit-artifacts/screenshots/endpoint-manifest.json'))
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({'count': len(rows), 'endpoints': rows}, indent=2), encoding='utf-8')
print(f'Exported {len(rows)} API endpoints to {out}')