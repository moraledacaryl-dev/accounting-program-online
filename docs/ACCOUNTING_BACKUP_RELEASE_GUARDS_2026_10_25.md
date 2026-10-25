# Accounting backup and release guards — October 25, 2026

The existing backup script automatically removed database dumps, uploads
archives and sidecars older than 14 days. No approved replacement retention or
offsite policy exists for Accounting. This pass preserves all existing evidence
sets, never rewrites a same-second name, and refuses a backup when less than
4 GiB remains. Space and retention need ongoing owner review; a low-space
failure is deliberately visible in the systemd service result.

The release workflow now holds a host-local lock through preparation and
activation. Standalone backup, activation and rollback use the same lock.
Nested child scripts inherit and validate the descriptor; a second process
gets a busy result instead of interleaving backup, migration or symlink switch.
An atomic sidecar publication completes a new evidence set after the dump and
uploads archive are both checksummed. The database and uploads remain normal
read-only backup sources.

The new Accounting timer runs hourly at minute 30 and shortly after activation.
It remains rooted in the exact active immutable release. The service owns no
financial posting permissions beyond the existing root-operated dump process.
No producer event, journal, payment, cash movement, stock movement, or account
data is created for this backup job.

Isolated Linux tests exercise actual `flock` contention, nested inheritance,
same-second collision, failed dump cleanup, low-disk refusal and preservation
of historical files. These tests use synthetic files and stubbed PostgreSQL
commands; existing PostgreSQL and restore tests retain their own full checks.

This is local-host protection. An independent offsite Accounting copy, owner
retention and formal RPO/RTO need separate evidence. Never count an Operations
bucket key restricted to `operations/` as Accounting coverage. The 166 historic
journal-link exceptions and 22 pending financial reviews remain documentary
business decisions, not backup or deployment defects.
