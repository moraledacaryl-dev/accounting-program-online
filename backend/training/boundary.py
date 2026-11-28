"""Bind every business request to its participant-owned, versioned practice."""
import re
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from training.curriculum import BY_ID, VERSION

def install_boundary(app, store, root, identity):
    @app.middleware('http')
    async def boundary(request, call_next):
        route = request.url.path.rstrip('/') or '/'
        method = request.method.upper()
        # Next removes trailing slashes while FastAPI collection routes add
        # them. Resolve the declared collection route internally, without a
        # redirect loop or sending the browser to the backend port.
        if route.startswith('/api/') and not request.url.path.endswith('/'):
            if route+'/' in app.openapi()['paths']:
                request.scope['path'] = route+'/'
                request.scope['raw_path'] = (route+'/').encode()
        def denied(code, message):
            return JSONResponse(status_code=code, content={'detail': message}, headers={'x-accounting-environment':'isolated-training', 'Cache-Control':'no-store'})
        if method not in {'GET', 'HEAD', 'OPTIONS'}:
            if request.headers.get('origin') not in {None, 'http://127.0.0.1:3420', 'http://localhost:3420'}:
                return denied(403, 'Use the Accounting Training window to save practice work.')
            if request.headers.get('x-requested-with') != 'HiddenOasisAccountingTraining':
                return denied(403, 'The training request verification is missing.')
        if route.startswith('/api/') and not route.startswith('/api/training/') and route != '/api/healthz':
            try:
                learner = identity(request)
                attempt = store.attempt(learner['id'])
                if not attempt or attempt['curriculum_version'] != VERSION:
                    raise HTTPException(409, 'Start or continue your current lesson from Training.')
                if request.headers.get('x-training-attempt') != attempt['id']:
                    raise HTTPException(409, 'This practice changed in another tab. Return to Training and continue the current task.')
                request.state.training_attempt = attempt
            except HTTPException as exc:
                return denied(exc.status_code, exc.detail)
            # These handlers can send external requests or manage identities/files;
            # they have no employee mutation path in this separate trainer.
            if any(route.startswith(prefix) for prefix in ('/api/integration/', '/api/integrations/', '/api/setup-imports', '/api/attachments', '/api/seed')):
                return denied(403, 'External delivery, imports and live connections are disabled in training.')
            if method not in {'GET', 'HEAD'}:
                if attempt['status']=='passed' and route != '/api/auth/logout':
                    return denied(409, 'This passed attempt is preserved. Start a fresh practice for further changes.')
                lesson = BY_ID[attempt['lesson_id']]
                from training.scenarios import values
                fixture = values(lesson, attempt['mode'])
                allowed = any(step.outcome and re.fullmatch(re.escape('/api'+step.outcome.format(**fixture).rstrip('/')).replace(r'\*', r'[0-9]+'), route)
                    and method == (step.outcome_method or 'POST') for step in lesson.steps)
                if not allowed and route != '/api/auth/logout':
                    return denied(403, 'This action is outside the current practice assignment. Return to the course to start another task.')
            response = await call_next(request)
            if method == 'GET':
                from training.scenarios import inspection_endpoint
                expected_read = inspection_endpoint(BY_ID[attempt['lesson_id']])
                if expected_read and response.status_code == 200 and route == expected_read.rstrip('/'):
                    store.event(attempt['id'], 'record_read', {'path':inspection_endpoint(BY_ID[attempt['lesson_id']]), 'method':'GET', 'status':200})
            else:
                detail = ''
                if response.status_code >= 400:
                    # Retain only the bounded fictional error reason, so a CSRF
                    # or malformed-request error cannot impersonate a business refusal.
                    import json
                    body = b''.join([chunk.encode() if isinstance(chunk,str) else chunk async for chunk in response.body_iterator])
                    async def replay():
                        yield body
                    response.body_iterator = replay()
                    try:
                        value=json.loads(body).get('detail','')
                        detail=value[:300] if isinstance(value,str) else ''
                    except (ValueError,AttributeError):
                        pass
                store.event(attempt['id'], 'business_action', {'path':route, 'method':method, 'status':response.status_code, 'detail':detail})
                expected = any(step.outcome_status == response.status_code for step in BY_ID[attempt['lesson_id']].steps)
                if response.status_code >= 400 and not expected:
                    with store.connect() as db:
                        db.execute("UPDATE attempts SET mistakes=mistakes+1 WHERE id=? AND status='active'", (attempt['id'],))
        else:
            response = await call_next(request)
        response.headers['x-accounting-environment'] = 'isolated-training'
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        # FastAPI's slash redirects otherwise expose the backend port through
        # the local Next proxy, losing the same-origin participant cookies.
        if response.status_code in {307, 308} and 'location' in response.headers:
            from urllib.parse import urlsplit
            destination = urlsplit(response.headers['location'])
            if destination.hostname in {'127.0.0.1', 'localhost'} and destination.path.startswith('/api/'):
                response.headers['location'] = destination.path + (('?' + destination.query) if destination.query else '')
        if route == '/api/auth/logout' and method == 'POST':
            response.delete_cookie('accounting_training_participant')
        return response
