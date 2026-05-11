#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/hiddenoasis/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
STAMP="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

sudo -u postgres pg_dump -Fc hiddenoasis_erp_live > "$BACKUP_DIR/hiddenoasis_erp_live-$STAMP.dump"
sudo -u postgres pg_dump -Fc hiddenoasis_pos_live > "$BACKUP_DIR/hiddenoasis_pos_live-$STAMP.dump"

find "$BACKUP_DIR" -type f -name '*.dump' -mtime +"$RETENTION_DAYS" -delete

echo "Backups written to $BACKUP_DIR"
