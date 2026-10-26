"""Deletion-policy guards over a synthetic Accounting-only repository."""
from datetime import datetime, timezone, timedelta
import importlib.util
import json
from pathlib import Path
import sys
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/dr"))
spec = importlib.util.spec_from_file_location("accounting_retention", ROOT / "scripts/dr/offsite_accounting_retention.py")
retention = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retention)


def snapshot(stamp: str, when: datetime, identifier: str) -> dict:
    prefix = f"/var/backups/hiddenoasis/accounting/accounting-{stamp}"
    return {
        "id": identifier, "hostname": retention.HOST,
        "tags": ["scheduled", "release:" + "c" * 40, "source:accounting-" + stamp],
        "paths": [prefix + ".dump", prefix + ".uploads.tar.gz", prefix + ".meta"],
        "time": when.isoformat(),
    }


class FakeClient:
    def __init__(self, snapshots, *, remove, null_empty_removal=False):
        self.snapshots = snapshots
        self.remove = remove
        self.null_empty_removal = null_empty_removal
        self.calls = []

    def run(self, *args):
        self.calls.append(args)
        if args[0] == "snapshots":
            return json.dumps(self.snapshots).encode()
        if args[0] == "check":
            return b"{}"
        if args[0] == "forget" and "--dry-run" in args:
            removed = [x for x in self.snapshots if x["id"] in self.remove]
            return json.dumps([{"host": retention.HOST,
                                "keep": [x for x in self.snapshots if x["id"] not in self.remove],
                                "remove": None if self.null_empty_removal and not removed else removed}]).encode()
        if args[0] == "forget" and "--prune" in args:
            return b"{}"
        raise AssertionError(args)


class AccountingRetentionContract(TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 26, 4, 50, tzinfo=timezone.utc)
        self.recent = snapshot("20261026T043000Z", self.now - timedelta(minutes=20), "a" * 64)
        self.old = snapshot("20261020T043000Z", self.now - timedelta(days=6), "b" * 64)

    def test_policy_groups_by_host_and_protects_recent_points(self):
        client = FakeClient([self.recent, self.old], remove={self.old["id"]})
        self.assertEqual(retention.apply_retention(client, now=self.now), 1)
        dry = next(call for call in client.calls if call[0] == "forget" and "--dry-run" in call)
        self.assertEqual(dry[dry.index("--group-by") + 1], "host")
        for option, value in (("--keep-hourly", "48"), ("--keep-daily", "30"),
                              ("--keep-weekly", "12"), ("--keep-monthly", "12"),
                              ("--keep-within", "48h")):
            self.assertEqual(dry[dry.index(option) + 1], value)
        self.assertEqual([x[0] for x in client.calls], ["snapshots", "check", "forget", "forget", "check"])

    def test_dry_run_never_deletes_and_rejects_recent_removal(self):
        client = FakeClient([self.recent, self.old], remove={self.old["id"]})
        _, planned = retention.retention_plan(client, now=self.now)
        self.assertEqual(planned, {self.old["id"]})
        self.assertFalse(any("--prune" in call for call in client.calls))
        unsafe = FakeClient([self.recent, self.old], remove={self.recent["id"]})
        with self.assertRaisesRegex(retention.OffsiteError, "recent"):
            retention.apply_retention(unsafe, now=self.now)
        self.assertFalse(any("--prune" in call for call in unsafe.calls))

    def test_unknown_snapshot_or_stale_cloud_copy_blocks_prune(self):
        foreign = {**self.recent, "hostname": "unknown"}
        for items in ([foreign], [self.old]):
            client = FakeClient(items, remove=set())
            with self.assertRaises(retention.OffsiteError):
                retention.apply_retention(client, now=self.now)
            self.assertEqual([x[0] for x in client.calls], ["snapshots"])

    def test_restic_null_empty_removal_is_safe_noop(self):
        client = FakeClient([self.recent], remove=set(), null_empty_removal=True)
        self.assertEqual(retention.apply_retention(client, now=self.now), 0)
        self.assertEqual([x[0] for x in client.calls], ["snapshots", "check", "forget"])
