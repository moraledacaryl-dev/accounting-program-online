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
methods_allowed = {'get', 'post', 'put', 'patch', 'delete', 'head', 'options'}
for route, methods in sorted(spec.get('paths', {}).items()):
    for method, meta in sorted(methods.items()):
        if method.lower() not in methods_allowed:
            continue
        parameters = []
        for parameter in meta.get('parameters', []):
            parameters.append({
                'name': parameter.get('name'),
                'in': parameter.get('in'),
                'required': bool(parameter.get('required')),
                'schema': parameter.get('schema', {}),
            })
        request_body = meta.get('requestBody') or None
        responses = {
            code: {
                'description': value.get('description') if isinstance(value, dict) else None,
                'content_types': sorted((value.get('content') or {}).keys()) if isinstance(value, dict) else [],
            }
            for code, value in sorted((meta.get('responses') or {}).items())
        }
        rows.append({
            'method': method.upper(),
            'route': route,
            'operation_id': meta.get('operationId'),
            'tags': meta.get('tags', []),
            'summary': meta.get('summary'),
            'deprecated': bool(meta.get('deprecated', False)),
            'security': meta.get('security', spec.get('security', [])),
            'parameters': parameters,
            'request_body': request_body,
            'responses': responses,
        })

by_tag = {}
by_method = {}
for row in rows:
    by_method[row['method']] = by_method.get(row['method'], 0) + 1
    tags = row['tags'] or ['untagged']
    for tag in tags:
        by_tag[tag] = by_tag.get(tag, 0) + 1

out = Path(os.environ.get('AUDIT_ENDPOINT_OUTPUT', 'audit-artifacts/screenshots/endpoint-manifest.json'))
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({
    'count': len(rows),
    'methods': dict(sorted(by_method.items())),
    'tags': dict(sorted(by_tag.items())),
    'endpoints': rows,
}, indent=2), encoding='utf-8')
print(f'Exported {len(rows)} API endpoints to {out}')
