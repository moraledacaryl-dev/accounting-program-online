# Pass 1 — Application Shell and Access Foundation

Base commit in supplied repository archive: `62cad81`.

## Implemented

- Replaced the old ERP workspace sidebar with the approved Accounting navigation:
  - Main
  - Hotel Operations
  - Finance
  - Setup
- Removed Restaurant, Inventory, and Payroll operational workspaces from primary navigation while preserving all existing routes.
- Added a shared client-side app-shell context so Header, Sidebar, and RouteGuard use one current-user request.
- Added responsive mobile navigation with scrim and drawer behavior.
- Added role-aware navigation using the existing permission service.
- Added Cashier and Auditor permission presets.
- Added new permission scaffolding for Review Inbox, Hotel, Events, Cash & Treasury, Daily Close, reversals, and account-access management.
- Added reusable UI primitives:
  - PageHeader
  - MetricCard
  - StatusBadge
  - LoadingState
  - EmptyState
  - ErrorState
  - PermissionState
- Updated Dashboard workspace links to the approved application structure.
- Applied the approved visual direction to the global application shell.

## Validation

- `npm ci --no-audit --no-fund`: passed
- `npm run build`: passed
- 61 Next.js routes compiled and generated successfully
- Python syntax check for modified backend permission service: passed
- `git diff --check`: passed
- Backend repository currently contains no discovered pytest tests (`pytest` returned no tests collected)

## Deliberately deferred to later passes

- Unified Cash & Treasury route behavior
- Backend financial-account access tables and row-level filtering
- Review Inbox persistence and integration acceptance
- Legacy route read-only banners/deep links
- Money ledger, Daily Close, and reconciliation refactor

These remain later-pass work; Pass 1 provides their navigation and permission foundation without changing current transaction behavior.
