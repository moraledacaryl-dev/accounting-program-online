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

Deployment model:

- Ubuntu 22.04
- PostgreSQL on the same server
- nginx reverse proxy
- Let's Encrypt HTTPS
- systemd services
- daily PostgreSQL backups

Accounting remains the source of truth for catalog, categories, item/variant structure, financial accounts, receivables, cashflow, reconciliation, and reports. POS consumes this through `https://hiddenoasis.app/api`.
