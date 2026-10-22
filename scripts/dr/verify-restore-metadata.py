#!/usr/bin/env python3
"""Fail-closed metadata preflight for an *isolated* Accounting restore rehearsal.

Reads a local backup and its sidecar; never opens a database or prints paths,
backup contents, financial identifiers or credentials.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REQUIRED = frozenset({
    "format", "created_utc", "database", "sha256", "size_bytes", "release_sha",
    "alembic_revision", "uploads_archive", "uploads_sha256",
})
HEX64 = re.compile(r"[0-9a-fA-F]{64}\Z")
STAMP = re.compile(r"[0-9]{8}T[0-9]{6}Z\Z")
MIGRATION = re.compile(r"[a-zA-Z0-9_]{1,32}\Z")


def validate_metadata(dump: Path, meta: Path) -> dict[str, str]:
    if meta.is_symlink() or not dump.is_file() or not meta.is_file():
        raise ValueError("Backup or sidecar is missing or unsafe.")
    if dump.parent.resolve() != meta.parent.resolve():
        raise ValueError("Backup and sidecar must be colocated.")
    if meta.name != dump.with_suffix(".meta").name or not dump.name.startswith("accounting-"):
        raise ValueError("Backup and sidecar names do not match.")
    parsed: dict[str, str] = {}
    for line in meta.read_text(encoding="utf-8").splitlines():
        if not line or "=" not in line:
            raise ValueError("Malformed metadata line.")
        key, value = line.split("=", 1)
        if key in parsed or key not in REQUIRED or not value or value.strip() != value:
            raise ValueError("Duplicate, unexpected or empty metadata field.")
        parsed[key] = value
    if set(parsed) != REQUIRED or parsed["format"] != "postgresql-custom":
        raise ValueError("Incomplete or unsupported backup manifest.")
    stamp = parsed["created_utc"]
    if not STAMP.fullmatch(stamp):
        raise ValueError("Invalid manifest timestamp.")
    if dump.name != f"accounting-{stamp}.dump":
        raise ValueError("Backup name and manifest timestamp mismatch.")
    if not HEX64.fullmatch(parsed["sha256"]) or not HEX64.fullmatch(parsed["uploads_sha256"]):
        raise ValueError("Invalid checksum shape.")
    if not parsed["size_bytes"].isdigit() or int(parsed["size_bytes"]) <= 0:
        raise ValueError("Invalid backup byte size.")
    if dump.stat().st_size != int(parsed["size_bytes"]):
        raise ValueError("Backup size differs from manifest.")
    expected_upload = f"accounting-{stamp}.uploads.tar.gz"
    if parsed["uploads_archive"] != expected_upload:
        raise ValueError("Evidence archive basename does not match backup.")
    if not MIGRATION.fullmatch(parsed["alembic_revision"]):
        raise ValueError("Invalid Alembic version.")
    if not parsed["database"].strip() or any(c.isspace() for c in parsed["database"]):
        raise ValueError("Invalid database name.")
    return parsed


def main() -> int:
    try:
        if len(sys.argv) != 3:
            raise ValueError("Expected a backup and manifest path.")
        validate_metadata(Path(sys.argv[1]), Path(sys.argv[2]))
        print("RESTORE METADATA PREFLIGHT: PASS")
        return 0
    except (ValueError, OSError, UnicodeError):
        print("RESTORE METADATA PREFLIGHT: NOT_CERTIFIED")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
