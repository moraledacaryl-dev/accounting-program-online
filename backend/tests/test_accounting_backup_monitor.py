"""Synthetic, disposable checks for read-only backup monitoring failures."""

import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "dr" / "accounting_backup_monitor.py"
spec = importlib.util.spec_from_file_location("accounting_backup_monitor", SCRIPT)
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


def write_set(base: Path, now: datetime):
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    dump = base / f"accounting-{stamp}.dump"
    uploads = base / f"accounting-{stamp}.uploads.tar.gz"
    dump.write_bytes(b"synthetic postgres custom dump")
    uploads.write_bytes(b"synthetic uploads archive")
    meta = base / f"accounting-{stamp}.meta"
    meta.write_text("\n".join([
        "format=postgresql-custom", f"created_utc={stamp}", "database=synthetic",
        f"sha256={hashlib.sha256(dump.read_bytes()).hexdigest()}",
        f"size_bytes={dump.stat().st_size}", "release_sha=" + "a" * 40,
        "alembic_revision=0017_journal_linkage_review",
        f"uploads_archive={uploads.name}",
        f"uploads_sha256={hashlib.sha256(uploads.read_bytes()).hexdigest()}",
    ]) + "\n")
    return dump, uploads, meta


def healthy_output(*args):
    if args[:2] == ("systemctl", "is-active"):
        return "active"
    if args[:2] == ("systemctl", "is-enabled"):
        return "enabled"
    if "Result" in args:
        return "success"
    if "ExecMainStatus" in args:
        return "0"
    if args[0] == "journalctl":
        return journal_entry({"status": "pass", "mode": "apply"}, datetime.now(timezone.utc))
    raise AssertionError(args)


def journal_entry(message: dict, when: datetime) -> str:
    return json.dumps({
        "MESSAGE": json.dumps(message),
        "__REALTIME_TIMESTAMP": str(int(when.timestamp() * 1_000_000)),
    })


class AccountingBackupMonitorTests(unittest.TestCase):
    def test_failure_codes_are_fixed_and_do_not_expose_exception_content(self):
        for message, expected in (
            ("No recent encrypted Accounting offsite success", "offsite_recent_success"),
            ("sensitive /private/path", "runtime_or_metadata"),
        ):
            with self.subTest(expected=expected), patch.object(
                monitor, "verify_latest_backup", side_effect=ValueError(message)
            ):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(monitor.main(), 2)
                self.assertIn(f"failure_code={expected}", output.getvalue())
                self.assertNotIn(message, output.getvalue())

    def test_recent_backup_set_checks_both_checksums(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        with tempfile.TemporaryDirectory() as scratch:
            base = Path(scratch)
            _, uploads, _ = write_set(base, now)
            self.assertEqual(monitor.verify_latest_backup(base, now), (0, 1))
            uploads.write_bytes(b"changed archive")
            with self.assertRaisesRegex(ValueError, "checksum"):
                monitor.verify_latest_backup(base, now)

    def test_stale_backup_is_rejected(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        with tempfile.TemporaryDirectory() as scratch:
            base = Path(scratch)
            write_set(base, now - timedelta(hours=4))
            with self.assertRaisesRegex(ValueError, "fresh"):
                monitor.verify_latest_backup(base, now)

    def test_runtime_requires_recent_offsite_success(self):
        def output(*args):
            if args[0] == "journalctl":
                return journal_entry({"status": "failed"}, datetime.now(timezone.utc))
            return healthy_output(*args)
        with patch.object(monitor, "_output", output):
            with self.assertRaisesRegex(ValueError, "offsite"):
                monitor.check_runtime()

    def test_inactive_timer_is_rejected(self):
        def output(*args):
            if args[:2] == ("systemctl", "is-active") and args[2] == "accounting-offsite.timer":
                return "inactive"
            return healthy_output(*args)
        with patch.object(monitor, "_output", output):
            with self.assertRaisesRegex(ValueError, "inactive"):
                monitor.check_runtime()

    def test_failed_service_result_identifies_only_the_service(self):
        def output(*args):
            if args[:5] == ("systemctl", "show", "-p", "Result", "--value") and args[5] == "accounting-offsite.service":
                return "exit-code"
            return healthy_output(*args)
        with patch.object(monitor, "_output", output):
            with self.assertRaisesRegex(ValueError, "Offsite backup service last result"):
                monitor.check_runtime()
        self.assertEqual(
            monitor.SAFE_FAILURE_CODES["Offsite backup service last result is not success"],
            "offsite_service_result",
        )

    def test_retention_dry_run_does_not_count_as_apply(self):
        def output(*args):
            if args[0] == "journalctl" and "retention" in args[2]:
                return journal_entry({"status": "pass", "mode": "dry_run"}, datetime.now(timezone.utc))
            return healthy_output(*args)
        with patch.object(monitor, "_output", output):
            self.assertEqual(monitor.check_runtime(), (True, False))

    def test_first_scheduled_retention_window_has_a_grace_period(self):
        due = monitor.FIRST_RETENTION_DUE_UTC
        self.assertFalse(monitor.retention_evidence_required(due + timedelta(hours=2)))
        self.assertTrue(monitor.retention_evidence_required(due + timedelta(hours=3)))

    def test_manual_retention_before_first_schedule_is_not_certified(self):
        prior_apply = journal_entry(
            {"status": "pass", "mode": "apply"},
            monitor.FIRST_RETENTION_DUE_UTC - timedelta(days=1),
        )
        with patch.object(monitor, "_output", return_value=prior_apply):
            self.assertFalse(monitor._recent_pass(
                "accounting-offsite-retention.service", hours=8 * 24,
                not_before=monitor.FIRST_RETENTION_DUE_UTC,
            ))


if __name__ == "__main__":
    unittest.main()
