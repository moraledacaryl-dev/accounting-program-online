"""Deployment retry integrity: never waive backups or overwrite artifacts."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (ROOT / '.github/workflows/deploy-accounting.yml').read_text()
ACTIVATE = (ROOT / 'scripts/release/activate-release.sh').read_text()
VERIFY = (ROOT / 'scripts/release/verify-release.sh').read_text()


def test_deployment_preflight_checks_disk_and_writable_database_before_preparation():
    preflight = WORKFLOW.index('Available bytes for mandatory database backup')
    verify = WORKFLOW.index('Prepared release already exists; verifying exact identity')
    activate = WORKFLOW.index('bash "$RELEASE/scripts/release/activate-release.sh"')
    assert preflight < verify < activate
    assert '4294967296' in WORKFLOW  # 4 GiB before expensive new build or backup.
    assert "SELECT pg_is_in_recovery()" in WORKFLOW
    assert 'pg_isready -h 127.0.0.1 -p 5432' in WORKFLOW


def test_existing_release_can_only_be_reused_after_full_immutable_verification():
    assert 'test -d "$RELEASE"' in WORKFLOW
    assert 'test ! -L "$RELEASE"' in WORKFLOW
    assert 'bash "$RELEASE/scripts/release/verify-release.sh" "$RELEASE_SHA"' in WORKFLOW
    for guard in (
        'manifest_value release_sha', 'manifest_value tree_sha',
        'manifest_value backend_requirements_sha256',
        'manifest_value frontend_lock_sha256',
        'manifest_value backend_env_sha256', 'manifest_value frontend_env_sha256',
        'manifest_value frontend_build_id',
    ):
        assert guard in VERIFY


def test_activation_still_requires_database_and_uploads_backup_before_migration():
    assert ACTIVATE.index('backup-accounting.sh') < ACTIVATE.index('alembic -c alembic.ini upgrade head')
    assert 'ROOT="$RELEASE" BACKUP_UPLOADS_DIR="$DEPLOY_UPLOADS_DIR"' in ACTIVATE
    assert 'pg_dump -Fc' in (ROOT / 'scripts/dr/backup-accounting.sh').read_text()
    assert 'pg_restore --list "$TMP"' in (ROOT / 'scripts/dr/backup-accounting.sh').read_text()
