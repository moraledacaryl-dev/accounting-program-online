#!/usr/bin/env bash
set -euo pipefail

DEPLOY=.github/workflows/deploy-accounting.yml
CI=.github/workflows/ci.yml
GOLDEN=backend/tests/test_golden_ledger_pass72.py
SCALE=backend/tests/test_postgresql_pass72_certification.py

for file in "$DEPLOY" "$CI" "$GOLDEN" "$SCALE"; do
  test -f "$file"
done

# Deployment dependencies must be immutable, not floating tags.
grep -Fq 'uses: appleboy/ssh-action@029f5b4aeeeb58fdfe1410a5d17f967dacf36262' "$DEPLOY"
! grep -Eq 'uses: appleboy/ssh-action@v' "$DEPLOY"

# Golden-ledger invariants: balanced books, balanced balance sheet, reversal neutrality.
grep -Fq "statements['trial_balance']['totals']['is_balanced'] is True" "$GOLDEN"
grep -Fq "statements['balance_sheet']['totals']['balance_check'] == 0" "$GOLDEN"
grep -Fq 'net_by_account' "$GOLDEN"

# Dense PostgreSQL ledger certification must remain in the real-database lane.
grep -Fq 'entry_count = 1000' "$SCALE"
grep -Fq 'test_postgresql_trial_balance_remains_exact_at_dense_ledger_volume' "$SCALE"
grep -Fq 'tests/test_postgresql_pass72_certification.py' "$CI"

# Existing adversarial/security blockers remain required in the backend suite.
test -f backend/tests/test_application_ownership.py
test -f backend/tests/test_attachment_security_pass67.py
test -f backend/tests/test_auth_security_state.py
test -f backend/tests/test_security_perimeter_pass69.py
test -f backend/tests/test_transaction_atomicity_pass66.py
test -f backend/tests/test_operations_outbox_pass68.py

# Production dependency gates remain active.
grep -Fq 'python3 -m pip_audit -r requirements.lock.txt' "$CI"
grep -Fq 'npm audit --omit=dev' "$CI"
grep -Fq 'Run browser regression blocker' "$CI"

echo 'PASS 72 GOLDEN-LEDGER / SCALE / ADVERSARIAL SOURCE CONTRACT: PASS'
