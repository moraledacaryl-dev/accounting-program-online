#!/usr/bin/env python3
"""Stage-only, read-only diagnosis of the active Accounting offsite job."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

ACTIVE_SCRIPT = Path("/opt/accounting-current/scripts/dr/offsite_accounting.py")
CONFIG = Path("/etc/hiddenoasis/accounting-offsite.json")
BACKUPS = Path("/var/backups/hiddenoasis/accounting")
CURRENT = Path("/opt/accounting-current")
CACHE = Path("/var/cache/hiddenoasis-accounting-offsite")
RESTIC = Path("/usr/local/bin/restic")


def diagnose(offsite: object) -> str:
    try:
        config = offsite.read_config(CONFIG)
        if not config.get("enabled"):
            return "config_disabled"
    except Exception:
        return "config_unverified"
    try:
        _files, _stamp, _sha, size = offsite.verified_source(BACKUPS, CURRENT)
    except Exception:
        return "source_unverified"
    try:
        offsite.verify_key_scope(config["keys"])
    except Exception:
        return "key_scope_unverified"
    try:
        client = offsite.Restic(RESTIC, config, CACHE)
        stats = json.loads(client.run("stats", "--mode", "raw-data"))
        used = stats.get("total_size")
        if type(used) is not int or used < 0:
            return "repository_stats_unverified"
        if used + size + 64 * 1024**2 > offsite.REPOSITORY_BUDGET_BYTES:
            return "repository_capacity_guard"
    except Exception:
        return "repository_read_unverified"
    return "preflight_pass"


def main() -> int:
    os.umask(0o077)
    try:
        if os.geteuid() != 0 or not ACTIVE_SCRIPT.is_file() or ACTIVE_SCRIPT.is_symlink():
            stage = "active_script_unverified"
        else:
            spec = importlib.util.spec_from_file_location("active_accounting_offsite", ACTIVE_SCRIPT)
            if spec is None or spec.loader is None:
                stage = "active_script_unverified"
            else:
                offsite = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(offsite)
                stage = diagnose(offsite)
    except Exception:
        stage = "active_script_unverified"
    # A fixed stage code is the only output. No exception text or private data.
    print(f"ACCOUNTING OFFSITE PREFLIGHT: {stage}")
    return 0 if stage == "preflight_pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
