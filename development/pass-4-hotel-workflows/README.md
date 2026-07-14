# Pass 4 — Hotel Workflows Checkpoint

This branch checkpoints the Pass 4 implementation package built on top of the Pass 3 source snapshot.

## Scope

- Expanded booking detail workspace with stay, charges/payments, guest, notes, and Beds24/Operations tabs
- Read-only breakfast status in Accounting; breakfast service remains POS-owned
- Guest duplicate search and merge flow using the existing guest merge endpoint
- Folio line reversal and transfer endpoints
- Folio settlement endpoint with zero-balance/tolerance validation
- Protection against editing/deleting linked, external, closed, or settled folio lines
- Source references displayed on folio lines
- Explicit Events commercial workspace with receivables, linked rooms, and Operations handoff boundaries
- Channel payout settlement posts and links the Accounting result once
- Events navigation changed from the generic workspace route to `/events`

## Validation

- Backend Python compilation passed
- Next.js production build compiled successfully
- All 63 frontend routes generated successfully, including `/events`

## Source package

The complete source archive and patch were generated separately as:

- `accounting-program-pass4.zip`
- `accounting-pass4.patch`

The live `main` branch is newer than the original source snapshot used for these compressed passes. Rebase/adapt this checkpoint carefully before merging; do not overwrite newer source blindly.
