#!/usr/bin/env python3
"""Upload one verified Accounting backup set to a private Restic repository.

The job is operator-gated and never initializes, forgets, prunes or deletes a
repository. It is not installed or enabled by the application release process.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tarfile
from urllib.request import Request, urlopen


REPOSITORY = (
    "s3:https://s3.us-west-004.backblazeb2.com/"
    "hidden-oasis-accounting-backups-20261026/accounting"
)
MAX_SOURCE_BYTES = 256 * 1024**2
REPOSITORY_BUDGET_BYTES = 8 * 1000**3
MAX_AGE_SECONDS = 90 * 60
STAMP = re.compile(r"accounting-([0-9]{8}T[0-9]{6}Z)\.meta\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
RESTIC_ID = re.compile(r"[0-9a-f]{64}\Z")


class OffsiteError(Exception):
    pass


def private_file(path: Path) -> Path:
    if not path.is_absolute() or path.is_symlink():
        raise OffsiteError("Private operator file required")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise OffsiteError("Private operator file required")
    parent = path.parent
    if parent.is_symlink() or parent.stat().st_mode & 0o022:
        raise OffsiteError("Untrusted private-file directory")
    return path


def read_config(path: Path) -> dict:
    if not path.exists():
        return {"enabled": False}
    private_file(path)
    if path.stat().st_size > 8192:
        raise OffsiteError("Invalid offsite configuration")
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("enabled") is not True:
        return {"enabled": False}
    if any(config.get(flag) is not True for flag in (
        "account_caps_verified", "recovery_key_custody_confirmed", "retention_policy_approved"
    )):
        raise OffsiteError("Offsite activation gates incomplete")
    if config.get("repository") != REPOSITORY:
        raise OffsiteError("Unexpected offsite repository")
    password = private_file(Path(config.get("password_file", "")))
    credentials = private_file(Path(config.get("credentials_file", "")))
    if not 32 <= password.stat().st_size <= 4096 or credentials.stat().st_size > 4096:
        raise OffsiteError("Invalid offsite secret file")
    keys = json.loads(credentials.read_text(encoding="utf-8"))
    if set(keys) != {"access_key_id", "secret_access_key"} or any(
        not isinstance(keys[name], str) or not keys[name].strip() or keys[name].startswith("ENTER_")
        for name in ("access_key_id", "secret_access_key")
    ):
        raise OffsiteError("Offsite credentials not installed")
    return {**config, "password_file": str(password), "keys": keys}


def verify_key_scope(keys: dict) -> None:
    """Reject a rotated key with broader access before touching the repository."""
    basic = base64.b64encode((keys["access_key_id"] + ":" + keys["secret_access_key"]).encode()).decode()
    request = Request(
        "https://api.backblazeb2.com/b2api/v3/b2_authorize_account",
        headers={"Authorization": "Basic " + basic},
    )
    with urlopen(request, timeout=15) as response:
        payload = response.read(16385)
    if len(payload) > 16384:
        raise OffsiteError("Invalid Backblaze authorization response")
    scope = json.loads(payload)["apiInfo"]["storageApi"]
    capabilities = set(scope["capabilities"])
    if (scope.get("bucketName") != "hidden-oasis-accounting-backups-20261026"
            or scope.get("namePrefix") != "accounting/"
            or scope.get("s3ApiUrl", "").rstrip("/") != "https://s3.us-west-004.backblazeb2.com"
            or not {"listFiles", "readFiles", "writeFiles", "deleteFiles"} <= capabilities
            or {"listAllBucketNames", "deleteBuckets", "listKeys", "writeKeys"} & capabilities):
        raise OffsiteError("Backblaze key scope does not match Accounting")


@contextmanager
def release_lock(directory: Path):
    if not directory.is_absolute() or directory.is_symlink():
        raise OffsiteError("Invalid Accounting release lock directory")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = directory.stat()
    if info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise OffsiteError("Accounting release lock directory is not private")
    lock = directory / "deployment.lock"
    descriptor = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        if os.fstat(descriptor).st_uid != os.geteuid():
            raise OffsiteError("Unsafe Accounting release lock")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise OffsiteError("Accounting release or backup is busy") from exc
        yield
    finally:
        os.close(descriptor)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verified_source(base: Path, current: Path, *, now: datetime | None = None) -> tuple[tuple[Path, ...], str, str, int]:
    if base.is_symlink() or not base.is_dir() or base.stat().st_uid != os.geteuid() or base.stat().st_mode & 0o077:
        raise OffsiteError("Private Accounting backup directory required")
    if not current.is_symlink():
        raise OffsiteError("Active Accounting release symlink required")
    active_sha = current.resolve(strict=True).name
    if not SHA.fullmatch(active_sha):
        raise OffsiteError("Invalid active Accounting release")
    metas = sorted(base.glob("accounting-*.meta"))
    if not metas:
        raise OffsiteError("No Accounting backup sidecar available")
    meta = private_file(metas[-1])
    match = STAMP.fullmatch(meta.name)
    if not match:
        raise OffsiteError("Invalid Accounting backup name")
    stamp = match.group(1)
    created = datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    age = ((now or datetime.now(timezone.utc)) - created).total_seconds()
    if not 0 <= age <= MAX_AGE_SECONDS:
        raise OffsiteError("Accounting backup is not fresh")
    prefix = base / f"accounting-{stamp}"
    dump = private_file(Path(str(prefix) + ".dump"))
    uploads = private_file(Path(str(prefix) + ".uploads.tar.gz"))
    files = (dump, uploads, meta)
    total = sum(path.stat().st_size for path in files)
    if total <= 0 or total > MAX_SOURCE_BYTES or meta.stat().st_size > 4096:
        raise OffsiteError("Unexpected Accounting backup size")
    fields: dict[str, str] = {}
    for line in meta.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            raise OffsiteError("Malformed Accounting backup sidecar")
        key, value = line.split("=", 1)
        if key in fields or not value:
            raise OffsiteError("Malformed Accounting backup sidecar")
        fields[key] = value
    if fields != {
        "format": "postgresql-custom", "created_utc": stamp,
        "database": fields.get("database"), "sha256": fields.get("sha256"),
        "size_bytes": fields.get("size_bytes"), "release_sha": active_sha,
        "alembic_revision": fields.get("alembic_revision"),
        "uploads_archive": uploads.name, "uploads_sha256": fields.get("uploads_sha256"),
    }:
        raise OffsiteError("Accounting backup sidecar does not match active release")
    if not fields["size_bytes"].isdigit() or int(fields["size_bytes"]) != dump.stat().st_size:
        raise OffsiteError("Accounting dump size mismatch")
    if _sha256(dump) != fields["sha256"] or _sha256(uploads) != fields["uploads_sha256"]:
        raise OffsiteError("Accounting backup checksum mismatch")
    with tarfile.open(uploads, "r:gz") as archive:
        for index, item in enumerate(archive):
            name = PurePosixPath(item.name)
            if index >= 100000 or item.name.startswith("/") or ".." in name.parts or not (item.isfile() or item.isdir()):
                raise OffsiteError("Unsafe Accounting uploads archive")
    result = subprocess.run(["pg_restore", "--list", str(dump)], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, timeout=60, check=False)
    if result.returncode:
        raise OffsiteError("Invalid Accounting database archive")
    return files, stamp, active_sha, total


class Restic:
    def __init__(self, binary: Path, config: dict, cache: Path):
        info = binary.stat()
        if not binary.is_absolute() or binary.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o022:
            raise OffsiteError("Trusted operator-installed Restic binary required")
        cache.mkdir(mode=0o700, parents=True, exist_ok=True)
        if cache.is_symlink() or cache.stat().st_uid != os.geteuid() or cache.stat().st_mode & 0o077:
            raise OffsiteError("Private Restic cache required")
        self.binary = binary
        self.environment = {
            "PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(cache), "RESTIC_CACHE_DIR": str(cache),
            "RESTIC_REPOSITORY": config["repository"], "RESTIC_PASSWORD_FILE": config["password_file"],
            "AWS_ACCESS_KEY_ID": config["keys"]["access_key_id"],
            "AWS_SECRET_ACCESS_KEY": config["keys"]["secret_access_key"],
        }

    def run(self, *args: str) -> bytes:
        result = subprocess.run([str(self.binary), "--json", *args], env=self.environment,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=1800, check=False)
        if result.returncode or len(result.stdout) > 1024**2:
            raise OffsiteError("Encrypted Accounting repository command failed")
        return result.stdout


def upload_source(files: tuple[Path, ...], stamp: str, sha: str, size: int, client: Restic) -> None:
    tag = "source:accounting-" + stamp
    existing = json.loads(client.run("snapshots", "--tag", tag))
    if existing:
        if len(existing) != 1 or not RESTIC_ID.fullmatch(existing[0].get("id", "")):
            raise OffsiteError("Unexpected Accounting repository snapshot identity")
    else:
        usage = json.loads(client.run("stats", "--mode", "raw-data"))
        used = usage.get("total_size")
        if type(used) is not int or used < 0 or used + size + 64 * 1024**2 > REPOSITORY_BUDGET_BYTES:
            raise OffsiteError("Offsite repository capacity guard reached")
        output = client.run("backup", "--host", "hidden-oasis-accounting", "--tag", "scheduled",
                            "--tag", "release:" + sha, "--tag", tag, "--", *(str(path) for path in files))
        summaries = [item for line in output.splitlines() if (item := json.loads(line)).get("message_type") == "summary"]
        if not summaries or not RESTIC_ID.fullmatch(summaries[-1].get("snapshot_id", "")):
            raise OffsiteError("Encrypted Accounting upload completion not verified")
    client.run("check")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("/etc/hiddenoasis/accounting-offsite.json"))
    args = parser.parse_args()
    os.umask(0o077)
    if os.geteuid() != 0:
        parser.error("Run as the authorized backup operator")
    try:
        config = read_config(args.config)
        if not config["enabled"]:
            print('{"status":"disabled","cloud_requests_sent":false}')
            return 0
        with release_lock(Path("/run/hiddenoasis-accounting-release")):
            files, stamp, sha, size = verified_source(
                Path("/var/backups/hiddenoasis/accounting"), Path("/opt/accounting-current")
            )
            verify_key_scope(config["keys"])
            client = Restic(Path("/usr/local/bin/restic"), config, Path("/var/cache/hiddenoasis-accounting-offsite"))
            upload_source(files, stamp, sha, size, client)
        print('{"status":"pass","repository_metadata_verified":true,"archives_deleted":false}')
        return 0
    except Exception:
        print('{"status":"failed","detail":"Inspect source integrity, private credentials, account capacity and repository health"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
