# Read-only Staff manual repayment ↔ Accounting reconciliation

The Staff historical audit identified five active manual repayments totaling
₱10,500 without a **Staff Accounting outbox** event. This does **not** prove
that Accounting lacks entries. All were recorded before the Staff outbox
fix in October 2026.

The Accounting-side script
`backend/scripts/audit_staff_manual_repayment_crossapp.py` checks *only*:

1. Exact `integration_review_items` source `staff` and
   `cash-advance-repayment:<id>`.
2. Exact legacy `integration_receipts` source
   `hidden_oasis_staff_payroll` and the same external ID.
3. Exact `money_transactions` external IDs with their Staff source identity.
4. Separately, **unverified** same-day/same-amount Money In candidates.

The script never matches a same-day amount as proof that money was received.
A row can appear as a candidate for multiple repayments, especially the two
₱3,000 receipts dated September 18. `source_identity_found` is only evidence
of an intake/linked record—not a posted, legitimate receipt. Even posted
cash transactions require document/bank/cash-ledger reconciliation.

## Server execution (no deployment necessary)

Fetch the merged commit in the Accounting source checkout first; do not
switch the runtime release. Use the same secure environment file as the
Accounting backend service, and ensure you are authorized to inspect both
databases. The script opens Staff SQLite in URI read-only mode with
`PRAGMA query_only=ON`, and uses a read-only Accounting transaction
(`SET TRANSACTION READ ONLY` on PostgreSQL).

```bash
cd /root/repos/accounting-program-online
git fetch origin main
git merge --ff-only origin/main
set -a
source /etc/hiddenoasis/staff-payroll.env
STAFF_DB="$STAFF_PAYROLL_DB_PATH"
source /etc/hiddenoasis/accounting-backend.env
set +a
cd backend
umask 077
.venv/bin/python scripts/audit_staff_manual_repayment_crossapp.py \
  --staff-db "$STAFF_DB" --limit 30 \
  | tee /tmp/staff-accounting-crossapp-reconciliation.json
```

If this checkout has no usable `.venv`, use the backend's installed
production Python interpreter without activating a deployment, provided
its dependencies match the checked-out code. **Do not run DB migrations,
replays, retroactive journal posting, or financial corrections as part of
this audit.**

For the five Staff repayment IDs 15, 29, 30, 42 and 43, compare the
returned source-identity evidence with actual Staff cash-advance balances,
the Accounting review queue, any manually entered Money In transactions,
cash count records, deposit receipts and bank/GCash statements.

**Payment method exception:** Staff repayment #30 is ₱3,000 dated
2026-08-15 with method `Other`. Confirm the actual receiving account and
receipt before considering a posting or replay. The other four use Cash,
but a Cash label alone is not evidence of receipt.

All output omits employee names and literal receipt references. Keep
database credentials private; do not paste environment variable values.
