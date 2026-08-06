# Application ownership

Accounting is the financial system of record. Operational source applications own their originating workflows and send approved financial events or references into Accounting.

| Workflow | Authoritative application | Accounting behavior |
| --- | --- | --- |
| Inventory item maintenance | Inventory & Procurement | Historical/read-only transition view |
| Stock movements and reconciliation | Inventory & Procurement | Historical/read-only transition view |
| Suppliers, purchase requests, purchase orders, receiving | Inventory & Procurement | Historical/read-only transition view |
| Menu, recipes, restaurant operations, staff meals | POS Cloud | Historical/read-only transition view |
| Journals, chart of accounts, cash, receivables, payables, tax, reports | Accounting | Full create/update authority |
| Bookings, guests, folios, channel payouts | Accounting until a dedicated hospitality source is formally designated | Full create/update authority |
| Employees, attendance, payroll | Accounting until Staff & Payroll ownership is formally enabled | Full create/update authority |

## Rule

A workflow must have one operational writer. Connected applications may read shared records and submit integration events, but duplicate human mutation paths must not remain enabled in multiple applications.
