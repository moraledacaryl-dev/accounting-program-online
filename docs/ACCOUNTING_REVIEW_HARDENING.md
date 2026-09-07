# Accounting review hardening — 7 September 2026

This change closes the demonstrated generic-record authorization, ledger consistency, and manual journal validation gaps from the independent review. It also improves finance workflows and strengthens release evidence.

## Financial controls

- Generic record mutations require module-specific permissions. Finance directions and approval/rejection transitions have additional permission checks. Both record approval routes follow the same policy. POS ownership also covers breakfast, cafe, and bar records.
- Posted generic records allow audited notes only; they cannot be changed financially or deleted. Corrections use the journal reversal workflow followed by a replacement source record referencing the original. Records and generated journals commit together.
- Manual journals require real dates, valid active chart accounts, at least two meaningful lines, nonnegative finite values, one side per line, and exact debit/credit equality. Stored account names come from the chart.
- Journal writes/reversals use row locks, and browser creation retries retain an idempotency key. A changed payload with a reused key is rejected.
- Reports and trial balance share the same posted-entry filter. Original posted entries and their posted reversals remain included so the economic effect nets correctly.
- Active configured posting rules control generic record posting, ordered by priority, specificity, and id. Missing/inactive accounts in matching rules block posting. Existing default maps remain the compatibility fallback when no rule matches.
- Chart-account cycles, deletion of used accounts, and renumbering accounts with journal history are rejected.
- Journal amounts use Numeric(20,4), with Decimal validation and reversal amounts. Other operational monetary fields still use their existing storage types; this is not a full conversion of every monetary field in the system.
- Financial statements aggregate journal lines in SQL, materializing one row per account rather than all ledger history. Other management-report datasets still need production-scale benchmarking.

## Interface

Accountants see cash/bank, AR, AP, reconciliation and approvals first. Hospitality context remains available. Retained integration records are labeled as unverified activity, not proof of a live connection. Beds24 cards identify the last recorded event/time.

Journals and payables open on their registers with explicit create actions. Journal fields use chart-account selection, validation, pending-save protection, empty/success/error states, keyboard-accessible details, and confirmations for financial state transitions. Amounts and report labels use clearer terminology, and close blockers link to their workflows. Mobile finance navigation is more compact. Connected operational actions point to the owning apps.

## Deployment and compatibility

Apply Alembic revision `0009_journal_precision` before starting this source revision. On PostgreSQL it converts journal debit/credit to Numeric(20,4). It stops on non-finite, out-of-range, or materially higher-precision historical values rather than silently rounding them. Rehearse against a recent production backup before activation. The change does not rewrite historical records or repair existing source/journal discrepancies automatically.

Legacy malformed draft journals cannot be posted until corrected. The manual journal API now requires a date and meaningful balanced lines even for saved drafts. Generic record status `posted` is no longer offered: approval generates the journal. Verify existing clients use the supported draft/pending_review/approved/rejected/cancelled states.

The database backup script now requires an uploads directory and creates a matching evidence archive and checksum. The restore rehearsal rejects incomplete database-only backup sets, unsafe archive entries, missing referenced files, and file-size mismatches. It extracts only into a temporary directory. `BACKUP_MIRROR_DIR` can copy complete sets to an operator-managed mounted destination; setting it does not itself establish or verify offsite storage. Database and evidence backup captures are sequential, so a write-quiesced backup or coordinated filesystem snapshot is recommended for exact point-in-time recovery.

No production database or financial records were changed during implementation. Deployment should use the existing exact-SHA release workflow after CI and production-data rehearsal.

## Validation evidence

- Backend suite: 231 passed; 15 PostgreSQL-only cases skipped in the SQLite lane.
- Isolated PostgreSQL lane: all 15 passed, including concurrent reversal protection and a clean migration to revision 0009.
- Browser suite: all 26 passed, including journal retry idempotency, keyboard interaction, mobile layout, dashboard metrics, and existing finance workflows. The local run used Playwright 1.55 with the already installed Chromium 1234 executable; CI retains the repository's pinned browser installation.
- Frontend production build passed. Clean SQLite migration, Python compilation, shell syntax, and diff whitespace checks passed.
- Production frontend dependency audit and locked backend dependency audit reported no known vulnerabilities at the time of the run.

These are local and isolated-database checks. Production-data migration, production load, and an actual offsite restore rehearsal remain unverified.

## Remaining architectural work

This is substantial hardening, not a claim of perfection. Historical migration 0001 still imports application metadata; replacing it needs a separately verified baseline. The large cashflow service and layered CSS remain candidates for incremental consolidation. Full operational-money Decimal conversion, production-load benchmarks, remote health monitoring, and a measured offsite recovery rehearsal remain separate work. The live database must be checked for pre-existing journal/source mismatches before certifying historical balances.

Before production activation, run `backend/scripts/check_accounting_integrity.py` with the intended backend environment. It is read-only and returns a nonzero exit status for malformed posted journals, source/journal mismatches, missing source records, or duplicate reversals. Review flagged record IDs and make audited corrections; never bulk-rewrite ledger history to silence the check.
