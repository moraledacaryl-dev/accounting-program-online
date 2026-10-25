#!/usr/bin/env bash
# Serialize backup, activation and rollback across separate server processes.
# The deployment workflow holds fd 200 for its entire prepare/activate phase.
accounting_release_lock() {
  local lock_dir="${ACCOUNTING_RELEASE_LOCK_DIR:-/run/hiddenoasis-accounting-release}"
  local lock_file="$lock_dir/deployment.lock"
  if [[ "$lock_dir" != /* || -L "$lock_dir" || -L "$lock_file" ]]; then
    echo 'Unsafe Accounting release lock path.' >&2
    return 1
  fi
  install -d -m 0700 "$lock_dir"
  if [[ "$(stat -c %u "$lock_dir")" != "$EUID" ]] || (( $(stat -c %a "$lock_dir") % 100 != 0 )); then
    echo 'Accounting release lock directory is not private.' >&2
    return 1
  fi
  if [[ "${ACCOUNTING_RELEASE_LOCK_HELD:-}" == 1 ]]; then
    if [[ "$(readlink "/proc/$$/fd/200" 2>/dev/null || true)" != "$lock_file" ]]; then
      echo 'Accounting release lock descriptor is missing.' >&2
      return 1
    fi
  else
    exec 200>"$lock_file"
  fi
  if ! flock -n 200; then
    echo 'Accounting release or backup is already running.' >&2
    return 75
  fi
  export ACCOUNTING_RELEASE_LOCK_HELD=1
}
