#!/usr/bin/env python3
"""Read-only Accounting backup and timer health check; emits aggregates only."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKUP_DIR = Path("/var/backups/hiddenoasis/accounting")
MAX_BACKUP_AGE_SECONDS = 3 * 60 * 60
MIN_FREE_BYTES = 4 * 1024**3
# The weekly timer was enabled after its October 26 window; the first due
# Monday window is November 2 at 04:50 Manila (November 1 at 20:50 UTC).
FIRST_RETENTION_DUE_UTC = datetime(2026, 11, 1, 20, 50, tzinfo=timezone.utc)
TIMERS = (
    "accounting-backup.timer",
    "accounting-offsite.timer",
    "accounting-offsite-retention.timer",
)
STAMP = re.compile(r"accounting-([0-9]{8}T[0-9]{6}Z)\.meta\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
REQUIRED_FIELDS = frozenset({
    "format", "created_utc", "database", "sha256", "size_bytes",
    "release_sha", "alembic_revision", "uploads_archive", "uploads_sha256",
})
SAFE_FAILURE_CODES = {
    "Backup directory is missing or unsafe": "backup_directory",
    "No completed Accounting backup manifest": "backup_manifest_missing",
    "Unexpected Accounting backup manifest": "backup_manifest_unsafe",
    "Latest Accounting backup is not fresh": "backup_stale",
    "Malformed Accounting backup manifest": "backup_manifest_malformed",
    "Accounting backup set is missing or unsafe": "backup_set_missing",
    "Accounting backup set is empty": "backup_set_empty",
    "Accounting backup manifest does not match files": "backup_manifest_mismatch",
    "Accounting backup checksum mismatch": "backup_checksum",
    "Required Accounting timer is inactive": "timer_inactive",
    "Required Accounting timer is disabled": "timer_disabled",
    "Accounting backup service last result is not success": "service_result",
    "Accounting backup service last exit is not zero": "service_exit",
    "No recent encrypted Accounting offsite success": "offsite_recent_success",
    "Accounting backup filesystem is below release threshold": "disk_free",
    "Scheduled Accounting offsite retention has no recent successful apply": "retention_apply",
}


def _output(*args: str) -> str:
    result = subprocess.run(args, capture_output=True, text=True, check=True, timeout=30)
    return result.stdout.strip()


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_latest_backup(base: Path, now: datetime) -> tuple[int, int]:
    if not base.is_dir() or base.is_symlink():
        raise ValueError("Backup directory is missing or unsafe")
    manifests = sorted(base.glob("accounting-*.meta"))
    if not manifests:
        raise ValueError("No completed Accounting backup manifest")
    manifest = manifests[-1]
    match = STAMP.fullmatch(manifest.name)
    if not match or manifest.is_symlink():
        raise ValueError("Unexpected Accounting backup manifest")
    stamp = match.group(1)
    created = datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    age = int((now - created).total_seconds())
    if age < 0 or age > MAX_BACKUP_AGE_SECONDS:
        raise ValueError("Latest Accounting backup is not fresh")
    fields: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if line.count("=") != 1:
            raise ValueError("Malformed Accounting backup manifest")
        key, value = line.split("=", 1)
        if not key or not value or key in fields:
            raise ValueError("Malformed Accounting backup manifest")
        fields[key] = value
    dump = base / f"accounting-{stamp}.dump"
    uploads = base / f"accounting-{stamp}.uploads.tar.gz"
    if any(item.is_symlink() or not item.is_file() for item in (dump, uploads)):
        raise ValueError("Accounting backup set is missing or unsafe")
    if dump.stat().st_size <= 0 or uploads.stat().st_size <= 0:
        raise ValueError("Accounting backup set is empty")
    if (set(fields) != REQUIRED_FIELDS
        or fields.get("created_utc") != stamp
        or fields.get("uploads_archive") != uploads.name
        or fields.get("format") != "postgresql-custom"
        or not HEX64.fullmatch(fields.get("sha256", ""))
        or not HEX64.fullmatch(fields.get("uploads_sha256", ""))
        or fields.get("size_bytes") != str(dump.stat().st_size)):
        raise ValueError("Accounting backup manifest does not match files")
    if _hash(dump) != fields["sha256"] or _hash(uploads) != fields["uploads_sha256"]:
        raise ValueError("Accounting backup checksum mismatch")
    return age, len(manifests)


def _recent_pass(service: str, *, hours: int, not_before: datetime | None = None) -> bool:
    output = _output("journalctl", "-u", service, "--since", f"{hours} hours ago", "-o", "json", "--no-pager")
    for line in output.splitlines():
        try:
            entry = json.loads(line)
            item = json.loads(entry["MESSAGE"])
            recorded = datetime.fromtimestamp(int(entry["__REALTIME_TIMESTAMP"]) / 1_000_000, timezone.utc)
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if not_before is not None and recorded < not_before:
            continue
        if isinstance(item, dict) and item.get("status") == "pass":
            if service == "accounting-offsite-retention.service" and item.get("mode") != "apply":
                continue
            return True
    return False


def check_runtime() -> tuple[bool, bool]:
    for timer in TIMERS:
        if _output("systemctl", "is-active", timer) != "active":
            raise ValueError("Required Accounting timer is inactive")
        if _output("systemctl", "is-enabled", timer) != "enabled":
            raise ValueError("Required Accounting timer is disabled")
    for service in ("accounting-backup.service", "accounting-offsite.service"):
        if _output("systemctl", "show", "-p", "Result", "--value", service) != "success":
            raise ValueError("Accounting backup service last result is not success")
        if _output("systemctl", "show", "-p", "ExecMainStatus", "--value", service) != "0":
            raise ValueError("Accounting backup service last exit is not zero")
    if not _recent_pass("accounting-offsite.service", hours=3):
        raise ValueError("No recent encrypted Accounting offsite success")
    return True, _recent_pass(
        "accounting-offsite-retention.service", hours=8 * 24,
        not_before=FIRST_RETENTION_DUE_UTC,
    )


def retention_evidence_required(now: datetime) -> bool:
    return now >= FIRST_RETENTION_DUE_UTC + timedelta(hours=3)


def main() -> int:
    try:
        now = datetime.now(timezone.utc)
        age, sets = verify_latest_backup(BACKUP_DIR, now)
        free = shutil.disk_usage(BACKUP_DIR).free
        if free < MIN_FREE_BYTES:
            raise ValueError("Accounting backup filesystem is below release threshold")
        _, retention_observed = check_runtime()
        if retention_evidence_required(now) and not retention_observed:
            raise ValueError("Scheduled Accounting offsite retention has no recent successful apply")
        print(f"ACCOUNTING BACKUP MONITOR: latest_backup_age_minutes={age // 60}")
        print(f"ACCOUNTING BACKUP MONITOR: local_completed_sets={sets}")
        print(f"ACCOUNTING BACKUP MONITOR: disk_free_gib={free / 1024**3:.1f}")
        print("ACCOUNTING BACKUP MONITOR: local_checksums=PASS")
        print("ACCOUNTING BACKUP MONITOR: hourly_timers=ACTIVE")
        print("ACCOUNTING BACKUP MONITOR: recent_offsite_upload=PASS")
        print(f"ACCOUNTING BACKUP MONITOR: weekly_retention_run_observed={'YES' if retention_observed else 'NO'}")
        print("ACCOUNTING BACKUP MONITOR: EXECUTION PASS")
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        # Only fixed, reviewed codes leave the server; never print exception text,
        # backup paths, business data, credentials or journal messages.
        code = SAFE_FAILURE_CODES.get(str(exc), "runtime_or_metadata") if isinstance(exc, ValueError) else "runtime_or_metadata"
        print(f"ACCOUNTING BACKUP MONITOR: NOT_CERTIFIED; failure_code={code}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
