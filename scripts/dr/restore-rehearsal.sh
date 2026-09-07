#!/usr/bin/env bash
set -euo pipefail
umask 077

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

EVIDENCE_DIR="$(mktemp -d)"
REHEARSAL_DB="accounting_dr_$(date -u +%Y%m%d%H%M%S)_$$"
cleanup() {
  sudo -u postgres dropdb --if-exists "$REHEARSAL_DB" >/dev/null 2>&1 || true
  rm -rf "$EVIDENCE_DIR"
}
trap cleanup EXIT

UPLOADS_NAME="$(awk -F= '$1=="uploads_archive" {print $2}' "$META")"
UPLOADS_SHA="$(awk -F= '$1=="uploads_sha256" {print $2}' "$META")"
if [ -z "$UPLOADS_NAME" ] || [ -z "$UPLOADS_SHA" ]; then
  echo "FAIL: backup has no evidence archive. Create a complete database and uploads backup." >&2
  exit 1
fi
[[ "$UPLOADS_NAME" != */* ]] || exit 1
EVIDENCE_ARCHIVE="$(dirname "$DUMP")/$UPLOADS_NAME"
test "$(sha256sum "$EVIDENCE_ARCHIVE" | awk '{print $1}')" = "$UPLOADS_SHA"
# Use Python's data filter to reject traversal, links outside the destination, and devices.
python3 - "$EVIDENCE_ARCHIVE" "$EVIDENCE_DIR" <<'PYTHON'
import sys, tarfile
with tarfile.open(sys.argv[1], 'r:gz') as archive:
    for member in archive.getmembers():
        if not (member.isfile() or member.isdir()):
            raise SystemExit('Evidence archive must contain only regular files and directories.')
        if member.name.startswith('/') or '..' in member.name.split('/'):
            raise SystemExit('Unsafe evidence archive path.')
    archive.extractall(sys.argv[2], filter='data')
PYTHON

sudo -u postgres createdb "$REHEARSAL_DB"
sudo -u postgres pg_restore --exit-on-error --no-owner --no-privileges --dbname "$REHEARSAL_DB" < "$DUMP"

RESTORED_ALEMBIC="$(sudo -u postgres psql -Atqc 'SELECT version_num FROM alembic_version' "$REHEARSAL_DB" | head -n1)"
test -n "$RESTORED_ALEMBIC"
test "$RESTORED_ALEMBIC" = "$EXPECTED_ALEMBIC"

TABLES="$(sudo -u postgres psql -Atqc "SELECT count(*) FROM pg_tables WHERE schemaname='public'" "$REHEARSAL_DB")"
test "${TABLES:-0}" -gt 0

sudo -u postgres psql -v ON_ERROR_STOP=1 -Atqc 'SELECT 1' "$REHEARSAL_DB" >/dev/null

sudo -u postgres psql -v ON_ERROR_STOP=1 -Atqc "SELECT coalesce(json_agg(a), '[]'::json) FROM (SELECT id, stored_name, file_path, size_bytes FROM attachments) a" "$REHEARSAL_DB" | python3 "$(dirname "$0")/verify-evidence.py" "$EVIDENCE_DIR"

cleanup
trap - EXIT

echo "Backup checksum: PASS"
echo "pg_restore archive validation: PASS"
echo "Restored Alembic: $RESTORED_ALEMBIC"
echo "Restored public tables: $TABLES"
echo "Evidence archive checksum and isolated extraction: PASS"
echo "DISASTER RECOVERY RESTORE REHEARSAL: PASS"
