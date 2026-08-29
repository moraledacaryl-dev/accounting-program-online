#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <40-character-git-sha>" >&2
  exit 2
fi

SHA="$1"
RELEASE_ROOT="${RELEASE_ROOT:-/opt/accounting-releases}"
BACKEND_ENV="${BACKEND_ENV:-/etc/hiddenoasis/accounting-backend.env}"
FRONTEND_ENV="${FRONTEND_ENV:-/etc/hiddenoasis/accounting-frontend.env}"
RELEASE="$RELEASE_ROOT/$SHA"
MANIFEST="$RELEASE/.release-manifest"

[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || exit 2
test -f "$MANIFEST"
test "$(git -C "$RELEASE" rev-parse HEAD)" = "$SHA"
test -z "$(git -C "$RELEASE" status --porcelain --untracked-files=no)"

manifest_value() {
  awk -F= -v key="$1" '$1==key {sub(/^[^=]*=/, ""); print; exit}' "$MANIFEST"
}

test "$(manifest_value release_sha)" = "$SHA"
test "$(manifest_value tree_sha)" = "$(git -C "$RELEASE" rev-parse HEAD^{tree})"
test "$(manifest_value backend_requirements_sha256)" = "$(sha256sum "$RELEASE/backend/requirements.txt" | awk '{print $1}')"
test "$(manifest_value frontend_lock_sha256)" = "$(sha256sum "$RELEASE/frontend/package-lock.json" | awk '{print $1}')"
test "$(manifest_value backend_env_sha256)" = "$(sha256sum "$BACKEND_ENV" | awk '{print $1}')"
test "$(manifest_value frontend_env_sha256)" = "$(sha256sum "$FRONTEND_ENV" | awk '{print $1}')"
test "$(manifest_value frontend_build_id)" = "$(cat "$RELEASE/frontend/.next/BUILD_ID")"
test -x "$RELEASE/backend/.venv/bin/python"
test -x "$RELEASE/frontend/node_modules/.bin/next"

if "$RELEASE/frontend/node_modules/.bin/next" --version | grep -q '^Next.js '; then :; else exit 1; fi

if (cd "$RELEASE/frontend" && npm ls @playwright/test playwright playwright-core --depth=0 >/dev/null 2>&1); then
  echo "FAIL: browser test tooling exists in production artifact." >&2
  exit 1
fi

echo "Release SHA: $SHA"
echo "Release tree/config/dependencies/build identity: PASS"
echo "IMMUTABLE RELEASE VERIFICATION: PASS"
