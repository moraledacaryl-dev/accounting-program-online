# Payroll Integration Contract

Accounting receives Staff/Payroll events into an integration review queue. It never final-posts payroll journals automatically.

## Idempotency

`external_source + external_id` is unique. Replays return `already_applied` and must not create duplicate review records or apply balances twice.

## Accepted Events

- `employee.sync`
- `payroll.run.approved`
- `payroll.run.paid`
- `payroll.13th_month.paid`
- `cash_advance.released`
- `cash_advance.repaid`

All events must use `schema_version: "2026-06-v1"` and `external_source: "hidden_oasis_staff_payroll"`.

## Endpoints

- `POST /api/integrations/payroll/employees`
- `POST /api/integrations/payroll/runs`
- `POST /api/integrations/payroll/13th-month`
- `POST /api/integrations/payroll/cash-advance-release`
- `POST /api/integrations/payroll/cash-advance-repayment`
- `GET /api/integrations/payroll/review-queue`

## Accounting Outcomes

`payroll.run.paid` creates a review preview:

- Debit Salaries & Wages Expense; credit Salaries Payable
- Debit Employer Contributions Expense; credit SSS, PhilHealth, and Pag-IBIG Payable
- Debit Salaries Payable; credit SSS, PhilHealth, and Pag-IBIG Payable for employee share
- Credit Employee Cash Advance Receivable when payroll deducts advances
- Credit Payroll Bank/Cash/GCash for net pay release

`payroll.13th_month.paid` previews debit 13th Month Pay Expense and credit Cash/Bank or 13th Month Payable.

`cash_advance.released` previews debit Employee Cash Advance Receivable and credit Cash in Drawer/Bank/GCash.

`cash_advance.repaid` previews debit Salaries Payable and credit Employee Cash Advance Receivable.

`employee.sync` upserts only a safe employee reference: employee code, display name, department, position, role, active status, primary department, and source staff ID.

Review statuses are `For Review`, `Ready to Post`, `Posted`, `Rejected`, `Errors`, and `Already Applied`.
