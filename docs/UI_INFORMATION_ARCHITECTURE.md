# Accounting Program Information Architecture

This document is the canonical route and terminology contract for the Accounting application.

## Workflow ownership

- **Review Inbox** validates financial events received from connected applications before Accounting accepts, rejects, edits, or retries them.
- **Approvals** authorizes operational or financial actions that require a manager or designated approver.
- **Guest Folios** contain guest stay charges, deposits, payments, refunds, adjustments, and balances.
- **Cash & Treasury** owns money accounts, cash movements, transfers, daily close, and reconciliation.
- **Tax & Period Close** owns BIR books, compliance review, accounting-period locks, and controlled reopening.
- **Fixed Assets** owns capitalization, depreciation, impairment, maintenance, and disposal.
- **Files & Evidence** owns supporting documents linked to operational and accounting records.

## Canonical routes

| Capability | Canonical route | Legacy aliases |
|---|---|---|
| Cash & Treasury | `/cashflow` | `/treasury` |
| Booking Channels | `/booking-channels` | `/channels` |
| Payroll periods | `/payroll-periods` | `/payroll` |
| Menu and recipe maintenance | `/menu-items` | `/recipes` |
| Room types and hotel setup | `/room-types` | `/room-setup` |

Legacy aliases remain as permanent redirects so bookmarks do not break.

## Workspace retirement

The generic `/workspace/*` directory pages duplicated the sidebar and forced users through an extra navigation layer. They now redirect to the primary operational route:

- Rooms → Bookings
- Events → Events
- Restaurant/Breakfast/Cafe/Bar → Restaurant Operations
- Inventory → Inventory Items
- Payroll → Payroll Periods
- Finance → Cash & Treasury
- Settings → System Settings

## Naming rules

1. Use business language first.
2. Do not expose raw payload keys, enum values, IDs, or integration terms as primary labels.
3. Expand underscore and hyphen statuses into title-cased language.
4. Button labels should identify the object and action, for example `Post receipt`, `Approve purchase request`, or `Save room type`.
5. Use one canonical title in navigation, page headers, search results, empty states, and documentation.
