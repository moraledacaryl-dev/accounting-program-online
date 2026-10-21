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
