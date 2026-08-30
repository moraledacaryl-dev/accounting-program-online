#!/usr/bin/env bash
set -euo pipefail

TARGET_SHA="${1:-}"
RELEASE_ROOT="${RELEASE_ROOT:-/opt/accounting-releases}"
CURRENT_LINK="${CURRENT_LINK:-/opt/accounting-current}"
STATE_DIR="${STATE_DIR:-/var/lib/hiddenoasis/accounting-release}"

if [ -z "$TARGET_SHA" ]; then
  test -f "$STATE_DIR/previous.sha"
  TARGET_SHA="$(cat "$STATE_DIR/previous.sha")"
fi

[[ "$TARGET_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "No valid rollback SHA available." >&2; exit 2; }
test -L "$CURRENT_LINK" || { echo "No active immutable release is available to perform rollback." >&2; exit 1; }
TOOL_ROOT="$(readlink -f "$CURRENT_LINK")"
TARGET="$RELEASE_ROOT/$TARGET_SHA"
test -f "$TOOL_ROOT/scripts/release/verify-release.sh"
bash "$TOOL_ROOT/scripts/release/verify-release.sh" "$TARGET_SHA"

OLD_PATH="$PATH"
set -a
. /etc/hiddenoasis/accounting-backend.env
set +a
export PATH="$OLD_PATH"

EXPECTED_ALEMBIC="$(awk -F= '$1=="alembic_head" {print $2}' "$TARGET/.release-manifest")"
CURRENT_ALEMBIC="$(cd "$TARGET/backend" && ./.venv/bin/alembic -c alembic.ini current 2>/dev/null | awk '{print $1}' | head -n1)"
if [ "$CURRENT_ALEMBIC" != "$EXPECTED_ALEMBIC" ]; then
  echo "REFUSING ROLLBACK: database revision $CURRENT_ALEMBIC is not compatible with target release head $EXPECTED_ALEMBIC." >&2
  exit 1
fi

CURRENT_SHA="$(basename "$TOOL_ROOT")"

ln -sfn "$TARGET" "${CURRENT_LINK}.new"
mv -Tf "${CURRENT_LINK}.new" "$CURRENT_LINK"

test "$(readlink -f "$CURRENT_LINK")" = "$TARGET"

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
printf '%s\n' "$TARGET_SHA" > "$STATE_DIR/current.sha"
printf '%s\n' "$CURRENT_SHA" > "$STATE_DIR/previous.sha"
printf '%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$STATE_DIR/activated.utc"
chmod 600 "$STATE_DIR"/*.sha "$STATE_DIR"/*.utc

echo "Rolled back from: $CURRENT_SHA"
echo "Current release: $TARGET_SHA"
echo "Schema compatibility: PASS ($CURRENT_ALEMBIC)"
echo "ATOMIC RELEASE ROLLBACK: PASS"
