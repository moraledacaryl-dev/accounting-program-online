#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ] || [ "$(id -u)" -ne 0 ]; then
  echo "Usage (as root): $0 <prepared-release-directory>" >&2
  exit 2
fi

RELEASE="$1"
test -d "$RELEASE"
test ! -L "$RELEASE"
test -f "$RELEASE/frontend/.next/BUILD_ID"

# The deploy workflow uses umask 077. Allow the service group to traverse and
# read the immutable artifact, while keeping write access root-only.
chown -R root:hiddenoasis "$RELEASE"
chmod -R g+rX,go-w,o-rwx "$RELEASE"

# Next.js image optimization has one deliberately writable cache directory.
install -d -o hiddenoasis -g hiddenoasis -m 0750 "$RELEASE/frontend/.next/cache/images"
test "$(stat -c '%U:%G' "$RELEASE/frontend/.next/cache/images")" = "hiddenoasis:hiddenoasis"
runuser -u hiddenoasis -- test -r "$RELEASE/frontend/.next/BUILD_ID"
runuser -u hiddenoasis -- test -w "$RELEASE/frontend/.next/cache/images"
