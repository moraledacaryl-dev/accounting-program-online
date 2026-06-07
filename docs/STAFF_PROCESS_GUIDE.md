# Staff Process Guide

This guide uses only processes that already exist in the accounting program. It is written for staff training, shift work, and simple daily operation.

## Golden Rules

1. Search first before creating a new guest, supplier, product, account, bill, or balance.
2. If something is wrong and Edit is available, use Edit first.
3. Use More only for manager actions like reverse, write off, cancel, or delete.
4. Do not use Post accounting now unless manager/accounting tells you to.
5. Add a note whenever the amount, delivery, count, or payment does not match what was expected.

## Start of Day or Shift

Where to go: `Start of Day`

Steps:

1. Open Start of Day.
2. Check today from the dashboard.
3. Review payments to receive.
4. Review bills to pay.
5. Check deliveries that need receiving.
6. Count active cash drawers, petty cash, or safes.
7. Check banks only when manager asks or when closing a period.

Done when:

- Staff know what needs attention.
- Cash drawers or safes that need counting are counted.
- Urgent payments, bills, and deliveries are visible.

## Receive Payment

Where to go: `Cashflow > To Receive`

Use this when a guest, OTA, event client, company, or group pays an open balance.

Steps:

1. Open To Receive.
2. Find the correct balance.
3. Click Receive or Collect.
4. Enter the amount received.
5. Choose the account where money went, such as cash drawer, bank, or GCash.
6. Choose the method.
7. Add reference if available, such as OR number, check number, or bank reference.
8. Save the payment.

Done when:

- The balance is reduced.
- The money account is updated.

## Create a Balance to Collect Later

Where to go: `Cashflow > To Receive`

Use this when someone owes money but has not paid yet.

Steps:

1. Open To Receive.
2. Click Add Balance to Collect.
3. Enter customer or source.
4. Choose type: guest, OTA, event, or company/group.
5. Enter date, due date, and total amount.
6. Leave Already Collected as 0 if no payment was received yet.
7. Save the balance.

Done when:

- The balance appears in Payments to Receive.

## Record Expense

Where to go: `Cashflow > Money Out`

Use this when money was spent from petty cash, drawer, bank, GCash, card, or another money account.

Steps:

1. Open Money Out.
2. Choose date.
3. Choose account used.
4. Choose area and reason.
5. Enter amount.
6. Choose method.
7. Enter payee or supplier.
8. Add reference if available.
9. Attach proof if available.
10. Save Money Out.

Done when:

- The spending is recorded.
- The money account balance changes.

## Pay Supplier or Bill

Where to go: `Cashflow > To Pay`

Use this when paying an open supplier bill, utility bill, tax payable, payroll/government payable, or service provider bill.

Steps:

1. Open To Pay.
2. Find the bill.
3. Click Pay.
4. Enter amount paid.
5. Choose account used.
6. Choose method.
7. Add reference if available.
8. Save the supplier payment.

Done when:

- The bill balance is reduced.
- The money account is updated.

## Create a Bill to Pay Later

Where to go: `Cashflow > To Pay`

Use this when the business owes money but will pay later.

Steps:

1. Open To Pay.
2. Click Add Bill to Pay.
3. Enter supplier.
4. Choose bill type.
5. Enter bill date, due date, and bill amount.
6. Leave Already Paid as 0 if nothing has been paid yet.
7. Save the bill.

Done when:

- The bill appears in Bills to Pay.

## Receive Delivery

Where to go: `Receiving`

Use this when ordered or delivered items arrive.

Steps:

1. Open Receiving.
2. Enter or open the delivery record.
3. Check supplier, items, quantities, cost, and reference.
4. Keep Create Supplier Bill as Yes if the delivery should become a bill.
5. Post the delivery.

Done when:

- Stock is updated.
- A supplier bill is created when needed.

## Count Cash

Where to go: `Cashflow > Cash Count`

Use this at shift start, shift end, handover, or when manager asks.

Steps:

1. Open Cash Count.
2. Choose the drawer, petty cash, safe, bank, or e-wallet account.
3. Enter date and shift.
4. Enter counted amount.
5. Check the difference shown by the system.
6. Add notes if there is a difference.
7. Save Count.

Done when:

- The count is saved.
- Any difference has a note.

## Transfer Money

Where to go: `Cashflow > Transfers`

Use this when moving money from one account to another, such as drawer to safe or safe to bank.

Steps:

1. Open Transfers.
2. Choose date.
3. Choose From account.
4. Choose To account.
5. Enter amount.
6. Add reference if available.
7. Save Transfer.

Done when:

- Money is moved between accounts in the system.

## Check Banks or Exceptions

Where to go: `Cashflow > Periodic Checks`

Use this for manager review, bank checks, OTA follow-up, or period closing. This is not required every day.

Steps:

1. Open Periodic Checks.
2. Choose Cash, Bank, OTA, To Receive, or To Pay.
3. Review only what needs checking.
4. Follow up unpaid balances, bills, payout variances, or count differences.

Done when:

- Open issues are visible and ready for manager follow-up.

## Repair Old Booking Charge Types

Where to go for all old bookings: `Beds24 Integration > All Old Booking Folio Classification`

Where to go for one booking: `Bookings > open booking > Review Existing Folio Classifications`

Use this when old imported folio rows look like the wrong type, such as a room charge, breakfast, minibar, room service, deposit, payment, refund, or adjustment.

Steps:

1. Run Preview first.
2. Read scanned, eligible, would update, and balance adjustment.
3. Review sample changed lines.
4. Open a specific booking when the change looks unusual.
5. Apply only after manager review.
6. Reopen affected folios and confirm the balance.

Done when:

- Old rows are classified correctly.
- Amounts were not duplicated.
- The folio balance matches the real guest situation.

## POS Limited Connection Process

Where to go: `Dedicated POS`

Use this when the browser, Wi-Fi, or POS server connection is unstable.

Steps:

1. Check the POS sync banner and connection badge.
2. Continue normal selling only when the POS server is reachable.
3. If the server is unreachable, save only an emergency offline draft for order-taking continuity.
4. Do not mark payments, refunds, room charges, or session closes as completed while offline.
5. Restore the draft after connection returns.
6. Save or settle the order normally.

Done when:

- Order details were preserved.
- No payment or folio action was falsely recorded.
- Recovery encoding happens once.

## Booking Sync

Where to go: `Beds24 Integration`

Use this if Beds24 is the main booking source.

Steps:

1. Open Beds24 Integration.
2. Check that sync is healthy.
3. Run manual sync only when needed or instructed.

Done when:

- Staff can rely on updated booking and folio information.

## Bookings, Guests, and Folios

Where to go: `Rooms & Guests`

Use:

- Bookings for reservation work.
- Guests for guest details.
- Room Folios for charges, deposits, payments, refunds, and balances.

Done when:

- Guest records and balances stay connected.

## Events

Where to go: `Events`

Use this for event clients, deposits, balances, add-ons, and notes.

Steps:

1. Create an event record.
2. Create a balance to collect if payment is not yet received.
3. Receive payment from To Receive when the client pays.

Done when:

- Event details and event balances are traceable.

## Inventory and Purchasing

Where to go: `Inventory & Purchasing`

Use:

- Purchase Requests when staff need approval before buying.
- Purchase Orders when ordering from suppliers.
- Receiving when items arrive.
- Inventory Items for item setup.
- Stock Movements for stock history.

Done when:

- Purchasing, delivery, stock, and supplier bills stay connected.

## Payroll and Staff

Where to go: `People & Payroll`

Use:

- Employees for staff records.
- Attendance for attendance input and review.
- Payroll Periods for payroll runs.
- Approvals for items waiting for review.

Done when:

- Staff records, attendance, payroll, and approvals stay connected.

## Restaurant and F&B Setup

Where to go: `Restaurant & F&B`

Use:

- Menu Items for menu setup.
- Menu Categories for menu grouping.
- Recipes for costing and ingredient links.
- Staff Meals for internal meal consumption.

Done when:

- Menu, recipes, and stock logic stay connected to POS and operations.

## Closing or Handover

Use existing pages:

1. Count cash in `Cash Count`.
2. Review payments to receive in `To Receive`.
3. Review bills to pay in `To Pay`.
4. Check delivery records in `Receiving`.
5. Add notes for any issue that needs manager review.

Done when:

- Cash is counted.
- Open issues are visible.
- The next staff member or manager can continue without guessing.
