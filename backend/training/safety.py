"""Configure a separate practice process before importing any application router."""
import json
import os
from pathlib import Path
import secrets
import sys

MARKER = {'application': 'hidden-oasis-accounting-training', 'schema': 1}


def configure(root: Path) -> Path:
    if root.is_symlink():
        raise RuntimeError('Training data cannot be a symbolic link.')
    root = root.expanduser().absolute()
    if root.name != 'accounting-training':
        raise RuntimeError('Use a dedicated accounting-training data directory.')
    if os.environ.get('ACCOUNTING_TRAINING_ORIGIN'):
        raise RuntimeError('This standalone build supports only its local training origin.')
    forbidden = [key for key, value in os.environ.items() if value and (
        key in {'DATABASE_URL', 'SECRET_KEY', 'UPLOADS_DIR', 'INTERNAL_API_URL', 'NEXT_PUBLIC_API_BASE'}
        or 'INTEGRATION' in key or key.startswith(('PGHOST', 'PGDATABASE', 'PGUSER', 'PGPASSWORD')))]
    if forbidden:
        raise RuntimeError('Training refuses inherited database, credential, API or integration configuration: ' + ', '.join(sorted(forbidden)))
    if os.environ.get('ENVIRONMENT', 'training') not in {'training', 'test'}:
        raise RuntimeError('Use the separate training launcher, not an operational environment.')
    for directory in {Path.cwd(), Path.cwd().parent, Path(__file__).resolve().parents[1], Path(__file__).resolve().parents[2]}:
        if any(directory.glob('.env')) or any(directory.glob('.env.local')):
            raise RuntimeError('Training must run from a separate checkout without operational .env files.')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == 'posix':
        root.chmod(0o700)
    marker = root / 'training-only.json'
    if marker.exists():
        if marker.is_symlink() or json.loads(marker.read_text()) != MARKER:
            raise RuntimeError('The training directory marker is invalid.')
    elif any(root.iterdir()):
        raise RuntimeError('Refusing an unmarked nonempty training directory.')
    else:
        marker.write_text(json.dumps(MARKER))
    secret_file = root / 'session-key'
    if secret_file.is_symlink():
        raise RuntimeError('The training session key cannot be a symbolic link.')
    if not secret_file.exists():
        fd = os.open(secret_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(secrets.token_hex(48))
    secret = secret_file.read_text().strip()
    if len(secret) < 64:
        raise RuntimeError('The training session key is incomplete.')
    from app.core import settings as config
    values = dict(environment='training', database_url='sqlite:///:memory:', secret_key=secret,
        allow_default_admin_bootstrap=False, allow_demo_seed=False, startup_require_migrations=False,
        integration_enabled=False, operations_integration_enabled=False, integration_api_key='',
        operations_integration_key='', integration_password=secrets.token_hex(32), integration_secret=secrets.token_hex(32),
        cors_origins='http://127.0.0.1:3420,http://localhost:3420',
        auth_cookie_name='accounting_training_session', csrf_cookie_name='accounting_training_csrf',
        auth_cookie_samesite='strict', auth_cookie_domain='', auth_cookie_secure=False,
        uploads_dir=str(root / 'uploads'), public_uploads_enabled=False)
    # Keep one settings object so the source modules all use the same isolated values.
    for key, value in values.items():
        setattr(config.settings, key, value)
    # Frozen modules and the source checkout have different __file__ depths.
    # Resolve the same bundled source taxonomy explicitly in the trainer.
    from app.services import taxonomy_service
    source_root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[2]))
    taxonomy_service.TAXONOMY_PATH=source_root/'shared'/'taxonomy.json'
    taxonomy_service.MODULE_INDEX_PATH=source_root/'shared'/'module_index.json'
    return root


def deny_network(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo', 'socket.gethostbyname', 'socket.sendto'}:
        raise PermissionError('Accounting Training cannot initiate network connections.')


def install_network_guard():
    sys.addaudithook(deny_network)
