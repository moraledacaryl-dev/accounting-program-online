# Form Field Guide

This guide explains what staff and managers should enter in the main forms that already exist in the accounting program.

Use this together with:

- `STAFF_PROCESS_GUIDE.md`
- `MANAGER_SETUP_GUIDE.md`

## General Rules for All Forms

1. Required fields usually control saving. Fill them first.
2. Dates should match the real business date, not always the date you are entering the record.
3. Amounts should be the actual peso amount before saving.
4. Reference means proof or trace number, such as OR number, invoice number, check number, bank reference, delivery receipt, PO number, or OTA reference.
5. Notes should be used when something is not normal, not just for decoration.
6. Include in BIR should be Yes only when manager/accounting wants that record included for BIR output.
7. Post accounting now is normally No for staff. Use Yes only when manager/accounting has approved the posting setup.
8. More actions like reverse, delete, write off, and cancel are manager actions.

## Payments to Receive - Add Balance to Collect

Where: `Cashflow > To Receive`

Use this when someone owes money and will pay later.

| Field | What to enter | Staff rule |
| --- | --- | --- |
| Customer / Source | Guest name, OTA name, event client, company, or group name | Use the name staff will search later |
| Type | Guest balance, OTA receivable, Event balance, or Company / group billing | Pick why they owe money |
| Date | Date the balance was created | Usually today or the transaction date |
| Due Date | Date payment is expected | Leave blank only if no due date exists |
| Total Amount | Full amount to collect | Do not subtract payments here |
| Already Collected | Amount already received before this record | Use 0 if nothing has been collected |
| Status | Open, Partially paid, or Paid | Usually Open for new balances |
| Include in BIR | Yes or No | Ask manager/accounting if unsure |
| Notes | Explanation, booking reference, event details, or special agreement | Required when arrangement is unusual |

Done correctly when:

- The balance appears in Open Payments to Receive.
- Staff can find it later by customer/source.

## Receive Payment Popup

Where: `Cashflow > To Receive > Collect`

Use this when payment is received for an open balance.

| Field | What to enter | Staff rule |
| --- | --- | --- |
| Amount | Amount actually received now | Can be full or partial |
| Account | Where the money went | Example: Front Desk Drawer, Bank, GCash |
| Method | Cash, GCash, Card, Bank Transfer, or OTA Payout | Match the real payment method |
| Reference | OR, check, bank ref, card ref, OTA payout ref | Add whenever available |
| Note | Short explanation | Add if partial, unusual, or corrected |
| Accounting options > Posting | Save payment first or Post accounting now | Staff normally leave as Save payment first |

Done correctly when:

- The open balance is reduced.
- The selected account receives the money.

## Bills to Pay - Add Bill to Pay

Where: `Cashflow > To Pay`

Use this when the business owes money and will pay later.

| Field | What to enter | Staff rule |
| --- | --- | --- |
| Supplier | Supplier, utility company, government agency, or service provider | Use the official supplier name when possible |
| Type | Supplier bill, Utility bill, Payroll / government payable, Tax payable, Service provider bill | Pick why the business owes money |
| Bill Date | Date of the bill or invoice | Use invoice date if available |
| Due Date | Date payment is due | Important for follow-up |
| Bill Amount | Full amount of the bill | Do not subtract payments here |
| Already Paid | Amount already paid before this record | Use 0 if unpaid |
| Status | Open, Partially paid, or Paid | Usually Open for new bills |
| Include in BIR | Yes or No | Ask manager/accounting if unsure |
| Notes | Invoice details, delivery details, terms, or issue | Add supplier invoice details here |

Done correctly when:

- The bill appears in Open Bills to Pay.

## Pay Supplier Popup

Where: `Cashflow > To Pay > Pay`

Use this when paying an open bill.

| Field | What to enter | Staff rule |
| --- | --- | --- |
| Amount | Amount actually paid now | Can be full or partial |
| Account | Where the money came from | Example: Main Bank, Petty Cash, GCash |
| Method | Cash, GCash, Card, Bank Transfer, or OTA Payout | Match the real payment method |
| Reference | Check number, bank ref, OR, supplier receipt | Add whenever available |
| Note | Short explanation | Add if partial, unusual, or corrected |
| Accounting options > Posting | Save payment first or Post accounting now | Staff normally leave as Save payment first |

Done correctly when:

- The bill balance is reduced.
- The selected account is reduced.

## Money In

Where: `Cashflow > Money In`

Use this for incoming money that is not handled through the Collect popup, or for direct money-in recording.

| Field | What to enter | Staff rule |
| --- | --- | --- |
| Date | Date money was received | Use actual receipt date |
| Account | Where money went | Drawer, bank, safe, GCash, etc. |
| Area | Business area related to the money | Rooms, Restaurant, Events, Finance, etc. |
| Category | Main reason for the money | Use the closest correct category |
| Subcategory | More specific reason | Choose based on manager setup |
| Detail | Detailed type | Choose based on manager setup |
| Amount | Amount received | Must be more than 0 |
| Method | Cash, card, GCash, bank transfer, etc. | Match real method |
| Payer / Customer | Who paid | Guest, company, OTA, event client |
| Reference No | OR, bank ref, card ref, check no. | Add whenever available |
| Linked Receivable | Open balance being paid | Use if the payment relates to an existing balance |
| Include in BIR | Yes or No | Ask manager/accounting if unsure |
| Attachment | Proof of payment | Upload if available |
| Accounting options > Post accounting now | Yes or No | Staff normally leave No |
| Notes | Reason or unusual detail | Add if anything needs explanation |

Done correctly when:

- Money is recorded in the selected account.
- Any linked balance is connected.

## Money Out

Where: `Cashflow > Money Out`

Use this for expenses or outgoing money.

| Field | What to enter | Staff rule |
| --- | --- | --- |
| Date | Date money was spent | Use actual spending date |
| Account | Where money came from | Petty cash, drawer, bank, GCash, etc. |
| Area | Business area related to the spending | Finance, Procurement, Utilities, Payroll, etc. |
| Category | Main expense reason | Use the closest correct category |
| Subcategory | More specific reason | Choose based on manager setup |
| Detail | Detailed type | Choose based on manager setup |
| Amount | Amount spent | Must be more than 0 |
| Method | Cash, card, GCash, bank transfer, etc. | Match real method |
| Payee / Supplier | Who received the money | Supplier, employee, utility company, etc. |
| Reference No | OR, invoice, check, bank ref | Add whenever available |
| Linked Payable | Open bill being paid | Use if paying an existing bill |
| Include in BIR | Yes or No | Ask manager/accounting if unsure |
| Attachment | Receipt or proof | Upload if available |
| Accounting options > Post accounting now | Yes or No | Staff normally leave No |
| Notes | Reason or unusual detail | Add if anything needs explanation |

Done correctly when:

- Spending is recorded.
- The selected account is reduced.

## Transfers

Where: `Cashflow > Transfers`

Use this when moving money between accounts, such as drawer to safe or safe to bank.

| Field | What to enter | Staff rule |
| --- | --- | --- |
| Date | Date money moved | Use the real transfer date |
| From | Account money came from | Example: Front Desk Drawer |
| To | Account money went to | Example: Main Safe |
| Amount | Amount moved | Must be more than 0 |
| Reference | Deposit slip, transfer ref, handover ref | Add if available |
| Accounting options > Post accounting now | Yes or No | Staff normally leave No |
| Notes | Reason or handover detail | Add who handled it if useful |

Done correctly when:

- One account decreases.
- The other account increases.

## Cash Count

Where: `Cashflow > Cash Count`

Use this for drawer, petty cash, safe, bank, or e-wallet count/check.

| Field | What to enter | Staff rule |
| --- | --- | --- |
| Account | Drawer, safe, bank, petty cash, or e-wallet being counted | Pick the exact account |
| Date | Date of count | Use shift/date being counted |
| Shift | Day, Night, AM, PM, or handover name | Use a consistent shift label |
| Counted Amount | Actual counted money | Count first, then enter |
| Status | Open, Counted, Reviewed, Closed, Difference needs review | Staff usually use Counted |
| Notes | Explanation of difference or handover | Required if there is a difference |

System preview fields:

| Field | Meaning |
| --- | --- |
| Opening | Starting balance before movement |
| Expected In | Money expected to come in |
| Expected Out | Money expected to go out |
| Expected | System expected closing balance |
| Difference | Counted amount minus expected amount |

Done correctly when:

- Count is saved.
- Any difference has a note.

## Cashflow Accounts

Where: `Cashflow > Accounts`

Manager setup form for drawers, banks, safes, petty cash, and e-wallets.

| Field | What to enter | Manager rule |
| --- | --- | --- |
| Name | Staff-friendly name | Example: Front Desk Drawer |
| Code | Short code | Leave blank if auto-generated is okay |
| Account Type | Cash drawer, petty cash, safe, bank, or e-wallet | Must match real account type |
| Subtype | Extra label | Example: BDO, Maya, Drawer 1 |
| Department | Area using it | Front Desk, Restaurant, Admin |
| Currency | Currency code | Usually PHP |
| Opening Balance | Starting balance at setup | Use the real opening amount |
| Active | Yes or No | No hides from daily use |
| Count Daily | Yes or No | Yes for drawers/safes counted daily |
| Notes | Setup detail | Use for manager context |

Done correctly when:

- Staff can choose the correct account in payments, expenses, transfers, and counts.

## Receiving

Where: `Receiving`

Use this when delivery arrives.

Header fields:

| Field | What to enter | Staff rule |
| --- | --- | --- |
| Receiving No | Delivery receiving number | Leave blank if auto-generated is okay |
| Receiving Date | Date items arrived | Use actual delivery date |
| Supplier | Supplier who delivered | Required for supplier tracking |
| Purchase Order | Related PO, if any | Pick PO to auto-fill lines |
| Status | Draft, posted, reversed | Use Draft while checking, Posted when final |
| Reference No | Delivery receipt, invoice, supplier ref | Add if available |
| Post to Stock | Yes or No | Usually Yes when stock should increase |
| Create Supplier Bill | Yes or No | Usually Yes if supplier must be paid |
| Notes | Delivery issue or explanation | Add if quantity/cost differs |

Line fields:

| Field | What to enter | Staff rule |
| --- | --- | --- |
| Inventory Item | Item received | Pick from inventory list |
| Description | Item description | Auto-fills when item is selected, can clarify |
| Qty Received | Actual quantity received | Count actual received quantity |
| Unit | Unit used | Example: kg, pcs, bottle |
| Unit Cost | Cost per unit | Use invoice or agreed cost |
| Notes | Line-specific issue | Add if damaged, short, substituted |

Done correctly when:

- Stock updates if Post to Stock is Yes.
- Supplier bill is created if Create Supplier Bill is Yes.

## Purchase Request

Where: `Inventory & Purchasing > Purchase Requests`

Use this when staff request items before ordering.

Header fields:

| Field | What to enter | Rule |
| --- | --- | --- |
| Request No | Request number | Leave blank if auto-generated is okay |
| Request Date | Date request was made | Usually today |
| Needed By | Date items are needed | Important for urgency |
| Department | Department requesting | Kitchen, Housekeeping, Front Desk, etc. |
| Supplier | Preferred supplier if known | Optional |
| Status | Draft, submitted, approved, rejected, converted, cancelled | Manager controls approval status |
| Notes | Reason for request | Add context if urgent |

Line fields:

| Field | What to enter | Rule |
| --- | --- | --- |
| Inventory Item | Item requested | Use existing inventory item |
| Description | Item detail | Use when item needs clarification |
| Qty | Quantity requested | Use realistic quantity |
| Unit | Unit requested | pcs, kg, case, bottle, etc. |
| Est. Unit Cost | Estimated cost per unit | Use latest known cost |
| Notes | Special instruction | Brand, quality, substitution, etc. |

## Purchase Order

Where: `Inventory & Purchasing > Purchase Orders`

Use this when ordering from supplier.

Header fields:

| Field | What to enter | Rule |
| --- | --- | --- |
| PO No | Purchase order number | Leave blank if auto-generated is okay |
| PO Date | Date order is made | Usually today |
| Supplier | Supplier being ordered from | Required for real order |
| From Purchase Request | Related request | Use when PO comes from approved PR |
| Status | Draft, issued, partially received, completed, cancelled | Update as order progresses |
| Payment Terms | COD, 15 days, 30 days, etc. | Match supplier terms |
| Expected Delivery | Expected arrival date | Useful for follow-up |
| Notes | Order instruction | Add delivery or substitution rules |

Line fields:

| Field | What to enter | Rule |
| --- | --- | --- |
| Inventory Item | Item ordered | Pick from inventory list |
| Description | Order detail | Auto-fills or clarify |
| Qty Ordered | Quantity ordered | Match supplier order |
| Unit | Unit ordered | pcs, kg, case, etc. |
| Unit Cost | Agreed unit cost | Use quoted cost |
| Notes | Line instruction | Brand, size, quality, etc. |

## Generic Record Form

Where: `Events`, `Restaurant & F&B records`, and other record workspaces

Use this for flexible operational records.

| Field | What to enter | Rule |
| --- | --- | --- |
| Category | Main group | Choose from available setup |
| Subcategory | More specific group | Choose from available setup |
| Detail | Detailed type | Choose from available setup |
| Title | Custom record title | Optional but useful |
| Flow | Income, expense, asset, liability, neutral | Choose the closest business direction |
| Amount | Peso amount | Use 0 or blank when not money-related |
| Quantity | Quantity involved | Optional |
| Unit | Unit of quantity | pcs, pax, kg, nights, etc. |
| Payment | Payment method | Cash, Card, GCash, etc. |
| Channel | Source channel | OTA, direct, event, etc. |
| Counterparty | Guest, supplier, company, or client | Who the record is about |
| Date | Transaction or event date | Use real business date |
| Due | Due date | Use when follow-up is needed |
| Reference | Document reference | Contract, OR, invoice, etc. |
| Status | Draft, For review, Approved, Posted | Manager/accounting controls final status |
| BIR | Internal only, Ready for BIR, Needs review, Posted to BIR | Accounting/manager should decide |
| Notes | Details | Add anything staff need later |

## Bookings

Where: `Rooms & Guests > Bookings`

Use this when manually creating or editing bookings. If Beds24 is the main booking source, managers should decide when manual booking entry is allowed.

| Field | What to enter | Rule |
| --- | --- | --- |
| Find Guest | Search existing guest | Search before creating a new guest |
| Guest Select | Existing guest record | Use if guest already exists |
| Guest Name Snapshot | Guest name shown on booking | Auto/readonly when guest is selected |
| Room Type | Type of room booked | Match booking |
| Room | Specific room | Assign if known |
| Rate Plan | Rate/inclusion plan | Match agreed package |
| Channel | Direct, OTA, corporate, etc. | Match booking source |
| Status | Booking status | Use operational truth |
| Payment Method | Expected or actual method | Use best known method |
| Check In | Arrival date | Required for stay |
| Check Out | Departure date | Required for stay |
| Effective Date | Accounting/effective date | Usually booking date or transaction date |
| Gross Amount | Total booking amount | Before deposits |
| Deposit | Amount already paid | Use 0 if none |
| Breakfast Included | Number of breakfasts included | Based on package/rate |
| Auto Post Accounting | Yes or No | Staff normally leave No |
| Auto Reverse On Cancel | Yes or No | Usually Yes if postings should reverse on cancellation |
| Notes | Special requests or booking notes | Add important operational notes |

Inline Guest fields:

| Field | What to enter |
| --- | --- |
| First Name / Last Name / Full Name | Guest name details |
| Phone / Email | Contact details |
| City | Guest city |
| VIP | Yes only for true VIP |
| Notes | Guest-specific notes |

## Room Folios

Where:

- `Rooms & Guests > Room Folios`
- Individual folio page

Create folio fields:

| Field | What to enter | Rule |
| --- | --- | --- |
| Booking | Booking linked to folio | Use if folio is for a booking |
| Guest override | Guest name if different or manual | Use carefully |
| Folio No | Folio number | Optional if auto-generated |
| Notes | Folio notes | Use for billing instruction |

Folio line fields:

| Field | What to enter | Rule |
| --- | --- | --- |
| Type | Charge, payment, deposit, refund, etc. | Match line purpose |
| Description | What the line is for | Must be understandable |
| Date | Line date | Use actual charge/payment date |
| Quantity | Quantity | Use 1 if not quantity-based |
| Unit Price | Price per unit | Use actual price |
| Amount override | Manual amount | Use only if calculated amount needs override |
| Reference | OR, receipt, booking ref, etc. | Add if available |
| Notes | Explanation | Add for adjustments |

## Rooms Setup

Where: `Rooms`, `Room Types`, `Rate Plans`, `Booking Channels`, `Package Rules`

Room Types:

| Field | What to enter |
| --- | --- |
| Code | Short room type code |
| Name | Room type name |
| Active | Yes if available for use |
| Base Capacity | Normal included pax |
| Max Capacity | Maximum allowed pax |
| Description | Room type description |
| Notes | Internal notes |

Rooms:

| Field | What to enter |
| --- | --- |
| Room No | Physical room number |
| Name | Display name |
| Room Type | Linked room type |
| Floor / Zone | Location |
| View | View or area |
| Status | Available, maintenance, etc. |
| Active | Yes if in use |
| Notes | Internal notes |

Rate Plans:

| Field | What to enter |
| --- | --- |
| Code | Short rate code |
| Name | Rate plan name |
| Room Type | Applicable room type |
| Base Rate | Room price |
| Breakfast Included | Included breakfasts |
| Pax Included | Included guests |
| Active | Yes if available |
| Notes | Rate conditions |

Booking Channels:

| Field | What to enter |
| --- | --- |
| Code | Short channel code |
| Name | Channel name |
| Class | OTA, Direct, Corporate, etc. |
| Settlement Mode | Net payout, direct collect, etc. |
| Default Commission % | Normal commission |
| Prepaid Channel | Yes if guest pays channel first |
| Active | Yes if in use |
| Notes | Channel notes |

Package Rules:

| Field | What to enter |
| --- | --- |
| Name | Package/rule name |
| Room Type | Applicable room type |
| Rate Plan | Applicable rate |
| Included Breakfast | Number included |
| Included Pax | Number included |
| Extra Pax Rate | Additional pax charge |
| Active | Yes if in use |
| Notes | Package conditions |

## Menu and F&B Setup

Where: `Restaurant & F&B`

Menu Categories:

| Field | What to enter |
| --- | --- |
| Category name | Customer/staff-friendly category |
| Optional code | Short code if useful |
| Status | Active or inactive |

Menu Items:

| Field | What to enter | Rule |
| --- | --- | --- |
| Item name | Sellable menu item | Use clear POS-friendly name |
| Service area | Restaurant, cafe, bar, etc. | Determines operational grouping |
| Category | Menu category | Must match category setup |
| Sale price | Selling price | Use current menu price |
| Item notes | Internal notes | Optional |

Recipe fields:

| Field | What to enter |
| --- | --- |
| Ingredient | Inventory item used |
| Quantity | Amount used per menu item |
| Unit | Unit used |

## Inventory Items

Where: `Inventory Items`

| Field | What to enter | Rule |
| --- | --- | --- |
| Name | Inventory item name | Use clear purchasing/stock name |
| Category | Main stock category | Choose correct category |
| Subcategory | More specific category | Choose correct subcategory |
| Unit | Stock unit | pcs, kg, liter, bottle, etc. |
| Reorder level | Minimum stock before reorder | Use realistic threshold |
| Notes | Item notes | Add supplier/quality notes if useful |

## Suppliers

Where: `Suppliers`

| Field | What to enter |
| --- | --- |
| Code | Supplier code, optional if auto-generated |
| Name | Supplier name |
| Type | Produce, utility, service, etc. |
| Category | Supplier category |
| Contact Person | Main contact |
| Phone | Contact number |
| Email | Supplier email |
| Payment Terms | COD, 15 days, 30 days, etc. |
| TIN | Taxpayer number if available |
| Tax ID | Other tax identifier if used |
| Active | Yes if supplier is in use |
| Address | Supplier address |
| Notes | Supplier notes |

## Employees and Attendance

Employees:

| Field | What to enter |
| --- | --- |
| Name | Employee full name |
| Department | Work department |
| Job Title | Position |
| Comp Type | Monthly, Daily, or Hourly |
| Monthly / Rate | Main salary or rate |
| Daily Rate | Daily rate if used |
| Hourly Rate | Hourly rate if used |

Attendance:

| Field | What to enter | Rule |
| --- | --- | --- |
| Employee | Employee worked or absent | Required |
| Work Date | Date worked | Required |
| Day Type | Regular day, rest day, holiday | Use correct labor day type |
| Is Absent | Yes or No | Yes disables time fields |
| Time In | Actual time in | Leave blank if absent |
| Time Out | Actual time out | Leave blank if absent |
| Late (mins) | Late minutes | Use 0 if none |
| Undertime (mins) | Undertime minutes | Use 0 if none |
| OT Hours | Overtime hours | Use approved OT |
| Night Diff Hours | Night differential hours | Use approved ND |
| Leave Type | Leave type if applicable | Optional |
| Notes | Attendance notes | Add explanation for exceptions |

## Payroll Periods

Where: `Payroll Periods`

Header fields:

| Field | What to enter |
| --- | --- |
| Name | Payroll period name |
| Period Start | First date covered |
| Period End | Last date covered |
| Release Date | Pay release date |
| Status | Draft, imported, reviewed, posted, etc. |
| Source | Manual, imported, etc. |
| Notes | Payroll notes |

Line fields:

| Field | What to enter |
| --- | --- |
| Employee Name | Employee |
| Department | Department |
| Regular Amount | Normal pay |
| OT Amount | Overtime pay |
| Holiday Amount | Holiday pay |
| Night Diff | Night differential pay |
| Allowances | Allowances |
| Deductions | Deductions |
| Employer Contribution | Employer-side contribution |
| Gross Pay | Total before deductions |
| Net Pay | Final pay |

## Beds24 Integration

Where: `Beds24 Integration`

Manager-only setup fields:

| Field | What to enter | Rule |
| --- | --- | --- |
| Enabled | Yes or No | Yes only when ready |
| API Base URL | Beds24 API endpoint | Use configured provider URL |
| Manual Sync Only | Yes or No | Safer as Yes during setup |
| Include Invoice Items on Fetch | Yes or No | Yes if folio/invoice items should sync |
| Access Token | API access token | Manager/admin only |
| Refresh Token | API refresh token | Recommended if used |
| Invite Code | Setup exchange code | Use only during setup |
| Log Verbosity | Normal or Verbose | Verbose only for troubleshooting |
| Webhook Enabled | Yes or No | Use when webhook flow is ready |
| Require Webhook Secret | Yes or No | Usually Yes for security |

Done correctly when:

- Test Connection works.
- Sync is controlled and understood.

## Which Fields Staff Should Avoid

Staff should usually avoid changing these unless manager/accounting instructs them:

- Post accounting now
- BIR fields
- Account Mapping fields
- Chart of Accounts fields
- System Settings
- Beds24 tokens and webhook settings
- Reverse, delete, write off, cancel
- Payroll posting
- Period locks

## Guides Still Missing

The app now has a staff process guide, manager setup guide, and this field guide. The most useful remaining guides would be:

1. `END_OF_DAY_AND_SHIFT_HANDOVER_GUIDE.md`
   - Detailed closing flow for cashier/front desk/manager.
   - Cash count, unpaid balances, bills, deliveries, notes, and manager review.

2. `CORRECTIONS_AND_REVERSALS_GUIDE.md`
   - What to do when staff entered the wrong amount, wrong account, duplicate bill, wrong delivery, wrong folio line, or wrong payment.
   - When to Edit vs Reverse vs Write off vs Delete.

3. `BIR_AND_MONTH_END_GUIDE.md`
   - How manager/accounting reviews BIR items, reports, locks, and month-end checks.

4. `BEDS24_SYNC_TROUBLESHOOTING_GUIDE.md`
   - What to check when bookings, guests, invoices, or folios do not sync as expected.

5. `POS_TO_ACCOUNTING_SYNC_GUIDE.md`
   - How POS sales, room charges, tenders, cash drawers, menu items, categories, and kitchen/F&B areas correspond to accounting.

6. `ROLE_PERMISSIONS_GUIDE.md`
   - Recommended permissions for Front Desk, Cashier, Purchasing, Inventory, Payroll, Finance, Manager, and Admin.

7. `REPORTS_GUIDE.md`
   - Which report to use for sales, cash, receivables, payables, inventory, payroll, BIR, and manager review.

8. `EMERGENCY_MANUAL_PROCESS_GUIDE.md`
   - What staff do if internet, POS, Beds24, printer, or accounting access is down.

Recommended next guide:

- Start with `END_OF_DAY_AND_SHIFT_HANDOVER_GUIDE.md`, because it directly protects daily cash, unpaid balances, deliveries, and manager review.
