# Manager Setup Guide

This is the manager-side setup guide for the accounting program. It explains how to prepare the system before staff use it daily.

Use this order when setting up the property. Do not jump straight into daily transactions until the basic setup is complete.

## Setup Order

1. Users and permissions
2. Company/system settings
3. Cash, bank, drawer, safe, and e-wallet accounts
4. Chart of accounts and account mapping
5. Rooms, rates, channels, and Beds24 sync
6. Suppliers, inventory, purchasing, and receiving setup
7. Menu categories, menu items, recipes, and F&B setup
8. Payroll setup
9. BIR/reporting setup
10. Staff process training
11. First live day checks

## 1. Create Users and Roles

Where to go:

- `Settings > Users`
- `Settings > Roles & Permissions`

Steps:

1. Create one user per staff member.
2. Do not let staff share one login if you want traceable activity.
3. Create roles based on actual work:
   - Front Desk
   - Cashier
   - Purchasing
   - Inventory
   - Payroll
   - Finance
   - Manager
   - Admin
4. Give staff only the pages they need.
5. Give reverse, delete, posting, BIR, chart, account mapping, and system settings only to manager/admin/accounting.

Manager rule:

- Staff should be able to create and edit normal records.
- Manager should control deleting, reversing, write-off, posting, permissions, and setup.

Done when:

- Every staff member has their own login.
- Staff can only see the pages needed for their job.

## 2. System Settings

Where to go:

- `Settings > System Settings`

Steps:

1. Review workflow defaults.
2. Decide which actions require approval.
3. Confirm system-wide controls before staff start using the system.
4. Keep settings conservative during the first live weeks.

Done when:

- Approval and workflow behavior is clear.
- Staff do not accidentally get manager-level controls.

## 3. Set Up Cashflow Accounts

Where to go:

- `Finance & Accounting > Cashflow > Accounts`

Create accounts for real money locations:

- Front desk drawer
- Restaurant drawer
- Petty cash
- Main safe
- Bank accounts
- GCash or other e-wallets
- Credit card clearing account if needed
- OTA payout clearing if needed

Steps:

1. Open Cashflow Accounts.
2. Create Default Accounts if useful.
3. Edit names to match how staff speak.
4. Set account type correctly:
   - Cash drawer
   - Petty cash
   - Safe
   - Bank
   - E-wallet
5. Turn Count Daily on for active drawers and safes that must be counted each shift/day.
6. Keep bank checks periodic unless the operation needs daily bank review.

Done when:

- Staff can choose the correct account when receiving or spending money.
- Cash Count shows the accounts that actually need counting.

## 4. Chart of Accounts and Account Mapping

Where to go:

- `Settings > Chart of Accounts`
- `Settings > Account Mapping`

What this controls:

- Chart of Accounts is the accounting structure.
- Account Mapping tells the system where operational activity posts.

Steps:

1. Review the chart of accounts.
2. Create or adjust accounts only if accounting needs them.
3. Map common operational flows:
   - Cash received
   - Bank received
   - GCash/e-wallet received
   - Cash expenses
   - Supplier bills
   - Guest balances
   - OTA receivables
   - Event receivables
   - Payroll liabilities
   - Tax/BIR-related flows
4. Test one sample transaction before going live.
5. Keep Post accounting now restricted until mappings are trusted.

Manager rule:

- Staff should not decide accounting accounts while serving guests.
- Staff records the real operation; mapping handles the accounting structure.

Done when:

- Transactions can be recorded by staff without them choosing debit/credit accounts.

## 5. Rooms, Rates, Channels, and Beds24

Where to go:

- `Rooms & Guests`
- `Rooms`
- `Room Types`
- `Rate Plans`
- `Booking Channels`
- `Room Package Rules`
- `Settings > Beds24 Integration`

Recommended if Beds24 is the main booking source:

- Beds24 owns booking creation.
- Accounting program receives/syncs bookings and folio information.
- Staff should not double-create bookings unless manager says so.

Steps:

1. Set up Room Types.
2. Set up Rooms.
3. Set up Rate Plans.
4. Set up Booking Channels.
5. Set up Room Package Rules if packages/inclusions matter.
6. Open Beds24 Integration.
7. Enter/check integration settings.
8. Test connection.
9. Run a small sync test.
10. Check that guests, bookings, and folio mirrors look correct.

Done when:

- Front desk can trust synced booking information.
- Room and rate setup matches the actual property.

## 6. Guests, Folios, and Balances

Where to go:

- `Rooms & Guests > Guests`
- `Rooms & Guests > Room Folios`
- `Cashflow > To Receive`

Setup decisions:

1. Decide when staff should create a guest manually.
2. Decide when charges go to folio.
3. Decide when an unpaid balance becomes a balance to collect.
4. Decide how deposits and refunds are handled.

Manager rule:

- If a balance is not paid immediately, create or confirm it in To Receive.
- For room charges, keep folio and receivable behavior consistent.

Done when:

- Guest balances do not disappear in notes or manual lists.
- Unpaid balances are visible in To Receive.

## 7. Events Setup

Where to go:

- `Events`
- `Cashflow > To Receive`

Steps:

1. Use Event Records for client details, event notes, dates, and add-ons.
2. Use To Receive for event deposits and unpaid event balances.
3. Receive payments from To Receive when the client pays.
4. Use notes for contract, package, or special arrangement details.

Done when:

- Event details and payment follow-up are not mixed into random notes.

## 8. Suppliers, Inventory, and Purchasing

Where to go:

- `Inventory & Purchasing`
- `Suppliers`
- `Inventory Items`
- `Purchase Requests`
- `Purchase Orders`
- `Receiving`
- `Stock Movements`

Setup steps:

1. Create suppliers.
2. Create inventory items.
3. Set units, reorder levels, and item names clearly.
4. Decide when Purchase Requests are required.
5. Decide who can approve Purchase Requests.
6. Use Purchase Orders for supplier ordering.
7. Use Receiving when items arrive.
8. Keep Create Supplier Bill as Yes when the delivery should be paid later.

Manager rule:

- Do not pay suppliers from memory. Use To Pay when a bill exists.
- Receiving should be the bridge between delivered stock and supplier bills.

Done when:

- Received items update stock.
- Supplier bills are created when needed.
- Managers can see purchasing history.

## 9. Restaurant and F&B Setup

Where to go:

- `Restaurant & F&B`
- `Menu Categories`
- `Menu Items`
- `Recipes`
- `Staff Meals`

Setup steps:

1. Create menu categories first.
2. Create menu items.
3. Keep simple items simple.
4. Use variants/options only where needed.
5. Add recipes or ingredient links when stock/cost control matters.
6. Use Staff Meals for internal consumption.

Manager rule:

- Accounting program owns the source menu/category/item structure.
- POS should consume the synced menu structure, not create a conflicting product setup.

Done when:

- Menu structure is clean enough for POS sync.
- Recipes and stock deduction can be trusted where configured.

## 10. Payroll Setup

Where to go:

- `People & Payroll`
- `Employees`
- `Attendance`
- `Payroll Periods`
- `Approvals`

Setup steps:

1. Create employees.
2. Check employee details.
3. Decide attendance input method.
4. Set payroll period rules.
5. Create a test payroll period.
6. Review approval flow before posting anything final.

Done when:

- Employees, attendance, payroll periods, and approvals are connected.

## 11. BIR and Reporting Setup

Where to go:

- `Finance & Accounting > BIR`
- `Finance & Accounting > Reports`
- `Settings > Account Mapping`

Setup steps:

1. Decide which transaction types should be BIR-included.
2. Keep internal-only transactions separate from BIR-ready entries.
3. Review BIR candidates before locking or posting.
4. Use reports to review totals before period close.
5. Let manager/accounting control BIR and period locks.

Done when:

- Staff can record daily operations without accidentally affecting statutory output.
- Manager/accounting can review and lock periods intentionally.

## 12. Cash and Bank Control

Where to go:

- `Cashflow > Cash Count`
- `Cashflow > Periodic Checks`
- `Cashflow > Transfers`
- `Cashflow > Account History`

Daily:

1. Count active drawers, petty cash, and safes.
2. Add notes for differences.
3. Move money using Transfers when cash goes from drawer to safe or safe to bank.

Periodic:

1. Check banks.
2. Review OTA payouts.
3. Review payments to receive.
4. Review bills to pay.
5. Review count differences.

Manager rule:

- Banks do not need to be reconciled daily unless the operation requires it.
- Drawers and safes should be counted based on shift or handover policy.

Done when:

- Cash is controlled daily.
- Bank checks are controlled periodically.

## 13. Train Staff

Where to go:

- `Staff Guide`
- `Start of Day`

Training checklist:

1. Show staff Start of Day.
2. Show Receive Payment.
3. Show Record Expense.
4. Show Pay Supplier.
5. Show Receive Delivery.
6. Show Count Cash.
7. Explain that More is for manager actions.
8. Explain that Post accounting now is not a normal staff action.
9. Explain that notes are required when something does not match.

Done when:

- Staff can follow the process without knowing accounting terms.

## 14. First Live Day Checklist

Before opening:

1. Users and permissions are correct.
2. Cashflow accounts exist.
3. Drawers and safes are set to count daily if needed.
4. Rooms and booking sync are checked.
5. Suppliers and inventory items needed for operations exist.
6. Menu categories/items needed by POS exist.
7. Staff know Start of Day and Staff Guide.

During the day:

1. Use To Receive for collections.
2. Use Money Out for expenses.
3. Use To Pay for supplier bills.
4. Use Receiving for deliveries.
5. Use Cash Count for drawers and safes.

End of day or shift:

1. Count cash.
2. Review Payments to Receive.
3. Review Bills to Pay.
4. Review deliveries posted today.
5. Review count differences.
6. Leave notes for manager/accounting.

Done when:

- The next staff member can continue without guessing.
- Manager can review exceptions instead of reconstructing the day from memory.

## What Managers Should Avoid

Avoid:

- Giving all staff admin permissions.
- Creating duplicate accounts for the same drawer, bank, or GCash.
- Creating duplicate products in POS and accounting.
- Letting staff choose accounting posting accounts manually during service.
- Paying suppliers without a bill when the bill should exist.
- Receiving stock without checking quantity and supplier.
- Closing a period before reviewing BIR/reporting output.

## Best Next Manager Feature

The most useful next feature would be a logged Manager Checklist:

- Opening checklist
- Closing checklist
- Cash count review
- Delivery review
- Receivable/payable follow-up
- Exception notes
- Manager sign-off

That would turn this document into a controlled daily operating process inside the app.
