#!/usr/bin/env bash
set -euo pipefail

test "$(id -u)" -eq 0
getent group hiddenoasis >/dev/null || groupadd --system hiddenoasis
id hiddenoasis >/dev/null 2>&1 || useradd --system --no-create-home --gid hiddenoasis hiddenoasis

scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT
chmod 755 "$scratch"
release="$scratch/release"
umask 077
mkdir -p "$release/frontend/.next/cache/images" "$release/frontend/node_modules/.bin" "$release/backend/.venv/bin"
printf 'synthetic-build\n' > "$release/frontend/.next/BUILD_ID"
printf 'synthetic-backend\n' > "$release/backend/app.py"
printf '#!/bin/sh\nexit 0\n' > "$release/backend/.venv/bin/python"
printf '#!/bin/sh\nexit 0\n' > "$release/frontend/node_modules/.bin/next"
chmod 700 "$release/backend/.venv/bin/python" "$release/frontend/node_modules/.bin/next"

# Reproduce the original failure under the workflow's restrictive umask.
if runuser -u hiddenoasis -- test -r "$release/frontend/.next/BUILD_ID"; then
  echo 'Synthetic release was unexpectedly accessible before repair.' >&2
  exit 1
fi

bash "$(dirname "$0")/set-release-permissions.sh" "$release"
test "$(stat -c '%U:%G' "$release")" = root:hiddenoasis
runuser -u hiddenoasis -- test -r "$release/backend/app.py"
runuser -u hiddenoasis -- test -x "$release/backend/.venv/bin/python"
runuser -u hiddenoasis -- test -x "$release/frontend/node_modules/.bin/next"
runuser -u hiddenoasis -- test -r "$release/frontend/.next/BUILD_ID"
runuser -u hiddenoasis -- test -w "$release/frontend/.next/cache/images"
if runuser -u hiddenoasis -- test -w "$release/backend/app.py"; then
  echo 'Synthetic backend source became writable by the service account.' >&2
  exit 1
fi
if runuser -u hiddenoasis -- test -w "$release/frontend/.next/BUILD_ID"; then
  echo 'Synthetic frontend build became writable by the service account.' >&2
  exit 1
fi
echo 'RELEASE SERVICE ACCESS: PASS'
