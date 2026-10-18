# Beds24 cancellation synchronization — production runbook

## Why a booking can stay confirmed

Accounting has two different sources of incoming Beds24 events:
1. **Booking Webhook V2** (Beds24 Property Access): payload identifies a booking. Accounting fetches the exact ID and applies cancellations.
2. **Inventory Webhook** (Beds24 Marketplace Webhooks): payload is commonly `{"roomId":"...","propId":"...","action":"SYNC_ROOM"}`. It is only a *room inventory* notification, not a booking update, and Accounting logs it as `webhook_room_sync` with status `ignored`. HTTP 200 on this endpoint does **not** mean a reservation status changed.

The POS/inventory integration worker's `room_charge_bookings` log is not an Accounting Beds24 cancellation reconciliation.

## Configuration

In Beds24, for each property, configure **Booking Webhook V2**, not only Inventory Webhooks, with the Accounting `/api/integrations/beds24/webhook` endpoint and the secret in a supported HTTP header. Do not put credentials in URL query parameters. Confirm the Accounting Beds24 integration is enabled, `webhook_enabled=true`, and `manual_sync_only=false`.

The recovery worker uses the same Accounting settings and token as manual synchronization. It **never** enables an integration that an administrator disabled.

## Recovery job

- `accounting-beds24-reconcile.timer` runs every 30 minutes (with jitter). It is installed and enabled by the exact-SHA deployment.
- It queries Beds24 V2 bookings by `modifiedFrom`, without any arrival or departure filter, paginates up to 20 pages per run, and checks only cancelled statuses.
- It updates only an **existing, unambiguously linked** Accounting booking via the status-only cancellation helper. It never creates bookings, guests, invoices, payment transactions, or folios.
- Initial lookback is 30 days. Thereafter a persisted last-success cursor with a 15-minute overlap helps recover missed webhooks. If API paging or any booking fails, the cursor does not advance, and the next run retries.
- It does **not** reinterpret existing historical payments or accounting reversals. Other statuses are not automatically rewritten by the recovery job.

## Read-only verification on production

```bash
systemctl status accounting-beds24-reconcile.timer --no-pager
systemctl list-timers --all | grep accounting-beds24-reconcile
journalctl -u accounting-beds24-reconcile.service --since '24 hours ago' --no-pager | tail -60
```

For the original missing-cancellation incident, use **Accounting → Integrations → Beds24 → Sync Logs** to inspect `webhook_room_sync`, `booking_cancellation`, `webhook_missing_booking_id`, `booking_upsert`, and `cancellation_reconciliation`. An HTTP 200 by itself cannot establish a booking was updated. Redact credentials and guest details before sharing any diagnostic output.

## Safety / troubleshooting

If the worker fails, inspect the application sync logs and `journalctl` (avoiding PII and credentials). Do not advance the persisted watermark manually. On API rate limits, wait for Beds24 to reset before retrying. If the first run fails with a 20-page limit, arrange a rate-aware backfill/reconciliation plan; **never** discard pages or forcibly advance the cursor.

When checking a real cancellation, verify: Beds24 shows cancelled; Accounting status is cancelled; room occupancy excludes it; guest identities, folios, receipts, and ledger history remain unchanged.
