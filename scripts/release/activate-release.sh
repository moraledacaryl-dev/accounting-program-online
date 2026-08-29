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
RELEASE="$RELEASE_ROOT/$SHA"

"$RELEASE/scripts/release/verify-release.sh" "$SHA"

CURRENT_TARGET=""
if [ -L "$CURRENT_LINK" ]; then
  CURRENT_TARGET="$(readlink -f "$CURRENT_LINK")"
fi
PREVIOUS_SHA="$(basename "${CURRENT_TARGET:-none}")"

ROOT="$RELEASE" "$RELEASE/scripts/dr/backup-accounting.sh"

OLD_PATH="$PATH"
set -a
. /etc/hiddenoasis/accounting-backend.env
set +a
export PATH="$OLD_PATH"

cd "$RELEASE/backend"
./.venv/bin/alembic -c alembic.ini upgrade head
EXPECTED_ALEMBIC="$(awk -F= '$1=="alembic_head" {print $2}' "$RELEASE/.release-manifest")"
CURRENT_ALEMBIC="$(./.venv/bin/alembic -c alembic.ini current 2>/dev/null | awk '{print $1}' | head -n1)"
test "$CURRENT_ALEMBIC" = "$EXPECTED_ALEMBIC"

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
echo "ATOMIC RELEASE ACTIVATION: PASS"
