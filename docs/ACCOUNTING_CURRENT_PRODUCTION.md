# Accounting current production operations

Verified 2026-10-26. The public Accounting UI is
`https://accounting.hiddenoasis.app`; its API is under the same host at
`/api`. `https://hiddenoasis.app` serves the static Hidden Oasis app launcher.
The live POS `ACCOUNTING_API_BASE` points to
`https://accounting.hiddenoasis.app/api`.

## Release path

Accounting runs on the shared VPS through `accounting-backend.service`,
`accounting-frontend.service` and `accounting-operations-outbox.service`.
`/opt/accounting-current` points to an immutable directory under
`/opt/accounting-releases/<40-character SHA>`. The production deployment
procedure is [Deploy Accounting](../.github/workflows/deploy-accounting.yml):
merge only passing changes, confirm successful exact-main CI and the DR
contract, then dispatch that workflow with the exact main commit SHA. Its
guarded server step holds the release lock, checks capacity, creates a
PostgreSQL/uploads backup, applies migrations as needed, and activates the
release. A green workflow alone is not direct production verification.

After deployment, independently confirm the active symlink and each service's
main process working directory resolve under the requested SHA. Check the
public UI and a JSON health response:

```bash
curl -fsS https://accounting.hiddenoasis.app/api/healthz
curl -fsS https://accounting.hiddenoasis.app/healthz
```

The authenticated `/healthz/details` endpoint is reserved for authorized
operators; do not treat an unauthenticated denial as a failed deployment.

## Backup and recovery state

`accounting-backup.timer` writes separate PostgreSQL custom dumps, uploads
archives and SHA-256 sidecars to `/var/backups/hiddenoasis/accounting` hourly
at minute 30. It preserves historical archives; there is no automatic local
deletion policy.

`accounting-offsite.timer` uploads a fresh verified set to the private,
Accounting-only encrypted Restic repository hourly at minute 40. Its key is
restricted to the Accounting bucket and `accounting/` prefix. A separate
Mac-held recovery copy of the encryption password exists. The operator-gated
configuration and working secrets are root-only and outside the app release.
See [Accounting offsite backup](ACCOUNTING_OFFSITE_BACKUP.md) for the safeguards.

`accounting-offsite-retention.timer` runs weekly on Monday at 04:50 Manila
time. The owner-approved policy keeps 48 hourly, 30 daily, 12 weekly and 12
monthly points, with a 48-hour recent-snapshot guard. The bucket's prior
version lifecycle is seven days. Retention requires a verified cloud restore
gate and performs a validated dry-run plan before any removal.

Useful read-only checks on the VPS:

```bash
readlink -f /opt/accounting-current
systemctl is-active accounting-backend.service accounting-frontend.service accounting-operations-outbox.service
systemctl is-enabled accounting-backup.timer accounting-offsite.timer accounting-offsite-retention.timer
systemctl list-timers --all accounting-backup.timer accounting-offsite.timer accounting-offsite-retention.timer
systemctl show -p Result accounting-backup.service accounting-offsite.service accounting-offsite-retention.service
```

The first independent cloud download and isolated PostgreSQL restore passed
on 2026-10-26. Continue checking the next scheduled runs and shared B2 account
usage; an isolated restore is not a measured full application RTO. Do not run
test financial transactions or bookings to prove backup health.
