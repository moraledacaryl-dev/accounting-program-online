#!/usr/bin/env bash
set -euo pipefail

for script in \
  scripts/dr/backup-accounting.sh \
  scripts/dr/restore-rehearsal.sh \
  scripts/release/prepare-release.sh \
  scripts/release/verify-release.sh \
  scripts/release/activate-release.sh \
  scripts/release/rollback-release.sh
do
  bash -n "$script"
done

for unit in \
  deploy/systemd/accounting-backend.service \
  deploy/systemd/accounting-frontend.service \
  deploy/systemd/accounting-operations-outbox.service
do
  grep -Fq '/opt/accounting-current/' "$unit"
  if grep -Fq '/opt/accounting-program-online/' "$unit"; then
    echo "Mutable production path found in canonical unit: $unit" >&2
    exit 1
  fi
done

test ! -e deploy/systemd/hiddenoasis-accounting-backend.service
test ! -e deploy/systemd/hiddenoasis-accounting-frontend.service

grep -Fq 'ReadWritePaths=-/var/lib/hiddenoasis/accounting/uploads' deploy/systemd/accounting-backend.service
grep -Fq "PRODUCTION_UPLOADS_PATH = Path('/var/lib/hiddenoasis/accounting/uploads')" backend/app/core/settings.py
grep -Fq 'install -d -o hiddenoasis -g hiddenoasis -m 0750 "$UPLOADS_DIR"' scripts/release/activate-release.sh
grep -Fq 'LEGACY_UPLOADS_DIR="${LEGACY_UPLOADS_DIR:-/opt/accounting-program-online/backend/uploads}"' scripts/release/activate-release.sh
grep -Fq 'sha256=' scripts/dr/backup-accounting.sh
grep -Fq 'pg_restore --exit-on-error' scripts/dr/restore-rehearsal.sh
grep -Fq 'merge-base --is-ancestor' scripts/release/prepare-release.sh
grep -Fq 'backend_env_sha256' scripts/release/verify-release.sh
grep -Fq 'mv -Tf' scripts/release/activate-release.sh
grep -Fq 'REFUSING ROLLBACK' scripts/release/rollback-release.sh

echo 'PASS 71 DR / IMMUTABLE DEPLOYMENT SOURCE CONTRACT: PASS'