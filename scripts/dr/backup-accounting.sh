#!/usr/bin/env bash
set -euo pipefail
umask 077
source "$(dirname "$0")/../release/release-lock.sh"
accounting_release_lock

ROOT="${ROOT:-/opt/accounting-current}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/hiddenoasis/accounting}"
ENV_FILE="${ENV_FILE:-/etc/hiddenoasis/accounting-backend.env}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_EVIDENCE_DIR="${BACKUP_UPLOADS_DIR:-/var/lib/hiddenoasis/accounting/uploads}"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

# A new dump, uploads archive and sidecar form one dated evidence set. Never
# reuse a name, even when an operator invokes two backups in the same second.
DUMP="$BACKUP_DIR/accounting-$STAMP.dump"
META="$BACKUP_DIR/accounting-$STAMP.meta"
TMP="$DUMP.tmp"
EVIDENCE="$BACKUP_DIR/accounting-$STAMP.uploads.tar.gz"
EVIDENCE_TMP="$EVIDENCE.tmp"
META_TMP="$META.tmp"
for path in "$DUMP" "$META" "$TMP" "$EVIDENCE" "$EVIDENCE_TMP" "$META_TMP"; do
  if [ -e "$path" ] || [ -L "$path" ]; then
    echo 'Accounting backup name already exists; wait for a new UTC second.' >&2
    exit 1
  fi
done
FREE_BYTES="$(df -B1 --output=avail "$BACKUP_DIR" | tail -n 1 | tr -d ' ')"
if ! [[ "$FREE_BYTES" =~ ^[0-9]+$ ]] || [ "$FREE_BYTES" -lt 4294967296 ]; then
  echo 'Accounting backup blocked: less than 4 GiB free.' >&2
  exit 1
fi

test -x "$ROOT/backend/.venv/bin/python"
test -f "$ENV_FILE"

OLD_PATH="$PATH"
set -a
. "$ENV_FILE"
set +a
export PATH="$OLD_PATH"

DB_NAME="$($ROOT/backend/.venv/bin/python - <<'PY'
import os
from sqlalchemy.engine import make_url
url = make_url(os.environ['DATABASE_URL'])
if not url.database:
    raise SystemExit('DATABASE_URL has no database name')
print(url.database)
PY
)"

UPLOADS_DIR="$BACKUP_EVIDENCE_DIR"
test -d "$UPLOADS_DIR"

trap 'rm -f "$TMP" "$EVIDENCE_TMP" "$META_TMP"' EXIT
sudo -u postgres pg_dump -Fc --dbname "$DB_NAME" > "$TMP"
pg_restore --list "$TMP" >/dev/null
tar -czf "$EVIDENCE_TMP" -C "$UPLOADS_DIR" .
tar -tzf "$EVIDENCE_TMP" >/dev/null
mv "$EVIDENCE_TMP" "$EVIDENCE"
mv "$TMP" "$DUMP"
EVIDENCE_SHA="$(sha256sum "$EVIDENCE" | awk '{print $1}')"

SHA="$(sha256sum "$DUMP" | awk '{print $1}')"
SIZE="$(stat -c '%s' "$DUMP")"
GIT_SHA="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || basename "$(readlink -f "$ROOT")")"
ALEMBIC="$(sudo -u postgres psql -Atqc 'SELECT version_num FROM alembic_version' "$DB_NAME" | head -n1)"

cat > "$META_TMP" <<EOF
format=postgresql-custom
created_utc=$STAMP
database=$DB_NAME
sha256=$SHA
size_bytes=$SIZE
release_sha=$GIT_SHA
alembic_revision=$ALEMBIC
uploads_archive=$(basename "$EVIDENCE")
uploads_sha256=$EVIDENCE_SHA
EOF
mv "$META_TMP" "$META"
trap - EXIT
chmod 600 "$DUMP" "$META" "$EVIDENCE"

# Retention needs an explicit operator policy; backup jobs never delete archives.

# A separately managed mounted backup destination may be configured by operators.
if [ -n "${BACKUP_MIRROR_DIR:-}" ]; then
  test -d "$BACKUP_MIRROR_DIR"
  cp "$DUMP" "$EVIDENCE" "$META" "$BACKUP_MIRROR_DIR/"
fi

echo "Backup: $DUMP"
echo "Metadata: $META"
echo "SHA256: $SHA"
echo "Alembic: $ALEMBIC"
echo "ACCOUNTING BACKUP: PASS"
