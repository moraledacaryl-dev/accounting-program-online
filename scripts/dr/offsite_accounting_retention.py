#!/usr/bin/env python3
"""Apply the owner-approved Accounting Restic history policy after a dry run."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from offsite_accounting import (
    OffsiteError, Restic, read_config, release_lock, verify_key_scope,
)


HOST = "hidden-oasis-accounting"
SOURCE = re.compile(r"source:accounting-[0-9]{8}T[0-9]{6}Z\Z")
ID = re.compile(r"[0-9a-f]{64}\Z")
POLICY = (
    "--host", HOST, "--tag", "scheduled", "--group-by", "host",
    "--keep-hourly", "48", "--keep-daily", "30", "--keep-weekly", "12",
    "--keep-monthly", "12", "--keep-within", "48h",
)


def _snapshot_time(item: dict) -> datetime:
    value = datetime.fromisoformat(item["time"].replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise OffsiteError("Accounting snapshot lacks timezone")
    return value.astimezone(timezone.utc)


def _validate_snapshots(items: list[dict], *, now: datetime) -> dict[str, dict]:
    if not isinstance(items, list) or not items:
        raise OffsiteError("Accounting repository has no snapshots")
    indexed = {}
    for item in items:
        if not isinstance(item, dict) or not ID.fullmatch(item.get("id", "")) or item.get("hostname") != HOST:
            raise OffsiteError("Unexpected Accounting repository snapshot")
        tags = item.get("tags")
        if not isinstance(tags, list) or "scheduled" not in tags or sum(bool(SOURCE.fullmatch(tag)) for tag in tags) != 1:
            raise OffsiteError("Unexpected Accounting repository snapshot tags")
        paths = item.get("paths")
        if not isinstance(paths, list) or len(paths) != 3 or not all(
            isinstance(path, str) and path.startswith("/var/backups/hiddenoasis/accounting/accounting-")
            for path in paths
        ):
            raise OffsiteError("Unexpected Accounting repository snapshot paths")
        stamp = next(tag.split(":", 1)[1] for tag in tags if SOURCE.fullmatch(tag))
        expected = {
            f"/var/backups/hiddenoasis/accounting/{stamp}.dump",
            f"/var/backups/hiddenoasis/accounting/{stamp}.uploads.tar.gz",
            f"/var/backups/hiddenoasis/accounting/{stamp}.meta",
        }
        if set(paths) != expected or item["id"] in indexed:
            raise OffsiteError("Unexpected Accounting repository source identity")
        _snapshot_time(item)
        indexed[item["id"]] = item
    age = (now - max(_snapshot_time(item) for item in items)).total_seconds()
    if not 0 <= age <= 2 * 3600:
        raise OffsiteError("Latest Accounting cloud snapshot is not fresh")
    return indexed


def retention_plan(client: Restic, *, now: datetime | None = None) -> tuple[dict[str, dict], set[str]]:
    current = now or datetime.now(timezone.utc)
    snapshots = _validate_snapshots(json.loads(client.run("snapshots")), now=current)
    client.run("check")
    groups = json.loads(client.run("forget", "--dry-run", *POLICY))
    if not isinstance(groups, list) or len(groups) != 1 or groups[0].get("host") != HOST:
        raise OffsiteError("Unexpected Accounting retention groups")
    group = groups[0]
    keep_items = group.get("keep")
    remove_items = group.get("remove")
    # Restic serializes an empty removal list as null in its JSON dry run.
    if remove_items is None:
        remove_items = []
    if not isinstance(keep_items, list) or not isinstance(remove_items, list) or not all(
        isinstance(item, dict) for item in (*keep_items, *remove_items)
    ):
        raise OffsiteError("Unexpected Accounting retention plan")
    kept = {item.get("id") for item in keep_items}
    removed = {item.get("id") for item in remove_items}
    if (not kept or None in kept or None in removed or kept & removed
            or kept | removed != set(snapshots)
            or len(kept) != len(keep_items)
            or len(removed) != len(remove_items)):
        raise OffsiteError("Accounting retention plan does not cover repository")
    if any((current - _snapshot_time(snapshots[identifier])).total_seconds() < 48 * 3600 for identifier in removed):
        raise OffsiteError("Accounting retention would remove a recent snapshot")
    return snapshots, removed


def apply_retention(client: Restic, *, now: datetime | None = None) -> int:
    _, removed = retention_plan(client, now=now)
    if removed:
        client.run("forget", *POLICY, "--prune")
        client.run("check")
    return len(removed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("/etc/hiddenoasis/accounting-offsite.json"))
    parser.add_argument("--apply", action="store_true", help="Apply the approved policy after validation")
    args = parser.parse_args()
    import os
    os.umask(0o077)
    if os.geteuid() != 0:
        parser.error("Run as the authorized backup operator")
    try:
        config = read_config(args.config)
        if not config["enabled"]:
            print('{"status":"disabled","cloud_requests_sent":false}')
            return 0
        if args.apply and config.get("initial_cloud_restore_verified") is not True:
            raise OffsiteError("Cloud restore gate incomplete")
        with release_lock(Path("/run/hiddenoasis-accounting-release")):
            verify_key_scope(config["keys"])
            client = Restic(Path("/usr/local/bin/restic"), config, Path("/var/cache/hiddenoasis-accounting-offsite"))
            if args.apply:
                count = apply_retention(client)
                print(json.dumps({"status": "pass", "mode": "apply", "snapshots_removed": count}))
            else:
                _, removed = retention_plan(client)
                print(json.dumps({"status": "pass", "mode": "dry_run", "planned_removals": len(removed)}))
        return 0
    except Exception:
        print('{"status":"failed","detail":"Inspect Accounting repository history, restore gate and capacity"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
