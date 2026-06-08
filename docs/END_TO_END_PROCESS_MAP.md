# Hidden Oasis End-to-End Process Map

## 1. POS Sale To Accounting

Source of truth: POS for order; Accounting for official books. Trigger: POS order finalized. Event: POS sale payload with `external_source=dedicated_pos_cloud`. Receiver: Accounting creates sale/import review with `auto_post_accounting=false`. Approval gate: Accounting review/post. Retry: external ID idempotency. Privacy: no HR data. Tests: sale replay, split tender, inventory behavior.

## 2. POS Refund

Source of truth: POS refund. Trigger: refund approved in POS. Event: refund/cashflow payload. Receiver: Accounting review or outgoing cashflow per existing contract. Approval gate: Accounting review when needed. Retry: refund external ID. Privacy: no payment secrets. Tests: refund replay and room-charge refund exclusion.

## 3. POS Void/Reversal

Source of truth: POS void. Trigger: manager void. Receiver: Accounting reversal only if original sale exists. Approval gate: POS manager approval and Accounting review. Retry: no duplicate reversal. Privacy: no customer PII beyond operational labels. Tests: void contract.

## 4. Drawer/Session Reconciliation

Source of truth: POS session close. Trigger: register close. Event: reconciliation/cash movement payload. Receiver: Accounting reconciliation review; Operations drawer variance alert. Approval gate: Accounting adjustment if needed. Retry: session external ID. Tests: variance and reconciliation replay.

## 5. Room Charge

Source of truth: POS room-charge source record. Trigger: room charge tender. Receiver: front desk/folio pending until posted/settled; Operations sees pending status. Accounting effect: receivable/folio only when confirmed by existing flow. Privacy: avoid guest PII beyond room/operational label. Tests: pending, posted, settled, rejected.

## 6. Attendance And OT

Source of truth: Staff/Payroll. Trigger: biometric/manual logs. Events: attendance exception, OT pending, POS daily context support. Receiver: Operations review/task only. Approval gate: supervisor approval in Staff/Payroll. Accounting effect: none until payroll paid event. Tests: unapproved OT excluded, approved OT included.

## 7. Leave Request

Source of truth: Staff/Payroll leave entitlement. Trigger: leave submitted. Event: leave pending to Operations. Receiver: Operations visibility/task only. Approval gate: Staff/Payroll leave approval. Accounting effect: payroll only. Tests: balance, overuse warning, paid/unpaid leave.

## 8. Cash Advance From Drawer

Source of truth: Staff/Payroll cash advance ledger; POS drawer for cash-out context; Accounting for receivable. Trigger: approved release. Events: `cash_advance.released`, later `cash_advance.repaid`. Approval gate: manager release and Accounting review. Accounting effect: Dr Employee Cash Advance Receivable / Cr Cash; repayment Dr Salaries Payable / Cr Receivable. Retry: advance/repayment IDs. Privacy: no HR notes. Tests: no double count.

## 9. Payroll Cutoff

Source of truth: Staff/Payroll. Trigger: approved attendance/leaves/OT/cash advances/freelance outputs. Event: `payroll.run.paid`. Receiver: Accounting review queue and journal preview; Operations status only. Approval gate: owner approve/pay/lock in Staff/Payroll, Accounting post. Tests: SSS catch-up, PhilHealth/Pag-IBIG basis, locked mutation block.

## 10. 13th Month

Source of truth: Staff/Payroll. Trigger: 13th month paid/locked. Event: `payroll.13th_month.paid`. Receiver: Accounting review item. Accounting effect: Dr 13th Month Pay Expense / Cr Cash/Bank or payable. Tests: basis, adjustment, paid state.

## 11. Annual Review

Source of truth: Staff/Payroll. Trigger: review due/completed. Event: `annual_review.due` or status only. Receiver: Operations dashboard/task. Privacy: no scores, qualitative text, infractions, or memo body. Tests: safe status only.

## 12. Department Request To PR/PO

Source of truth: Operations for request; Accounting for official PR/PO. Trigger: department request approved. Event/status: Accounting PR/PO pending/completed back to Operations. Approval gate: Operations approval then Accounting PR/PO workflow. Tests: no duplicate PR ownership.

## 13. Employee Sync

Source of truth: Staff/Payroll employee identity. Trigger: employee created/status changed. Event: `employee.sync`. Receiver: Operations user mapping, POS cashier mapping, Accounting payee/reference mapping. Privacy: safe identity fields only. Tests: no salary/benefits/government/private data.

## 14. Failed Integration Retry

Source of truth: sending app outbox. Trigger: network/API failure. Receiver: none until retry succeeds. Behavior: mark Failed/Pending Retry and retry with same external ID. Tests: duplicate-safe retry.
