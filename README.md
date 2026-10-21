# Resort Accounting ERP Online

This is the deployment copy for the live Hidden Oasis Accounting ERP.

Live target:

```text
Frontend: https://hiddenoasis.app
Backend:  https://hiddenoasis.app/api
Database: hiddenoasis_erp_live
DB user:  hiddenoasis_erp_app
```

It is deployed together with:

```text
/Users/carylmoraleda/pos-cloud-online
```

Server path:

```text
/opt/accounting-program-online
```

Primary deployment guide:

```text
docs/HIDDENOASIS_LIVE_DEPLOYMENT.md
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
- daily PostgreSQL backups

Accounting remains the source of truth for catalog, categories, item/variant structure, financial accounts, receivables, cashflow, reconciliation, and reports. POS consumes this through `https://hiddenoasis.app/api`.
