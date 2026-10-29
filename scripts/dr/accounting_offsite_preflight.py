#!/usr/bin/env python3
"""Stage-only, read-only diagnosis of the active Accounting offsite job."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path

ACTIVE_SCRIPT = Path("/opt/accounting-current/scripts/dr/offsite_accounting.py")
CONFIG = Path("/etc/hiddenoasis/accounting-offsite.json")
BACKUPS = Path("/var/backups/hiddenoasis/accounting")
CURRENT = Path("/opt/accounting-current")
CACHE = Path("/var/cache/hiddenoasis-accounting-offsite")
RESTIC = Path("/usr/local/bin/restic")


def classify_restic_failure(stderr: bytes) -> str:
    """Map private command diagnostics to fixed, non-sensitive categories."""
    message = stderr[:8192].decode("utf-8", errors="replace").lower()
    if "locked" in message or "lock" in message:
        return "repository_lock"
    if "wrong password" in message or "no key found" in message:
        return "repository_password"
    if any(term in message for term in ("access denied", "unauthorized", "forbidden", "403")):
        return "repository_access"
    if any(term in message for term in ("timeout", "connection", "network", "temporary failure")):
        return "repository_network"
    if "not found" in message or "does not exist" in message:
        return "repository_missing"
    return "repository_command_failed"


def read_repository(client: object, size: int, budget: int) -> str:
    """Run read-only Restic commands without ever printing their output."""
    for args in (("snapshots",), ("stats", "--mode", "raw-data")):
        try:
            result = subprocess.run(
                [str(client.binary), "--json", *args], env=client.environment,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                check=False, timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired):
            return "repository_command_unavailable"
        if result.returncode:
            return classify_restic_failure(result.stderr)
        if len(result.stdout) > 1024**2:
            return "repository_output_unverified"
        if args[0] == "stats":
            try:
                used = json.loads(result.stdout).get("total_size")
            except (ValueError, AttributeError):
                return "repository_stats_unverified"
            if type(used) is not int or used < 0:
                return "repository_stats_unverified"
            if used + size + 64 * 1024**2 > budget:
                return "repository_capacity_guard"
    return "preflight_pass"


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
    except Exception:
        return "repository_client_unverified"
    return read_repository(client, size, offsite.REPOSITORY_BUDGET_BYTES)


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
