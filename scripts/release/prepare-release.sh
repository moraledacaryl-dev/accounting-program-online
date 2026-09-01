#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <40-character-git-sha>" >&2
  exit 2
fi

SHA="$1"
SOURCE_ROOT="${SOURCE_ROOT:-/opt/accounting-program-online}"
RELEASE_ROOT="${RELEASE_ROOT:-/opt/accounting-releases}"
BACKEND_ENV="${BACKEND_ENV:-/etc/hiddenoasis/accounting-backend.env}"
FRONTEND_ENV="${FRONTEND_ENV:-/etc/hiddenoasis/accounting-frontend.env}"
RELEASE="$RELEASE_ROOT/$SHA"

[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "Release SHA must be a full 40-character lowercase SHA." >&2; exit 2; }

test -d "$SOURCE_ROOT/.git"
mkdir -p "$RELEASE_ROOT"

git -C "$SOURCE_ROOT" fetch --no-tags origin main
git -C "$SOURCE_ROOT" cat-file -e "$SHA^{commit}"
git -C "$SOURCE_ROOT" merge-base --is-ancestor "$SHA" origin/main

test ! -e "$RELEASE" || { echo "Release already exists: $RELEASE" >&2; exit 1; }
git -C "$SOURCE_ROOT" worktree add --detach "$RELEASE" "$SHA"
test "$(git -C "$RELEASE" rev-parse HEAD)" = "$SHA"
test -z "$(git -C "$RELEASE" status --porcelain)"

python3 -m venv "$RELEASE/backend/.venv"
"$RELEASE/backend/.venv/bin/pip" install --disable-pip-version-check -r "$RELEASE/backend/requirements.txt"
"$RELEASE/backend/.venv/bin/python" -m compileall -q "$RELEASE/backend/app"

OLD_PATH="$PATH"
set -a
. "$FRONTEND_ENV"
set +a
export PATH="$OLD_PATH"

cd "$RELEASE/frontend"
npm ci
npm audit --omit=dev
npm run qa:ui
rm -rf .next
npm run build

test -f .next/BUILD_ID
if npm ls @playwright/test playwright playwright-core --depth=0 >/dev/null 2>&1; then
  echo "Playwright must not exist in immutable production release." >&2
  exit 1
fi

cd "$RELEASE"
TREE_SHA="$(git rev-parse HEAD^{tree})"
BACKEND_ENV_SHA="$(sha256sum "$BACKEND_ENV" | awk '{print $1}')"
FRONTEND_ENV_SHA="$(sha256sum "$FRONTEND_ENV" | awk '{print $1}')"
REQUIREMENTS_SHA="$(sha256sum backend/requirements.txt | awk '{print $1}')"
LOCK_SHA="$(sha256sum frontend/package-lock.json | awk '{print $1}')"
BUILD_ID="$(cat frontend/.next/BUILD_ID)"
ALEMBIC_HEAD="$(cd backend && ./.venv/bin/alembic -c alembic.ini heads | awk '{print $1}' | head -n1)"
test -n "$ALEMBIC_HEAD"

cat > .release-manifest <<EOF
release_sha=$SHA
tree_sha=$TREE_SHA
prepared_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
alembic_head=$ALEMBIC_HEAD
backend_requirements_sha256=$REQUIREMENTS_SHA
frontend_lock_sha256=$LOCK_SHA
backend_env_sha256=$BACKEND_ENV_SHA
frontend_env_sha256=$FRONTEND_ENV_SHA
frontend_build_id=$BUILD_ID
EOF

chown -R root:root "$RELEASE"
chmod 644 "$RELEASE/.release-manifest"

# Next.js image optimization writes runtime cache entries. Keep the release
# immutable except for this narrowly-scoped cache directory owned by the
# frontend service account.
install -d -o hiddenoasis -g hiddenoasis -m 0750 "$RELEASE/frontend/.next/cache/images"
test "$(stat -c '%U:%G' "$RELEASE/frontend/.next/cache/images")" = "hiddenoasis:hiddenoasis"
sudo -u hiddenoasis test -w "$RELEASE/frontend/.next/cache/images"

echo "Release: $RELEASE"
echo "SHA: $SHA"
echo "Tree: $TREE_SHA"
echo "Alembic head: $ALEMBIC_HEAD"
echo "Build ID: $BUILD_ID"
echo "IMMUTABLE RELEASE PREPARATION: PASS"
