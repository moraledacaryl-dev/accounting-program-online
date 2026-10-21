#!/usr/bin/env python3
"""Validate a private restore-evidence archive BEFORE PostgreSQL restore.

Reject unsafe tar entries and ensure the expanded evidence has disk headroom.
Never log attachment names, source paths, or document contents.
"""
from __future__ import annotations

import shutil
import sys
import tarfile
from pathlib import Path, PurePosixPath

MAX_ARCHIVE_MEMBERS = 100000
FREE_SPACE_RESERVE_BYTES = 512 * 1024 * 1024


def inspect_archive(archive_path: str | Path) -> tuple[int, int]:
    """Return (regular-file count, expanded bytes) after strict member validation."""
    seen = set()
    files = 0
    expanded_bytes = 0
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        if len(members) > MAX_ARCHIVE_MEMBERS:
            raise ValueError("Evidence archive exceeds the safe member limit.")
        for member in members:
            name = member.name
            # Normal archives produced with -C uploads . contain a ./ root.
            if (
                not name
                or name.startswith("/")
                or "\\" in name
                or ".." in name.split("/")
                or not (member.isfile() or member.isdir())
            ):
                raise ValueError("Evidence archive contains an unsafe member.")
            normalized = str(PurePosixPath(name))
            if normalized == ".":
                if not member.isdir():
                    raise ValueError("Evidence archive has an invalid root entry.")
                continue
            if normalized in seen:
                raise ValueError("Evidence archive contains repeated destination paths.")
            seen.add(normalized)
            if member.isfile():
                files += 1
                expanded_bytes += member.size
    return files, expanded_bytes


def extract_verified(archive_path: str | Path, destination: str | Path) -> tuple[int, int]:
    """Extract regular files/dirs only, with a free-disk reserve and Python data filter."""
    destination = Path(destination)
    if not destination.is_dir() or destination.is_symlink():
        raise ValueError("Evidence destination must be a real directory.")
    counts = inspect_archive(archive_path)
    if shutil.disk_usage(destination).free < counts[1] + FREE_SPACE_RESERVE_BYTES:
        raise ValueError("Insufficient free space to extract restore evidence safely.")
    # Reopen after validation; Python tarfile data filter is an independent defense.
    # The source archive must stay in a protected, operator-owned directory.
    with tarfile.open(archive_path, "r:gz") as archive:
        archive.extractall(destination, filter="data")
    return counts


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: verify-restore-archive.py ARCHIVE DESTINATION", file=sys.stderr)
        return 2
    try:
        count, expanded_bytes = extract_verified(sys.argv[1], sys.argv[2])
    except (ValueError, OSError, tarfile.TarError) as exc:
        # Do not leak attachment paths or filenames into CI/workflow logs.
        print(f"Restore evidence preflight failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(f"RESTORE EVIDENCE PREFLIGHT: PASS | files={count} expanded_bytes={expanded_bytes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
