#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
DB_FILE="${ROOT}/.pytest-accounting.db"
trap 'rm -f "${DB_FILE}"' EXIT

cd "${ROOT}"
rm -f "${DB_FILE}"

env \
  -u INTEGRATION_API_KEY \
  -u INTEGRATION_SECRET \
  -u INTEGRATION_PASSWORD \
  -u INTEGRATION_USERNAME \
  ENVIRONMENT=test \
  DATABASE_URL="sqlite:///${DB_FILE}" \
  SECRET_KEY="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" \
  STARTUP_REQUIRE_MIGRATIONS=false \
  ALLOW_DEFAULT_ADMIN_BOOTSTRAP=false \
  ALLOW_DEMO_SEED=false \
  "${PYTHON}" -m pytest
