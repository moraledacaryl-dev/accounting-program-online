#!/usr/bin/env python3
"""Exercise the approved policy in an actual disposable encrypted repository."""
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import subprocess
import tempfile

from offsite_accounting_retention import POLICY


def main():
    binary = Path(os.environ["ACCOUNTING_TEST_RESTIC_BINARY"])
    if not binary.is_file():
        raise SystemExit("Verified Restic binary required")
    with tempfile.TemporaryDirectory(prefix="accounting-restic-contract-") as scratch:
        root = Path(scratch)
        (root / "password").write_text("synthetic-only-restic-contract-password")
        source = root / "synthetic-only.txt"
        source.write_text("synthetic Accounting recovery marker")
        env = {"PATH": "/usr/bin:/bin", "HOME": str(root), "TZ": "UTC",
               "RESTIC_REPOSITORY": str(root / "repo"),
               "RESTIC_PASSWORD_FILE": str(root / "password"),
               "RESTIC_CACHE_DIR": str(root / "cache")}

        def run(*args):
            result = subprocess.run([str(binary), "--json", *args], env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, timeout=60, check=False)
            if result.returncode:
                raise RuntimeError("Synthetic Restic contract failed")
            return result.stdout

        run("init")
        recent = datetime.now(timezone.utc) - timedelta(minutes=5)
        run("backup", "--time", recent.strftime("%Y-%m-%d %H:%M:%S"),
            "--host", "hidden-oasis-accounting", "--tag", "scheduled",
            "--tag", "source:accounting-" + recent.strftime("%Y%m%dT%H%M%SZ"), "--", str(source))
        no_removal = json.loads(run("forget", "--dry-run", *POLICY))
        if len(no_removal) != 1 or no_removal[0].get("remove") is not None:
            raise RuntimeError("Synthetic single-snapshot retention shape changed")
        old = datetime.now(timezone.utc).replace(hour=2, minute=0, second=0, microsecond=0) - timedelta(days=55)
        for minute in range(6):
            when = old + timedelta(minutes=minute)
            stamp = when.strftime("%Y%m%dT%H%M%SZ")
            run("backup", "--time", when.strftime("%Y-%m-%d %H:%M:%S"),
                "--host", "hidden-oasis-accounting", "--tag", "scheduled",
                "--tag", "source:accounting-" + stamp, "--", str(source))
        before = json.loads(run("snapshots"))
        latest = max(before, key=lambda item: item["time"])["id"]
        groups = json.loads(run("forget", "--dry-run", *POLICY))
        if len(before) != 7 or len(groups) != 1 or not groups[0]["remove"]:
            raise RuntimeError("Synthetic retention dry run did not select old snapshots")
        if any(item["id"] == latest for item in groups[0]["remove"]):
            raise RuntimeError("Synthetic retention selected latest snapshot")
        run("forget", *POLICY, "--prune")
        run("check")
        after = json.loads(run("snapshots"))
        if len(after) >= len(before) or latest not in {item["id"] for item in after}:
            raise RuntimeError("Synthetic retention removed latest or failed to prune")
        run("restore", latest, "--target", str(root / "restored"))
        restored = root / "restored" / source.relative_to("/")
        if restored.read_text() != source.read_text():
            raise RuntimeError("Synthetic restored content differs")
    print("ACCOUNTING OFFSITE RESTIC RETENTION/RESTORE: PASS (synthetic only)")


if __name__ == "__main__":
    main()
