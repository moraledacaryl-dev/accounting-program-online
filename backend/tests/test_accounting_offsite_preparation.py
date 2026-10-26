"""Synthetic source and failure checks; no cloud or production data is used."""
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import os
from unittest import TestCase, mock
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/dr/offsite_accounting.py"
spec = importlib.util.spec_from_file_location("accounting_offsite", SCRIPT)
offsite = importlib.util.module_from_spec(spec)
spec.loader.exec_module(offsite)


class FakeRestic:
    def __init__(self, *, existing=False, used=0):
        self.calls = []
        self.existing = existing
        self.used = used

    def run(self, *args):
        self.calls.append(args)
        if args[0] == "snapshots":
            return json.dumps([{"id": "a" * 64}] if self.existing else []).encode()
        if args[0] == "stats":
            return json.dumps({"total_size": self.used}).encode()
        if args[0] == "backup":
            return (json.dumps({"message_type": "summary", "snapshot_id": "b" * 64}) + "\n").encode()
        if args[0] == "check":
            return b"{}"
        raise AssertionError(args)


class AccountingOffsitePreparation(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="accounting-offsite-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / "backups"
        self.base.mkdir(mode=0o700)
        self.sha = "c" * 40
        release = self.root / self.sha
        release.mkdir()
        self.current = self.root / "current"
        self.current.symlink_to(release)
        self.stamp = "20261026T020000Z"
        prefix = self.base / ("accounting-" + self.stamp)
        self.dump = Path(str(prefix) + ".dump")
        self.uploads = Path(str(prefix) + ".uploads.tar.gz")
        self.meta = Path(str(prefix) + ".meta")
        self.dump.write_bytes(b"synthetic custom archive")
        with tarfile.open(self.uploads, "w:gz") as archive:
            info = tarfile.TarInfo("./evidence.txt")
            content = b"synthetic upload"
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
        self.write_meta()
        for path in (self.dump, self.uploads, self.meta):
            path.chmod(0o600)
        self.now = datetime(2026, 10, 26, 2, 10, tzinfo=timezone.utc)

    def write_meta(self):
        self.meta.write_text("\n".join((
            "format=postgresql-custom", "created_utc=" + self.stamp,
            "database=synthetic_only", "sha256=" + hashlib.sha256(self.dump.read_bytes()).hexdigest(),
            "size_bytes=" + str(self.dump.stat().st_size), "release_sha=" + self.sha,
            "alembic_revision=0017_journal_linkage_review", "uploads_archive=" + self.uploads.name,
            "uploads_sha256=" + hashlib.sha256(self.uploads.read_bytes()).hexdigest(), "",
        )))

    def verified(self):
        with mock.patch.object(offsite.subprocess, "run", return_value=mock.Mock(returncode=0)):
            return offsite.verified_source(self.base, self.current, now=self.now)

    def test_missing_or_disabled_config_never_uses_credentials(self):
        self.assertEqual(offsite.read_config(self.root / "absent.json"), {"enabled": False})
        config = self.root / "disabled.json"
        config.write_text('{"enabled": false, "password_file": "missing"}')
        config.chmod(0o600)
        self.assertEqual(offsite.read_config(config), {"enabled": False})

    def test_config_rejects_wrong_repository_and_missing_gates(self):
        config = self.root / "config.json"
        config.write_text(json.dumps({"enabled": True, "repository": offsite.REPOSITORY}))
        config.chmod(0o600)
        with self.assertRaises(offsite.OffsiteError):
            offsite.read_config(config)
        data = {"enabled": True, "account_caps_verified": True,
                "recovery_key_custody_confirmed": True, "retention_policy_approved": True,
                "repository": offsite.REPOSITORY.replace("accounting", "operations", 1)}
        config.write_text(json.dumps(data))
        with self.assertRaises(offsite.OffsiteError):
            offsite.read_config(config)
        config.chmod(0o644)
        with self.assertRaises(offsite.OffsiteError):
            offsite.read_config(config)

    def test_effective_backblaze_key_scope_rejects_master_or_wrong_prefix(self):
        class Response:
            def __init__(self, data):
                self.data = json.dumps({"apiInfo": {"storageApi": data}}).encode()

            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def read(self, _):
                return self.data

        scope = {"bucketName": "hidden-oasis-accounting-backups-20261026",
                 "namePrefix": "accounting/",
                 "s3ApiUrl": "https://s3.us-west-004.backblazeb2.com",
                 "capabilities": ["listFiles", "readFiles", "writeFiles", "deleteFiles"]}
        keys = {"access_key_id": "synthetic", "secret_access_key": "synthetic"}
        with mock.patch.object(offsite, "urlopen", return_value=Response(scope)) as authorize:
            offsite.verify_key_scope(keys)
        self.assertEqual(authorize.call_count, 1)
        self.assertEqual(authorize.call_args.kwargs["timeout"], 15)
        for changed in ({"namePrefix": "operations/"}, {"capabilities": scope["capabilities"] + ["listAllBucketNames"]}):
            with mock.patch.object(offsite, "urlopen", return_value=Response({**scope, **changed})):
                with self.assertRaisesRegex(offsite.OffsiteError, "key scope"):
                    offsite.verify_key_scope(keys)

    def test_private_operator_config_can_be_read_without_leaking_secrets(self):
        password = self.root / "password"
        password.write_text("synthetic-restic-password-long-enough\n")
        password.chmod(0o600)
        credentials = self.root / "credentials.json"
        credentials.write_text(json.dumps({"access_key_id": "synthetic-id",
                                           "secret_access_key": "synthetic-secret"}))
        credentials.chmod(0o600)
        config = self.root / "config.json"
        config.write_text(json.dumps({"enabled": True, "account_caps_verified": True,
                                      "recovery_key_custody_confirmed": True,
                                      "retention_policy_approved": True,
                                      "repository": offsite.REPOSITORY,
                                      "password_file": str(password),
                                      "credentials_file": str(credentials)}))
        config.chmod(0o600)
        loaded = offsite.read_config(config)
        self.assertTrue(loaded["enabled"])
        self.assertEqual(loaded["keys"]["access_key_id"], "synthetic-id")
        credentials.chmod(0o644)
        with self.assertRaisesRegex(offsite.OffsiteError, "Private"):
            offsite.read_config(config)

    def test_verified_set_and_idempotent_retry(self):
        files, stamp, sha, size = self.verified()
        self.assertEqual(files, (self.dump, self.uploads, self.meta))
        self.assertEqual((stamp, sha), (self.stamp, self.sha))
        self.assertEqual(size, sum(x.stat().st_size for x in files))
        client = FakeRestic()
        offsite.upload_source(files, stamp, sha, size, client)
        self.assertEqual([call[0] for call in client.calls], ["snapshots", "stats", "backup", "check"])
        self.assertEqual(client.calls[2][-3:], tuple(map(str, files)))
        retry = FakeRestic(existing=True)
        offsite.upload_source(files, stamp, sha, size, retry)
        self.assertEqual([call[0] for call in retry.calls], ["snapshots", "check"])

    def test_tampering_stale_and_incomplete_set_fail_closed(self):
        self.dump.write_bytes(b"synthetic custom archivE")
        with self.assertRaisesRegex(offsite.OffsiteError, "checksum"):
            self.verified()
        self.dump.write_bytes(b"synthetic custom archive")
        with mock.patch.object(offsite.subprocess, "run", return_value=mock.Mock(returncode=0)):
            with self.assertRaisesRegex(offsite.OffsiteError, "not fresh"):
                offsite.verified_source(self.base, self.current, now=self.now + timedelta(hours=2))
        self.uploads.unlink()
        with self.assertRaises((offsite.OffsiteError, FileNotFoundError)):
            self.verified()

    def test_unsafe_archive_and_backup_permissions_rejected(self):
        with tarfile.open(self.uploads, "w:gz") as archive:
            info = tarfile.TarInfo("../../escape")
            info.size = 1
            archive.addfile(info, io.BytesIO(b"x"))
        self.write_meta()
        with self.assertRaisesRegex(offsite.OffsiteError, "Unsafe"):
            self.verified()
        self.meta.chmod(0o644)
        with self.assertRaisesRegex(offsite.OffsiteError, "Private"):
            self.verified()

    def test_invalid_pg_restore_catalog_blocks_upload(self):
        with mock.patch.object(offsite.subprocess, "run", return_value=mock.Mock(returncode=1)):
            with self.assertRaisesRegex(offsite.OffsiteError, "database archive"):
                offsite.verified_source(self.base, self.current, now=self.now)

    def test_budget_guard_prevents_upload_and_preserves_snapshot_history(self):
        files, stamp, sha, size = self.verified()
        client = FakeRestic(used=offsite.REPOSITORY_BUDGET_BYTES)
        with self.assertRaisesRegex(offsite.OffsiteError, "capacity"):
            offsite.upload_source(files, stamp, sha, size, client)
        self.assertEqual([call[0] for call in client.calls], ["snapshots", "stats"])

    def test_release_lock_blocks_parallel_offsite_job(self):
        lock_dir = self.root / "lock"
        with offsite.release_lock(lock_dir):
            with self.assertRaisesRegex(offsite.OffsiteError, "busy"):
                with offsite.release_lock(lock_dir):
                    self.fail("parallel job entered")
        with offsite.release_lock(lock_dir):
            pass

    def test_systemd_job_is_inactive_after_standard_release(self):
        activate = (ROOT / "scripts/release/activate-release.sh").read_text()
        self.assertNotIn("accounting-offsite.service", activate)
        self.assertNotIn("accounting-offsite.timer", activate)
        unit = (ROOT / "deploy/systemd/accounting-offsite.service").read_text()
        self.assertIn("ProtectSystem=strict", unit)
        self.assertIn("CacheDirectoryMode=0700", unit)
        self.assertIn("offsite_accounting.py", unit)
        self.assertIn("OnCalendar=*-*-* *:40:00", (ROOT / "deploy/systemd/accounting-offsite.timer").read_text())
