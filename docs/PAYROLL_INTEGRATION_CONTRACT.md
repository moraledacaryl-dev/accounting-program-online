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
- `GET /api/integrations/payroll/receipts`
- `GET /api/integrations/payroll/receipts/{id}`
- `POST /api/integrations/payroll/receipts/{id}/approve`
- `POST /api/integrations/payroll/receipts/{id}/reject?reason=...`
- `POST /api/integrations/payroll/receipts/{id}/post?confirm=true`

Imports create receipts and review previews only. Posting requires an explicit Accounting action and `confirm=true`; duplicate receipts return `already_applied` without overwriting the original review status.

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

## Sample Payload

```json
{
  "external_source": "hidden_oasis_staff_payroll",
  "external_id": "payroll-run:42:Paid",
  "event_type": "payroll.run.paid",
  "source_record_type": "Payroll Run",
  "source_record_id": 42,
  "generated_at": "2026-06-08T10:30:00+08:00",
  "schema_version": "2026-06-v1",
  "payload": {
    "totals": {
      "gross_pay": 100000,
      "sss_ee": 4500,
      "philhealth_ee": 2500,
      "pagibig_ee": 1000,
      "sss_er": 9000,
      "sss_ec": 300,
      "philhealth_er": 2500,
      "pagibig_er": 1000,
      "cash_advance_deduction": 2000,
      "net_pay": 90000
    }
  }
}
```

Expected preview:

- Dr Salaries & Wages Expense / Cr Salaries Payable
- Dr Employer Contributions Expense / Cr SSS, PhilHealth, and Pag-IBIG Payable
- Dr Salaries Payable / Cr SSS, PhilHealth, Pag-IBIG, Employee Cash Advance Receivable, and Payroll Bank/Cash/GCash

## Validation Errors

Accounting rejects unsupported `external_source`, unsupported `schema_version`, missing required envelope fields, unsupported event types, and unsafe employee sync payloads that cannot be scrubbed. Payroll amount payloads are accepted only from Staff/Payroll approved/paid events.
