# Close Readiness Guide

Use **Reports -> Overview -> Close Readiness** before daily or monthly close.

## Status

- **ready**: No close-blocking exceptions were found for the selected period.
- **review**: Close may continue after manager review of warning items.
- **blocked**: Do not close yet. Critical reconciliation or approval work remains.

## Critical Checks

- **Draft or pending records**: approve, cancel, or correct records before close.
- **Unreconciled cash/bank accounts**: complete daily cash and bank reconciliation first.

## Warning Checks

- **Unposted payroll periods**: post payroll or confirm it belongs outside the selected period.
- **Receivables over 30 days**: review collection notes, settlement status, dispute handling, or write-off context.
- **Payables over 30 days**: review supplier payment timing and hold reasons.

## Informational Checks

- **Low stock items**: review purchasing needs. This does not block financial close by itself.

## Close Routine

1. Set Period Start, Period End, and Aging As Of dates.
2. Click **Refresh**.
3. Resolve all critical checks.
4. Review warnings and document manager decisions.
5. Open **Financial Statements** and confirm Trial Balance is balanced and Balance Sheet check is zero.
6. Export the management CSV for the close folder.
7. Lock/report the period only after the close readiness status is ready or manager-approved review.
