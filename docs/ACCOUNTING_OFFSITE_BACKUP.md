# Accounting encrypted offsite backup preparation

This release contains an **inactive** upload job. Deploying the application
does not install or enable `accounting-offsite.service` or its timer, create a
Restic repository, upload business data, or delete local/cloud archives.

The job expects the latest complete Accounting `.dump`, `.uploads.tar.gz` and
`.meta` set from the hourly local backup. It rechecks private ownership,
current release SHA, age, size, both SHA-256 values, safe uploads archive
members and the PostgreSQL archive catalog. It uses the same release lock as
the backup and deployment programs. A repeated run for the same source tag
reuses its existing Restic snapshot; it does not upload a duplicate.

The repository is fixed to the separate private Accounting bucket and
`accounting/` prefix in Backblaze US West 004. The Restic process receives
only a minimal environment, with a root-private password file and a
root-private JSON credentials file containing `access_key_id` and
`secret_access_key`. The job refuses an untrusted Restic binary, credentials,
source files or config. It caps each source set at 256 MiB and refuses a new
upload when the Restic logical repository plus reserve would exceed 8 GB.
The Backblaze account's physical version usage can differ from this logical
figure, so its storage cap and alerts must be monitored separately.

The config template remains `enabled: false` and all three operator gates
false. Before activation an owner/operator must:

1. Record the owner-approved 48 hourly, 30 daily, 12 weekly and 12 monthly
   history policy. The Accounting bucket's `accounting/` lifecycle now retains
   hidden prior versions for 7 days; check the effective rule before activation.
2. Generate a separate Accounting Restic encryption password, store its
   independent recovery copy outside the VPS and authorize any root-private
   working copy on the VPS.
3. Install the scoped Accounting B2 key and the config as root-only files;
   verify the key's actual bucket, prefix and capabilities. Never reuse the
   Operations key or expose either secret in logs or CI.
4. Install the service/timer files manually, with the timer still disabled.
   Run the disabled job and check `cloud_requests_sent=false`.
5. Initialize only the intended encrypted repository, run one authorized
   upload, independently download it, and restore the database/uploads and
   application in isolation. Verify checksums and counts without logging
   financial details.
6. Only after cloud recovery succeeds, set the three gates and `enabled` to
   true, enable the hourly timer, and inspect its next successful run and
   Backblaze physical usage. Set `initial_cloud_restore_verified` only after
   the independent restore. The retention job runs a checked dry run by
   default; its `--apply` mode additionally requires that restore gate. Its
   separate weekly timer must be installed/enabled only after a successful
   synthetic retention test and the initial cloud restore. Recheck the first
   real dry run before enabling cleanup.

The upload job never invokes Restic `init`, `forget`, `prune`, `unlock` or a
Backblaze lifecycle API. The separate retention job first validates every
snapshot belongs to the Accounting host/source set, checks repository
metadata, dry-runs the exact policy, and refuses any plan that would remove a
snapshot newer than 48 hours. An actual `forget --prune` is separately gated
and followed by another metadata check. Backblaze's 7-day hidden-version rule
allows cloud space to be reclaimed after Restic pruning; its implementation
does not affect Operations. Restic metadata checks are not full downloads or
restore certifications. Offsite age while healthy is roughly
one hour plus the local/offsite timer offset and execution time; no RPO/RTO
promise follows from this schedule. The local backups remain independent.
