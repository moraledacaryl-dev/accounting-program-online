# Pass 7 production activation

This runbook activates the cross-application financial event flow after the Pass 7 adapters are deployed.

## System ownership

- Accounting owns the Review Inbox, approval, posting, money ledger, payables, receivables, and financial audit trail.
- Staff/Payroll publishes payroll and cash-advance financial events.
- POS publishes settlements, refunds, room charges, transfers, order references, void references, and register reconciliation.
- Inventory publishes goods receipts, procurement references, production valuation references, and POS consumption/reversal references.
- Operations Command Center is a review consumer only; it must not create duplicate financial events.

## Required production values

Use one strong shared integration secret where the applications already share the Accounting integration credential. Never commit the secret.

### Accounting

Set:

```env
PUBLIC_APP_URL=https://accounting.hiddenoasis.app
ACCOUNTING_API_BASE_URL=https://accounting.hiddenoasis.app/api
INTEGRATION_API_KEY=<strong-shared-secret>
```

Confirm the service-intake route is available at:

```text
/api/integration-review/service-intake
```

Confirm the POS compatibility routes are available at:

```text
/api/integrations/pos-review/cashflow
/api/integrations/pos-review/transfer
/api/integrations/pos-review/room-charge
/api/integrations/pos-review/order
/api/integrations/pos-review/order-void
/api/integrations/pos-review/reconciliation
```

### Staff/Payroll

Set the existing Accounting sync variables:

```env
STAFF_PAYROLL_ACCOUNTING_SYNC_URL=https://accounting.hiddenoasis.app
STAFF_PAYROLL_ACCOUNTING_SYNC_TOKEN=<same-accounting-integration-secret>
```

The worker keeps employee identity synchronization on the employee integration route and sends financial events to the canonical service-intake route.

### Inventory

Set:

```env
INTEGRATION_API_KEY=<same-accounting-integration-secret>
INTEGRATION_ENDPOINTS_JSON={"accounting":"https://accounting.hiddenoasis.app"}
```

The Inventory worker appends `/api/integration-review/service-intake` to the Accounting base URL.

### POS

Keep the existing Accounting API base URL and integration credential configured in POS. On application startup, untouched legacy paths are upgraded to the Review Inbox compatibility routes. Explicitly customized paths are preserved.

Verify the stored `accounting_sync` settings contain:

```text
current_erp_cashflow_path=/integrations/pos-review/cashflow
current_erp_transfers_path=/integrations/pos-review/transfer
current_erp_receivables_path=/integrations/pos-review/room-charge
current_erp_sales_path=/integrations/pos-review/order
current_erp_sales_void_path=/integrations/pos-review/order-void
current_erp_reconciliation_path=/integrations/pos-review/reconciliation
```

## Deployment order

1. Deploy Accounting first.
2. Run Accounting migrations and confirm health checks.
3. Deploy Inventory and restart its integration worker.
4. Deploy Staff/Payroll and restart its outbox worker.
5. Deploy POS and restart it so the route migration runs.
6. Deploy Operations Command Center only after the producer systems are stable.

Do not enable producer delivery before Accounting is reachable and its integration secret is configured.

## Acceptance events

Use non-production or clearly marked test records where possible.

1. Staff: approve a small test payroll run and confirm one payable Review Inbox item.
2. Staff: mark the same test payroll paid and confirm one cash-out item linked to the payroll run.
3. Inventory: post one goods receipt and confirm one payable item with the accepted quantity × unit cost total.
4. POS: finalize one cash order and confirm the cash-in and order reference items.
5. POS: create one room charge and confirm a receivable item, not cash-in.
6. POS: void one finalized order and confirm one order-void reference item.
7. POS: close one register session and confirm one reconciliation reference.
8. Inventory: process the POS sale consumption and confirm the Inventory-owned COGS reference; ensure POS did not create a duplicate COGS item.

## Idempotency and replay checks

For each acceptance event:

1. Record the producer event ID and idempotency key.
2. Retry the same outbox event without changing the source record.
3. Confirm Accounting returns or records the existing Review Inbox item rather than creating a duplicate.
4. Confirm producer retry count and response capture are updated normally.
5. Confirm no duplicate money-ledger entry, payable, receivable, or journal proposal is created.

## Failure handling

- A producer delivery failure must remain in its durable outbox and follow normal retry/backoff behavior.
- Exhausted retries must enter the producer's dead-letter or attention state.
- Do not manually create replacement financial records while the original event remains retryable.
- After correcting configuration, replay the original event so its idempotency key remains authoritative.
- Never delete failed outbox rows merely to clear a dashboard.

## Go-live sign-off

Go live only after all of the following are true:

- Accounting health checks pass and migrations are current.
- Integration secrets are configured and are not placeholders.
- Each producer can reach Accounting over HTTPS.
- All acceptance events appear in the Review Inbox with the correct financial effect.
- Replaying each test event does not create duplicates.
- POS room charges are receivables, not cash receipts.
- Inventory is the sole owner of stock consumption and COGS references.
- Review Inbox approval and rejection permissions are verified with a non-owner account.
- Outbox retry and dead-letter monitoring is visible to operations staff.

## Rollback

If a producer creates malformed review items:

1. Stop that producer's worker or disable its Accounting destination.
2. Leave its outbox rows intact.
3. Reject malformed Review Inbox items; do not post them.
4. Deploy the corrected adapter.
5. Replay the original outbox events.
6. Verify idempotency and links before re-enabling normal delivery.
