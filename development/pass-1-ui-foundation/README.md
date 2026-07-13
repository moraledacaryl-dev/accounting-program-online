# Accounting Pass 1 — preserved development package

This branch preserves the Pass 1 UI and permissions work generated from the supplied Accounting source snapshot.

## Important

The live `main` branch had moved beyond the source snapshot used to generate Pass 1. To avoid overwriting newer code, the changes were stored as a split patch package instead of being applied directly.

Files:

- `accounting-pass1.patch.part-00`
- `accounting-pass1.patch.part-01`
- `accounting-pass1.patch.part-02`
- `accounting-pass1.patch.part-03`
- `accounting-pass1.patch.part-04`

Concatenate the parts in numeric order to reconstruct `accounting-pass1.patch`, then rebase or manually adapt the changes against the current application before committing production source changes.

## Scope preserved

- New Accounting application shell
- Final sidebar/navigation structure
- Responsive desktop/tablet/mobile behavior
- Role-aware navigation scaffolding
- Cashier and Auditor role presets
- Review Inbox, Hotel Operations, Cash & Treasury, Daily Close, reversal, and account-access permission scaffolding
- Dashboard workspace changes
- Shared loading, empty, error, and permission-state UI

## Safety

Nothing on this branch is deployed. `main` and production are unchanged. The package should be adapted against the current codebase before opening a production-ready implementation PR.
