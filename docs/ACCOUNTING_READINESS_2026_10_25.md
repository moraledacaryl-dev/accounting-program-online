# Accounting release-readiness improvements — October 25, 2026

## Group 1: connected-app journal integrity

**High:** Integration Review used cent-rounded floating totals for proposals,
although the ledger persists four decimal places. A debit of 100.004 and credit
of 100 passed validation. Acceptance also bypassed the active-chart-account
checks required by manual journals. Both defects were reproduced in isolated
databases before correction; no production posting was attempted.

Intake now compares normalized decimal amounts at the ledger's four-place
precision. Acceptance applies the shared journal validator before creating a
posted journal, rechecking dates, valid lines, exact balance and active chart
accounts. Valid four-place amounts are stored without cent truncation. Existing
accepted history is preserved; no backfill, automatic acceptance or repair runs.

**Medium:** malformed journal lines and nonfinite amounts could cause unhelpful
errors or invalid JSON responses. Nonfinite transport amounts/JSON values are
rejected before persistence. JSON-safe malformed proposals retain validation
findings. Legacy row amounts are revalidated at acceptance. Request validation
responses retain the field location, message and error type without echoing
private submitted values or exception contexts.

Regression coverage includes isolated intake/HTTP boundaries, active/unknown
chart accounts, exact decimal posting and retries. Real PostgreSQL cases prove
that subcent imbalances cannot post and concurrent acceptance produces one
economic journal effect. CI includes these PostgreSQL cases.

Historical journal-linkage issue #249 and documentary financial acceptance
issue #334 remain separate. These controls do not reconcile bank balances,
prove original source documents, or authorize posting pending reviews.
