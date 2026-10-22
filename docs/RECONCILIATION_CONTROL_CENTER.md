# Reconciliation Control Center and Integration Intake

## What has been built

The Accounting dashboard now links to **Reconciliation Control Center**
(`/reconciliation-center`). It reads four independently permission-checked
sources: private historical Journal Review, Cash & Treasury daily reconciliation,
integration Review Inbox summary, and period-close readiness.

The page **does not** post journals, link folios, match deposits, change cash
balances, or set an accounting period to reconciled. It shows unavailable or
role-restricted data as unknown, **never as zero**.

## Recommended review order

1. **Journal Review:** owner/admin opens the private historical evidence
   worklist; inspect receipts, source identity, cashbook, folio and existing
   journals. Recording a review does not resolve the journal mismatch.
2. **Daily cash:** confirm counted drawer balances, cash, bank and GCash
   movement. Review variances before approving a daily close.
3. **Review Inbox:** inspect incoming events from POS, Inventory, Payroll and
   other sources. Select **Review failed validations** to isolate failed items.
   Source cards show only *received retained events*; click a card to apply
   that application's filter.
4. **Period close:** use the source-specific checklist and financial statements.
   A passed readiness checklist does not certify cash, AR/AP or ledger balances.

## Distinguish these states

| State | Meaning |
|---|---|
| Source checked | The API returned successfully |
| Restricted | The user lacks permission; no data is exposed |
| Unavailable | Fetch failed; no negative inference is permitted |
| Zero received integration events | No review items retained for that source; **not** proof of connectivity |
| Evidence recorded for a journal exception | Reviewer saved a classification; **not** journal linkage resolution |
| Financially reconciled | Underlying evidence and GL agree, independently signed off |

The historical 166 missing journal direct links in issue #249 remain an
evidence-dependent backlog until verified individually. Do not create
synthetic financial transactions, overwrite booking/folio cash histories,
or assume app uptime proves correct event delivery.

## Scope excluded from this improvement group

Bank/GCash statement file importing, OCR, AI-based bank parsing, and
automatic ledger adjustment have intentionally **not** been added.


## Integration delivery evidence (Group 3, read-only)

The reconciliation page also shows **Source intake evidence**, sourced from the
existing permission-gated Integration Review summary. For each producer it shows
retained intake counts, latest recorded receipt time, validation/review counts,
accepted events with or without direct Accounting foreign-key links, rejected
events, and source events that have multiple stored revisions. The raw intake
counters include Staff revision records excluded from the *actionable* queue.

These are **Accounting observation metrics**, not producer health metrics:

- An empty feed or an old "last received" time does not prove a source is
  disconnected; a recent one does not prove delivery completeness.
- Unreceived events, sender connectivity, duplicate delivery attempts and
  source outbox backlog remain explicitly **unknown** until checked upstream.
- An accepted reference-only event can correctly lack a direct Accounting
  financial link. Do not auto-post or reclassify based on the count.
- No webhook, source delivery acknowledgement, cash movement, journal,
  booking, payroll run, or financial balance is changed by this view.

Source outbox watermarks and end-to-end delivery proofs remain an outstanding
acceptance gate for a fully certified integration.


## Review Inbox aging and query efficiency

Source cards distinguish pending events older than seven full days from
those with missing or unparsable intake timestamps. An oldest pending
timestamp is shown only when a timestamp exists. These observations refer
only to Accounting-received records, not upstream sender health.

The summary builds Staff Approved/Paid visibility from one retained snapshot
rather than querying per approved payroll run. Existing visible Review Inbox
totals and immutable Staff revision history are preserved.


## Accepted event local record linkage audit

The **Accepted Accounting record links** section is a separate, permission-gated,
read-only `GET /integration-review/accepted-linkage-audit` check. It interrogates
the actual Accounting target rows for accepted review events rather than treating
an accepted status as proof that a journal or money transaction exists. It
checks:

- Cash In/Out and settlement: linked MoneyTransaction exists, has the expected
  direction and source amount, and is posted (unless explicitly reversed).
- Journal-only: linked JournalEntry exists and is posted with positive,
  balanced debit and credit totals (or is explicitly reversed).
- Receivable and payable: linked local target record exists; this does **not**
  establish its external settlement, account classification or correct aging.
- Inventory payable adjustment: recorded adjustment / supplier-credit IDs
  resolve to existing local rows. These are not assumed to be direct payable
  foreign keys on the original IntegrationReviewItem.
- Folio charges / reference-only events: no direct financial link is expected;
  they do not count as missing journal exceptions.
- Reversed targets are counted separately rather than automatically labelled
  erroneous; an auditor must inspect their reversal trail and original entries.

The result includes a bounded set of exception identities (no raw payroll
payloads). Source-app permissions are enforced by the same Integration Review
authorization as the inbox. Missing/unavailable checks must never display
zero exceptions. All target lookups are batched and read-only; no journal,
transaction, booking, or balance is automatically changed.

**Limitations:** Local record existence and status checks do not prove upstream
producer outbox completeness, banking settlement, independent financial
reconciliation, balances, or tax compliance. Review the original documents and
reversal history before correcting any financial posting.
