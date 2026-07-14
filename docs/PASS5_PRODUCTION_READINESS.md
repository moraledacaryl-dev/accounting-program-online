# Pass 5 Production Readiness

- Journal posting, locking, reversals, and audit history are explicit.
- Trial balance excludes draft journals.
- Legacy operational modules are marked transitional/read-only in Accounting UI.
- Beds24 reset/backfill already requires preview and explicit confirmation.
- Existing payable/receivable pay, reverse, reopen, and write-off endpoints remain authoritative.
- Production deployment requires PostgreSQL backup, migration verification, smoke tests, and role/account-access tests.
