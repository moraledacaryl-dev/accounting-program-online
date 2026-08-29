#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/opt/accounting-current}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/hiddenoasis/accounting}"
ENV_FILE="${ENV_FILE:-/etc/hiddenoasis/accounting-backend.env}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

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

DUMP="$BACKUP_DIR/accounting-$STAMP.dump"
META="$BACKUP_DIR/accounting-$STAMP.meta"
TMP="$DUMP.tmp"

trap 'rm -f "$TMP"' EXIT
sudo -u postgres pg_dump -Fc --dbname "$DB_NAME" --file "$TMP"
pg_restore --list "$TMP" >/dev/null
mv "$TMP" "$DUMP"
trap - EXIT

SHA="$(sha256sum "$DUMP" | awk '{print $1}')"
SIZE="$(stat -c '%s' "$DUMP")"
GIT_SHA="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || basename "$(readlink -f "$ROOT")")"
ALEMBIC="$(sudo -u postgres psql -Atqc 'SELECT version_num FROM alembic_version' "$DB_NAME" | head -n1)"

cat > "$META" <<EOF
format=postgresql-custom
created_utc=$STAMP
database=$DB_NAME
sha256=$SHA
size_bytes=$SIZE
release_sha=$GIT_SHA
alembic_revision=$ALEMBIC
EOF
chmod 600 "$DUMP" "$META"

find "$BACKUP_DIR" -type f \( -name 'accounting-*.dump' -o -name 'accounting-*.meta' \) -mtime +"$RETENTION_DAYS" -delete

echo "Backup: $DUMP"
echo "Metadata: $META"
echo "SHA256: $SHA"
echo "Alembic: $ALEMBIC"
echo "ACCOUNTING BACKUP: PASS"
