#!/usr/bin/env bash
set -euo pipefail

HOST="${SMOKE_HOST:-127.0.0.1}"
PORT="${SMOKE_PORT:-3100}"
BASE_URL="http://${HOST}:${PORT}"
LOG_FILE="${RUNNER_TEMP:-/tmp}/accounting-frontend-smoke.log"

npm run start -- --hostname "$HOST" --port "$PORT" >"$LOG_FILE" 2>&1 &
SERVER_PID=$!

cleanup() {
  kill "$SERVER_PID" 2>/dev/null || true
  wait "$SERVER_PID" 2>/dev/null || true
}
trap cleanup EXIT

for attempt in $(seq 1 30); do
  if curl --silent --show-error --fail "$BASE_URL/login" >/dev/null 2>&1; then
    break
  fi

  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "Frontend server exited before becoming ready."
    cat "$LOG_FILE"
    exit 1
  fi

  if [[ "$attempt" == "30" ]]; then
    echo "Frontend server did not become ready within 30 seconds."
    cat "$LOG_FILE"
    exit 1
  fi

  sleep 1
done

assert_status() {
  local path="$1"
  local expected="$2"
  local actual

  actual=$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' "$BASE_URL$path")
  if [[ "$actual" != "$expected" ]]; then
    echo "Smoke check failed for $path: expected HTTP $expected, received $actual."
    cat "$LOG_FILE"
    exit 1
  fi

  echo "Smoke check passed: $path -> HTTP $actual"
}

assert_status "/login" "200"
assert_status "/dashboard" "200"
assert_status "/reports" "200"
assert_status "/this-route-must-not-exist" "404"

echo "Frontend production smoke checks passed."
