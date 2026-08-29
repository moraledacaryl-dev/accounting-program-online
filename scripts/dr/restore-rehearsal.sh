#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 /path/to/accounting-YYYYMMDDTHHMMSSZ.dump" >&2
  exit 2
fi

DUMP="$(readlink -f "$1")"
META="${DUMP%.dump}.meta"

test -f "$DUMP"
test -f "$META"

EXPECTED_SHA="$(awk -F= '$1=="sha256" {print $2}' "$META")"
EXPECTED_ALEMBIC="$(awk -F= '$1=="alembic_revision" {print $2}' "$META")"
ACTUAL_SHA="$(sha256sum "$DUMP" | awk '{print $1}')"

test -n "$EXPECTED_SHA"
test "$ACTUAL_SHA" = "$EXPECTED_SHA"
pg_restore --list "$DUMP" >/dev/null

REHEARSAL_DB="accounting_dr_$(date -u +%Y%m%d%H%M%S)_$$"
cleanup() {
  sudo -u postgres dropdb --if-exists "$REHEARSAL_DB" >/dev/null 2>&1 || true
}
trap cleanup EXIT

sudo -u postgres createdb "$REHEARSAL_DB"
sudo -u postgres pg_restore --exit-on-error --no-owner --no-privileges --dbname "$REHEARSAL_DB" "$DUMP"

RESTORED_ALEMBIC="$(sudo -u postgres psql -Atqc 'SELECT version_num FROM alembic_version' "$REHEARSAL_DB" | head -n1)"
test -n "$RESTORED_ALEMBIC"
test "$RESTORED_ALEMBIC" = "$EXPECTED_ALEMBIC"

TABLES="$(sudo -u postgres psql -Atqc "SELECT count(*) FROM pg_tables WHERE schemaname='public'" "$REHEARSAL_DB")"
test "${TABLES:-0}" -gt 0

sudo -u postgres psql -v ON_ERROR_STOP=1 -Atqc 'SELECT 1' "$REHEARSAL_DB" >/dev/null

cleanup
trap - EXIT

echo "Backup checksum: PASS"
echo "pg_restore archive validation: PASS"
echo "Restored Alembic: $RESTORED_ALEMBIC"
echo "Restored public tables: $TABLES"
echo "DISASTER RECOVERY RESTORE REHEARSAL: PASS"
