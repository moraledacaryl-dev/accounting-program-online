# Resort Accounting ERP Online

This is the deployment copy for the live Hidden Oasis Accounting ERP.

Live target:

```text
Frontend: https://accounting.hiddenoasis.app
Backend:  https://accounting.hiddenoasis.app/api
Database: hiddenoasis_erp_live
DB user:  hiddenoasis_erp_app
```

It runs on the shared Hidden Oasis VPS alongside the separate POS application.

Server source path and active release pointer:

```text
/opt/accounting-program-online
/opt/accounting-current
```

Current production operations guide:

```text
docs/ACCOUNTING_CURRENT_PRODUCTION.md
```

## Current audit goals and reconciliation status

For the original six-group audit goals, evidence-backed progress, unresolved historical journal links, Beds24 status review, Staff repayment investigation, and financial sign-off criteria, see [Accounting Goal Tracker](docs/ACCOUNTING_GOAL_TRACKER.md). Statuses are a dated snapshot; green CI does not certify physical cash or bank balances.

## Backend tests

From the repository root, run the isolated backend suite with:

```bash
bash scripts/test-backend.sh
```

Production/runtime Python dependencies are installed from `backend/requirements.lock.txt` through `backend/requirements.txt`.

Deployment model:

- Ubuntu 22.04
- PostgreSQL on the same server
- nginx reverse proxy
- Let's Encrypt HTTPS
- systemd services
- hourly local PostgreSQL/uploads backups and encrypted offsite snapshots

Accounting remains the source of truth for catalog, categories, item/variant structure, financial accounts, receivables, cashflow, reconciliation, and reports. POS consumes this through `https://accounting.hiddenoasis.app/api`. The apex `https://hiddenoasis.app` is a static app launcher.
