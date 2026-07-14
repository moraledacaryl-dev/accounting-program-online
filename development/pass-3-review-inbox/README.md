# Pass 3 — Review Inbox and Connected-App Intake

This branch preserves the Pass 3 implementation built on top of Pass 2.

## Implemented

- Persistent `integration_review_items` model with source app, event ID, revision, financial effect, proposed result, validation, idempotency, correlation, and accepted-record links
- Idempotent intake endpoint
- Review Inbox list, summary, detail, accept, reject, and retry endpoints
- Cash effects create one Money Transaction linked to the source event
- Journal-only effects create one Journal Entry
- Receivable and payable effects create one open balance
- Reference-only and folio-oriented effects retain source linkage without creating cash
- New `/review-inbox` frontend route with filters, metrics, review drawer, account selection, acceptance, rejection, and retry
- Primary navigation now links Review Inbox to the dedicated route
- Frontend API functions for the complete review workflow

## Validation

- Backend Python compilation passed
- Next.js production build compiled successfully
- All routes were generated, including `/review-inbox`

## Important integration note

The live `main` branch had moved beyond the original ZIP snapshot used for the implementation passes. The pass is preserved as a reviewable development package and must be adapted/rebased against the latest application before merge.

Nothing in this branch is deployed or merged to `main`.
