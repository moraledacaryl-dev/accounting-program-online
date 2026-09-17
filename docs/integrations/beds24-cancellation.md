# Beds24 cancellation reconciliation

A cancelled stay is not a reversal of cash received. Cancellation preserves the
original booking amount, guest/link, room/dates/channel, map snapshot, folio lines,
receipts, refunds and ledger records. An ordinary stay balance is no longer
collectible; explicitly classified cancellation/non-refundable charges remain.

## Status-only path

`POST /integrations/beds24/sync/booking/cancellation` accepts an exact `booking_id`
and requires `integrations.sync`. It fetches that ID and applies only an explicit
live cancellation to an existing exact local link. Non-cancelled reservations and
unknown IDs are unchanged. Conflicting maps, dates, rooms or property evidence
fail for review. There is no bulk-import fallback.

Every existing sync entry point also routes cancelled payloads through this path
before guest matching or financial mirroring. Repeat notifications are idempotent.
Cancellation writes an audit log with before/after state. The stored map snapshot
is retained rather than pretending that unrelated fields were refreshed.

Ordinary guest-balance receivables retain gross value and actual amount collected;
the cancelled component is written off with before/after amounts in the sync log.
An explicit cancellation fee may leave a remaining collectible balance. Separate
fee receivables are untouched. Ambiguous allocation across multiple receivables
requires review. Refund/reversal recalculation cannot recreate the room claim.

Folio summaries retain original charges, deposits, payments, refunds and reversals.
They exclude room charges from collectible charges on a cancelled booking. Explicit
`cancellation_fee` and `nonrefundable_charge` lines remain collectible/classified;
the code never invents either from an old room price. Unallocated payments are
shown for refund/retention review. Synthetic prepaid OTA settlement lines remain
in history but are not treated as evidence of cash received or retained.

## Why cancellations were missed

The former webhook route attempted JSON only; parsing failure became `{}`. A
payload with no recognized booking ID then triggered a generic 25-booking full
sync. This neither guaranteed retrieval of the changed/cancelled reservation nor
isolated identity updates. Production logs inspected on 2026-09-18 show this
fallback running, followed by a successful individual manual cancellation sync.
The old logs do not preserve the original request body, so its exact format is
not established by those logs alone.

The webhook now supports JSON and URL-encoded forms, including `bookid` and ID
arrays. Nested guest/invoice IDs are not mistaken for booking IDs. Authenticated
ID-less events are logged and rejected instead of silently syncing other stays.
Failed individual syncs are not acknowledged as success. Configure the Beds24
notification to send the exact booking ID; secrets remain in supported headers.
No periodic full sync or retrospective bulk cancellation job is installed.

## Verification and operational limits

Regression coverage includes corrected/placeholder/stale guest identities,
idempotency, non-cancelled reservations, exact-link mismatch rejection, real
receipts, full refunds, retained fees, unpaid cancellation fees, synthetic OTA
settlements, and dashboard/occupancy/revenue/payout exclusions.

Cancellation does not decide whether an unallocated deposit should be refunded,
transferred to another reservation, or retained. Record the verified refund or
explicit fee separately. It also cannot reconstruct financial lines deleted by
an earlier release; recovering those requires independent source evidence.
