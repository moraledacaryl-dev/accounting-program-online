#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <40-character-git-sha>" >&2
  exit 2
fi

SHA="$1"
RELEASE_ROOT="${RELEASE_ROOT:-/opt/accounting-releases}"
CURRENT_LINK="${CURRENT_LINK:-/opt/accounting-current}"
STATE_DIR="${STATE_DIR:-/var/lib/hiddenoasis/accounting-release}"
UPLOADS_DIR="${UPLOADS_DIR:-/var/lib/hiddenoasis/accounting/uploads}"
LEGACY_UPLOADS_DIR="${LEGACY_UPLOADS_DIR:-/opt/accounting-program-online/backend/uploads}"
RELEASE="$RELEASE_ROOT/$SHA"

# Deployment-controlled filesystem paths must not be overridden by application
# environment values sourced below (for example, a legacy UPLOADS_DIR=./uploads).
DEPLOY_UPLOADS_DIR="$UPLOADS_DIR"
DEPLOY_LEGACY_UPLOADS_DIR="$LEGACY_UPLOADS_DIR"

bash "$RELEASE/scripts/release/verify-release.sh" "$SHA"

CURRENT_TARGET=""
if [ -L "$CURRENT_LINK" ]; then
  CURRENT_TARGET="$(readlink -f "$CURRENT_LINK")"
fi
PREVIOUS_SHA="$(basename "${CURRENT_TARGET:-none}")"

ROOT="$RELEASE" bash "$RELEASE/scripts/dr/backup-accounting.sh"

OLD_PATH="$PATH"
set -a
. /etc/hiddenoasis/accounting-backend.env
set +a
export PATH="$OLD_PATH"
UPLOADS_DIR="$DEPLOY_UPLOADS_DIR"
LEGACY_UPLOADS_DIR="$DEPLOY_LEGACY_UPLOADS_DIR"

cd "$RELEASE/backend"
./.venv/bin/alembic -c alembic.ini upgrade head
EXPECTED_ALEMBIC="$(awk -F= '$1=="alembic_head" {print $2}' "$RELEASE/.release-manifest")"
CURRENT_ALEMBIC="$(./.venv/bin/alembic -c alembic.ini current 2>/dev/null | awk '{print $1}' | head -n1)"
test "$CURRENT_ALEMBIC" = "$EXPECTED_ALEMBIC"

install -d -o hiddenoasis -g hiddenoasis -m 0750 "$(dirname "$UPLOADS_DIR")"
install -d -o hiddenoasis -g hiddenoasis -m 0750 "$UPLOADS_DIR"
if [ -d "$LEGACY_UPLOADS_DIR" ]; then
  find "$LEGACY_UPLOADS_DIR" -mindepth 1 -maxdepth 1 -type f -print0 \
    | while IFS= read -r -d '' file; do
        target="$UPLOADS_DIR/$(basename "$file")"
        if [ ! -e "$target" ]; then
          install -o hiddenoasis -g hiddenoasis -m 0600 "$file" "$target"
        fi
      done
fi

install -o root -g root -m 0644 "$RELEASE/deploy/systemd/accounting-backend.service" /etc/systemd/system/accounting-backend.service
install -o root -g root -m 0644 "$RELEASE/deploy/systemd/accounting-frontend.service" /etc/systemd/system/accounting-frontend.service
install -o root -g root -m 0644 "$RELEASE/deploy/systemd/accounting-operations-outbox.service" /etc/systemd/system/accounting-operations-outbox.service
systemctl daemon-reload

ln -sfn "$RELEASE" "${CURRENT_LINK}.new"
mv -Tf "${CURRENT_LINK}.new" "$CURRENT_LINK"

test "$(readlink -f "$CURRENT_LINK")" = "$RELEASE"

systemctl restart accounting-backend
systemctl restart accounting-operations-outbox
systemctl restart accounting-frontend

for service in accounting-backend accounting-operations-outbox accounting-frontend; do
  test "$(systemctl is-active "$service")" = active
done

for _ in $(seq 1 30); do
  curl -fsS http://127.0.0.1:8000/healthz >/dev/null 2>&1 && curl -fsSI http://127.0.0.1:3000 >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS http://127.0.0.1:8000/healthz >/dev/null
curl -fsSI http://127.0.0.1:3000 >/dev/null

mkdir -p "$STATE_DIR"
chmod 700 "$STATE_DIR"
printf '%s\n' "$SHA" > "$STATE_DIR/current.sha"
printf '%s\n' "$PREVIOUS_SHA" > "$STATE_DIR/previous.sha"
printf '%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$STATE_DIR/activated.utc"
chmod 600 "$STATE_DIR"/*.sha "$STATE_DIR"/*.utc

echo "Previous release: $PREVIOUS_SHA"
echo "Current release: $SHA"
echo "Alembic: $CURRENT_ALEMBIC"
echo "Persistent uploads: $UPLOADS_DIR"
echo "ATOMIC RELEASE ACTIVATION: PASS"
