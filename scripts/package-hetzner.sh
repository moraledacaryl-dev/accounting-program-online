#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/hiddenoasis-accounting-online.tar.gz}"

export LC_ALL=C

tar \
  --exclude='.git' \
  --exclude='.DS_Store' \
  --exclude='*.tar.gz' \
  --exclude='.env' \
  --exclude='.env.production' \
  --exclude='*/.env' \
  --exclude='*/.env.local' \
  --exclude='.venv' \
  --exclude='.pytest_cache' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='*.pyo' \
  --exclude='accounting.db' \
  --exclude='backend/accounting.db' \
  --exclude='backend/erp.db' \
  --exclude='backend/.env' \
  --exclude='backend/.venv' \
  --exclude='backend/uploads' \
  --exclude='frontend/.env.local' \
  --exclude='frontend/node_modules' \
  --exclude='frontend/.next' \
  --exclude='data' \
  --exclude='backups' \
  -czf "$OUT" \
  -C "$ROOT" .

echo "Created $OUT"
