"""Run real Linux shell programs against disposable backup directories."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / 'scripts/release/release-lock.sh'
BACKUP = ROOT / 'scripts/dr/backup-accounting.sh'


@unittest.skipUnless(sys.platform.startswith('linux') and shutil.which('flock'), 'Linux flock gate')
class ReleaseSerialization(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='accounting-release-test-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.lock_dir = self.path / 'lock'
        self.env = {**os.environ, 'ACCOUNTING_RELEASE_LOCK_DIR': str(self.lock_dir),
                    'LOCK_HELPER': str(LOCK), 'PYTHONDONTWRITEBYTECODE': '1'}

    def shell(self, code, *, env=None, timeout=8):
        return subprocess.run(['bash', '-e', '-c', code], env=env or self.env, text=True,
                              capture_output=True, timeout=timeout)

    def test_second_process_fails_busy_then_recovers_and_nested_child_inherits_lock(self):
        first = subprocess.Popen(
            ['bash', '-c', 'source "$LOCK_HELPER"; accounting_release_lock; echo READY; read -r release'],
            env=self.env, text=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.addCleanup(lambda: first.poll() is None and first.kill())
        self.addCleanup(first.stdin.close)
        self.addCleanup(first.stdout.close)
        self.addCleanup(first.stderr.close)
        self.assertEqual(first.stdout.readline().strip(), 'READY')
        busy = self.shell('source "$LOCK_HELPER"; accounting_release_lock; echo UNEXPECTED')
        self.assertEqual(busy.returncode, 75)
        self.assertNotIn('UNEXPECTED', busy.stdout)
        first.stdin.write('release\n'); first.stdin.flush()
        self.assertEqual(first.wait(timeout=5), 0)
        nested = self.shell('source "$LOCK_HELPER"; accounting_release_lock; bash -c '\
                            '\'source "$LOCK_HELPER"; accounting_release_lock; echo NESTED\'')
        self.assertEqual(nested.returncode, 0, nested.stderr)
        self.assertEqual(nested.stdout.strip(), 'NESTED')

    def test_forged_inherited_marker_and_symlink_are_rejected(self):
        forged = self.shell('source "$LOCK_HELPER"; accounting_release_lock',
                            env={**self.env, 'ACCOUNTING_RELEASE_LOCK_HELD': '1'})
        self.assertNotEqual(forged.returncode, 0)
        self.assertFalse(self.lock_dir.joinpath('deployment.lock').is_symlink())
        self.lock_dir.mkdir(mode=0o700, exist_ok=True)
        target = self.path / 'other'; target.write_text('unchanged')
        self.lock_dir.joinpath('deployment.lock').symlink_to(target)
        unsafe = self.shell('source "$LOCK_HELPER"; accounting_release_lock')
        self.assertNotEqual(unsafe.returncode, 0)
        self.assertEqual(target.read_text(), 'unchanged')

    def fixture(self):
        release = self.path / 'release'
        runner = release / 'backend/.venv/bin/python'
        runner.parent.mkdir(parents=True)
        runner.write_text('#!/bin/sh\nprintf synthetic_database\n')
        runner.chmod(0o700)
        env_file = self.path / 'accounting.env'; env_file.write_text('DATABASE_URL=synthetic-only\n')
        uploads = self.path / 'uploads'; uploads.mkdir(); (uploads / 'original.txt').write_text('synthetic upload')
        backups = self.path / 'backups'; backups.mkdir(mode=0o700)
        bin_dir = self.path / 'bin'; bin_dir.mkdir()
        stubs = {
            'date': '#!/bin/sh\necho 20261025T120000Z\n',
            'df': '#!/bin/sh\nprintf "Avail\\n5000000000\\n"\n',
            'sudo': '#!/bin/bash\nshift 2\nif [ "$1" = "pg_dump" ]; then '
                    '[ "${FAIL_PG_DUMP:-0}" != 1 ] || exit 13; printf synthetic-custom-dump; '
                    'elif [ "$1" = "psql" ]; then printf 0017_journal_linkage_review; '
                    'else exit 2; fi\n',
            'pg_restore': '#!/bin/sh\n[ "$1" = "--list" ] && [ -s "$2" ]\n',
        }
        for name, body in stubs.items():
            path = bin_dir / name; path.write_text(body); path.chmod(0o700)
        return {**self.env, 'ROOT': str(release), 'BACKUP_DIR': str(backups),
                'BACKUP_UPLOADS_DIR': str(uploads), 'ENV_FILE': str(env_file),
                'PATH': str(bin_dir) + os.pathsep + os.environ['PATH']}, backups

    def test_backup_keeps_old_archive_and_refuses_same_second_collision(self):
        env, backups = self.fixture()
        free = subprocess.check_output(['df', '-B1', '--output=avail', str(backups)], env=env, text=True)
        self.assertEqual(free.splitlines()[-1], '5000000000')
        old = backups / 'accounting-20261001T000000Z.dump'; old.write_text('historical evidence')
        one = subprocess.run(['bash', str(BACKUP)], env=env, text=True, capture_output=True)
        self.assertEqual(one.returncode, 0, one.stderr)
        created = {p.name: p.read_bytes() for p in backups.iterdir() if p.name != old.name}
        self.assertEqual(len(created), 3)
        self.assertIn('sha256=', created['accounting-20261025T120000Z.meta'].decode())
        second = subprocess.run(['bash', str(BACKUP)], env=env, text=True, capture_output=True)
        self.assertNotEqual(second.returncode, 0)
        self.assertEqual({p.name: p.read_bytes() for p in backups.iterdir() if p.name != old.name}, created)
        self.assertEqual(old.read_text(), 'historical evidence')

    def test_failed_dump_cannot_publish_incomplete_manifest_or_remove_history(self):
        env, backups = self.fixture()
        old = backups / 'accounting-20261001T000000Z.dump'; old.write_text('historical evidence')
        failed = subprocess.run(['bash', str(BACKUP)], env={**env, 'FAIL_PG_DUMP': '1'}, text=True, capture_output=True)
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual([p.name for p in backups.iterdir()], [old.name])
        self.assertEqual(old.read_text(), 'historical evidence')

    def test_low_space_blocks_before_dump_and_preserves_history(self):
        env, backups = self.fixture()
        (self.path / 'bin/df').write_text('#!/bin/sh\nprintf "Avail\\n500\\n"\n')
        old = backups / 'accounting-20261001T000000Z.dump'; old.write_text('historical evidence')
        blocked = subprocess.run(['bash', str(BACKUP)], env=env, text=True, capture_output=True)
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn('less than 4 GiB', blocked.stderr)
        self.assertEqual([p.name for p in backups.iterdir()], [old.name])


if __name__ == '__main__':
    unittest.main()
