#!/usr/bin/env python3
"""Stage-only, read-only diagnosis of the active Accounting offsite job."""

from __future__ import annotations

import importlib.util
import base64
import json
import os
import re
import subprocess
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

ACTIVE_SCRIPT = Path("/opt/accounting-current/scripts/dr/offsite_accounting.py")
CONFIG = Path("/etc/hiddenoasis/accounting-offsite.json")
BACKUPS = Path("/var/backups/hiddenoasis/accounting")
CURRENT = Path("/opt/accounting-current")
CACHE = Path("/var/cache/hiddenoasis-accounting-offsite")
RESTIC = Path("/usr/local/bin/restic")
API_URL = re.compile(r"https://api[0-9]+\.backblazeb2\.com\Z")
DOWNLOAD_URL = re.compile(r"https://f[0-9]+\.backblazeb2\.com\Z")
BUCKET_NAME = "hidden-oasis-accounting-backups-20261026"


def native_repository_has_objects(keys: dict[str, str]) -> bool:
    """Read at most one object name through B2 Native API; never return it."""
    basic = base64.b64encode(
        (keys["access_key_id"] + ":" + keys["secret_access_key"]).encode()
    ).decode()
    authorize = Request(
        "https://api.backblazeb2.com/b2api/v3/b2_authorize_account",
        headers={"Authorization": "Basic " + basic},
    )
    with urlopen(authorize, timeout=15) as response:
        payload = response.read(16385)
    if len(payload) > 16384:
        raise ValueError("B2 authorization response too large")
    authorization = json.loads(payload)
    scope = authorization["apiInfo"]["storageApi"]
    base = scope["apiUrl"].rstrip("/")
    bucket = scope["bucketId"]
    if not API_URL.fullmatch(base) or not isinstance(bucket, str) or not re.fullmatch(r"[0-9a-f]{24}", bucket):
        raise ValueError("Unexpected B2 bucket identity")
    query = urlencode({"bucketId": bucket, "prefix": "accounting/", "maxFileCount": 1})
    request = Request(
        base + "/b2api/v3/b2_list_file_names?" + query,
        headers={"Authorization": authorization["authorizationToken"]},
    )
    with urlopen(request, timeout=15) as response:
        body = response.read(16385)
    if len(body) > 16384:
        raise ValueError("B2 listing response too large")
    files = json.loads(body)["files"]
    if not isinstance(files, list) or len(files) > 1:
        raise ValueError("Unexpected B2 listing response")
    return len(files) == 1


def native_config_read(keys: dict[str, str]) -> str:
    """Check only the small Restic config object through B2 Native API."""
    basic = base64.b64encode(
        (keys["access_key_id"] + ":" + keys["secret_access_key"]).encode()
    ).decode()
    authorize = Request(
        "https://api.backblazeb2.com/b2api/v3/b2_authorize_account",
        headers={"Authorization": "Basic " + basic},
    )
    try:
        with urlopen(authorize, timeout=15) as response:
            payload = response.read(16385)
        if len(payload) > 16384:
            return "native_config_read_unverified"
        authorization = json.loads(payload)
        scope = authorization["apiInfo"]["storageApi"]
        base = scope["downloadUrl"].rstrip("/")
        if not DOWNLOAD_URL.fullmatch(base) or scope["bucketName"] != BUCKET_NAME:
            return "native_config_read_unverified"
        request = Request(
            base + "/file/" + quote(BUCKET_NAME) + "/accounting/config",
            headers={"Authorization": authorization["authorizationToken"]},
        )
        with urlopen(request, timeout=15) as response:
            body = response.read(4097)
        if not body or len(body) > 4096:
            return "native_config_read_unverified"
    except HTTPError as exc:
        if exc.code == 403:
            return "native_config_access_denied"
        if exc.code == 404:
            return "native_config_missing"
        return "native_config_read_unverified"
    except Exception:
        return "native_config_read_unverified"
    return "native_config_read_pass"


def classify_restic_failure(stderr: bytes) -> str:
    """Map private command diagnostics to fixed, non-sensitive categories."""
    message = stderr[:8192].decode("utf-8", errors="replace").lower()
    if "locked" in message or "lock" in message:
        return "repository_lock"
    if "wrong password" in message or "no key found" in message:
        return "repository_password"
    if any(term in message for term in ("access denied", "unauthorized", "forbidden", "403")):
        if "listobjects" in message or "list objects" in message:
            return "repository_access_object_list"
        if "listbuckets" in message or "list buckets" in message:
            return "repository_access_bucket_list"
        if "headobject" in message or "stat:" in message:
            return "repository_access_object_read"
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
        if not native_repository_has_objects(config["keys"]):
            return "native_repository_empty"
    except Exception:
        return "native_repository_list_unverified"
    native_stage = native_config_read(config["keys"])
    if native_stage != "native_config_read_pass":
        return native_stage
    try:
        client = offsite.Restic(RESTIC, config, CACHE)
    except Exception:
        return "repository_client_unverified"
    stage = read_repository(client, size, offsite.REPOSITORY_BUDGET_BYTES)
    if stage.startswith("repository_access"):
        return stage + "_native_config_pass"
    return stage


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
