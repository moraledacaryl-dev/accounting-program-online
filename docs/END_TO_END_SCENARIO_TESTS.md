# Hidden Oasis End-to-End Scenario Tests

Use separate databases for Accounting, POS, Operations, and Staff/Payroll. Each app keeps its own login.

## 1. Normal POS Sale to Accounting

Create a paid POS order, sync it to Accounting, verify Accounting creates one sale/import review record, then replay the POS event and verify no duplicate.

## 2. POS Refund

Refund a paid POS order, sync the refund, verify Accounting records an outgoing cashflow/review item and replay is idempotent.

## 3. Cash Drawer Close

Close a POS register session with expected/actual cash, sync reconciliation, verify Accounting receives one drawer reconciliation pending review and Operations shows a drawer variance alert if nonzero.

## 4. Room Charge Flow

Pay a POS order by room charge, verify POS marks it pending front-desk post, Accounting receives room-charge receivable context, and Operations shows pending room charges.

## 5. Attendance and OT Approval

Create Staff/Payroll time logs with attendance exceptions and detected OT, approve/review in Staff/Payroll, send Operations snapshot, verify Operations counts update and does not compute payroll.

## 6. Leave Request Approval

Create a leave request, send pending event to Operations, convert to a task/approval if needed, then approve in Staff/Payroll and verify payroll uses Staff/Payroll source data only.

## 7. Cash Advance Release and Repayment

Release a staff cash advance, send Accounting release event, verify debit Employee Cash Advance Receivable / credit cash-bank-GCash preview. Deduct repayment in payroll, send repayment event, verify debit Salaries Payable / credit Employee Cash Advance Receivable preview.

## 8. Full Payroll Computation and Approval

Compute payroll in Staff/Payroll, run QA, approve/pay, send payroll event to Accounting, verify employer contribution lines, employee share deductions, net pay release, idempotency, and no final posting until Accounting review approval.

## 9. 13th Month Payment

Create/pay 13th month run, send event to Accounting, verify debit 13th Month Pay Expense and credit Cash/Bank or 13th Month Payable preview.

## 10. Annual Review

Mark annual review due in Staff/Payroll, send Operations review event, verify Operations stores safe status only and no scores/private notes.

## 11. Department Request to PR/PO

Create an Operations request, approve it, create Accounting PR/PO status events, and verify Operations dashboard shows pending PR/PO approvals.

## 12. Employee Sync Propagation

Send `employee.sync` from Staff/Payroll to Accounting and Operations. Verify only safe identity fields are stored and credentials/payroll details are untouched.

## 13. Failed Integration Retry

Generate a valid Staff/Payroll payload, simulate Accounting endpoint unavailable, confirm outbox marks Failed/Pending Retry, retry later, and verify receiver idempotency prevents duplicates.

## 14. Launcher Routing

Open `https://hiddenoasis.app`, verify four static launcher cards, confirm each opens its subdomain, and confirm each app keeps its own login with no shared session.

## Current Execution Status

- Automated local unit/smoke coverage passed for Staff/Payroll.
- Backend syntax checks passed for touched Accounting, POS, and Operations Python files.
- Full pytest and frontend build/lint checks were not executed because `pytest` and `node` are missing in the shell environment.
- Real browser/device E2E scenarios remain manual next-stage validation.
