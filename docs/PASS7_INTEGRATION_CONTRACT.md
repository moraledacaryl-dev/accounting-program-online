# Pass 7 Cross-App Financial Intake Contract

Accounting is the financial system of record. Producer applications remain authoritative for their operational records and deliver immutable financial events to Accounting for review.

## Canonical endpoint

`POST /api/integration-review/service-intake`

Authentication uses `X-Integration-Api-Key` and Accounting's production `INTEGRATION_API_KEY` or `INTEGRATION_SECRET`.

## Envelope

```json
{
  "source_app": "pos",
  "source_event_id": "settlement:2026-07-17:register-1",
  "source_entity_type": "register_settlement",
  "source_entity_id": "register-1:2026-07-17",
  "source_revision": 1,
  "financial_effect": "settlement",
  "amount": 12500.00,
  "currency": "PHP",
  "proposed_account_id": 1,
  "proposed_journal": null,
  "proposed_links": {
    "category": "POS Settlement",
    "payment_method": "cash"
  },
  "payload": {},
  "correlation_id": "optional-shared-business-flow-id",
  "idempotency_key": "pos:settlement:2026-07-17:register-1:1"
}
```

## Delivery semantics

- Producers use a durable outbox.
- Delivery is at least once.
- Accounting deduplicates by `idempotency_key` and source app/event/revision.
- Repeated delivery returns the existing review item.
- Corrections retain the same source event ID and increment `source_revision`.
- Producers retry network errors and 5xx responses with exponential backoff.
- Producers treat 2xx as delivered and retain the returned Accounting review-item ID.
- Producers treat 400, 401 and 403 as operator-action failures.

## Financial effects

- `cash_in`
- `cash_out`
- `settlement`
- `journal_only`
- `receivable`
- `payable`
- `folio_charge`
- `reference_only`

Accounting validates every event before acceptance. Acceptance creates exactly one canonical Accounting transaction, journal, payable, receivable or durable reference result.
