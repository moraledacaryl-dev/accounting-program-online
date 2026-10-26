#!/usr/bin/env python3
"""Fetch and verify the official Restic binary for isolated CI tests."""
import argparse
import bz2
import hashlib
import os
from pathlib import Path
import platform
import urllib.request


VERSION = "0.19.1"
DIGESTS = {
    ("Darwin", "arm64"): ("darwin_arm64", "7be0a144ccc377880f294204aa271d76e4b79554b42a751151d425ce6ebac143"),
    ("Linux", "x86_64"): ("linux_amd64", "f415415624dcc452f2a02b8c33641791a8c6d6d3b65bbb3543fcf9a25151585c"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    folder = args.directory
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not folder.is_absolute() or folder.is_symlink() or folder.stat().st_uid != os.geteuid() or folder.stat().st_mode & 0o077:
        parser.error("Private operator-owned directory required")
    target = folder / "restic"
    if target.exists() or target.is_symlink():
        parser.error("Destination exists; will not replace a binary")
    name, expected = DIGESTS[(platform.system(), platform.machine())]
    url = f"https://github.com/restic/restic/releases/download/v{VERSION}/restic_{VERSION}_{name}.bz2"
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read(32 * 1024**2 + 1)
    if len(data) > 32 * 1024**2 or hashlib.sha256(data).hexdigest() != expected:
        raise SystemExit("Official Restic release checksum mismatch")
    with target.open("xb") as output:
        output.write(bz2.decompress(data))
    target.chmod(0o700)
    print(f"ACCOUNTING RESTIC {VERSION}: CHECKSUM VERIFIED")


if __name__ == "__main__":
    main()
