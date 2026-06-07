# Hidden Oasis Staff-Ready End-to-End Guide

Last updated: 2026-06-02  
Applies to: Accounting ERP and Dedicated Cloud POS  
Audience: front desk, cashier, kitchen, purchasing, inventory, finance, supervisors, managers, and owners

## 1. Purpose

Use this handbook during training and real shifts. It explains:

- which app owns each record
- what each important field means
- what each important button does
- the normal end-to-end processes
- what proof to attach or record
- what to do in hot situations without creating duplicates

The two systems are connected but have different jobs:

| System | Use it for | Do not use it for |
| --- | --- | --- |
| Dedicated Cloud POS | Restaurant orders, cashier payment, room-charge queue, drawer shifts, cash movement, kitchen display, customer display, and staff recipe PDFs | Creating a second menu master or manually repeating a sale already recorded in POS |
| Accounting ERP | Menu master, inventory, purchasing, receiving, bookings, folios, Beds24, cashflow, receivables, payables, payroll, BIR, attachments, reports, and setup | Re-entering normal POS restaurant sales unless POS was unavailable and manager approved outage encoding |

## 2. Golden Rules

1. Encode once in the correct app.
2. Search before creating a guest, supplier, item, booking, receivable, payable, account, or event.
3. Never create a second record just because the original is hard to find.
4. Add a reference and proof whenever money, stock, room charges, delivery, or corrections are involved.
5. Staff should not guess accounting accounts. Ask a manager when mapping is missing.
6. Do not force retries repeatedly. The POS sync worker schedules retries automatically.
7. Use Edit for ordinary corrections. Use Void, Reverse, Reopen, Archive, Resolve, or Write Off only with the correct manager process.
8. When the POS sync banner is not green, continue only with the documented hot-situation steps.

## 3. Proof and Reference Standards

### 3.1 Reference formats

Use a traceable reference instead of `test`, `sample`, or blank text.

| Situation | Good sample reference |
| --- | --- |
| Restaurant order | `ORD-20260602-0042` |
| GCash payment | `GCASH-20260602-884211` |
| Card payment | `CARD-BDO-20260602-0917` |
| Bank transfer | `BDO-TRX-20260602-112233` |
| Room charge front-desk posting | `BEDS24-INV-204-20260602-01` |
| Supplier invoice | `INV-FRESHMART-20260602-188` |
| Delivery receipt | `DR-FRESHMART-20260602-771` |
| Purchase request | `PR-KITCHEN-20260602-03` |
| Purchase order | `PO-FRESHMART-20260602-09` |
| Event contract | `EVT-SANTOS-20260718` |
| Drawer count variance | `VAR-MAINPOS-AM-20260602` |

### 3.2 Sample proof examples

Use the same structure for real proof files:

| Proof type | Sample filename |
| --- | --- |
| GCash screenshot | `GCASH-20260602-884211-JUAN-SANTOS.png` |
| Supplier invoice scan | `INV-FRESHMART-20260602-188.pdf` |
| Delivery receipt photo | `DR-FRESHMART-20260602-771.jpg` |
| Signed event contract | `EVT-SANTOS-20260718-CONTRACT.pdf` |
| Bank deposit slip | `BDO-DEPOSIT-20260602-112233.jpg` |
| Drawer variance note | `VAR-MAINPOS-AM-20260602.txt` |

Proof must show the amount, date, counterparty, and trace number when available.

## 4. Role Map

| Role | Main duties | Manager-only actions |
| --- | --- | --- |
| Cashier | Open mapped shift, take orders, collect payment, issue receipt, hold/resume orders, close count | Large discount approval, void, refund approval, reopen shift, mapping changes |
| Kitchen / bar | Monitor KDS, acknowledge, prepare, mark ready, open recipe PDFs | Catalog setup, void, drawer work |
| Front desk | Review room-charge queue, post to Beds24 manually, settle guest folio status, booking and folio work | Reject/write-off decisions without supervisor approval |
| Purchasing | PR, PO, supplier coordination, receiving preparation | PO approval and receiving reversal unless authorized |
| Inventory | Receiving validation, stock checks, reconciliation notes | Final adjustment approval |
| Finance | Receivables, payables, cashflow, attachments, reports, reconciliation | Posting, period lock, chart mapping based on assigned permission |
| Manager | Shift support, approvals, mapping health, sync diagnostics, exceptions | Admin settings and user permission changes if assigned |

## 5. Start-of-Shift Checklist

### 5.1 Cashier

1. Log in to POS with your own user.
2. Check the sync banner at the top.
3. Confirm the banner is green: `POS sync healthy`.
4. Open `Sessions`.
5. In `Open New Session`, select the correct register.
6. Confirm no yellow `Manager setup required` warning appears.
7. Enter the real `Business Date`.
8. Enter `Shift`, such as `AM`, `PM`, or `DINNER`.
9. Enter `Opening Float`.
10. Enter an `Opening Note` when money was handed over or differs from normal.
11. Click `Open Session`.

Expected result:

- A session code is created.
- Opening float is recorded.
- POS orders can be saved against the open drawer.

### 5.2 Front desk and finance

1. Open Accounting ERP `Start of Day`.
2. Review payments to receive.
3. Review bills to pay.
4. Review deliveries needing receiving.
5. Review drawers or safes requiring count.
6. Open Beds24 integration if arrivals, departures, or folios need a sync check.

### 5.3 Kitchen

1. Open POS `Kitchen`.
2. Confirm the screen is filtered to the correct station when needed.
3. Open POS `Recipes` and confirm recipe PDFs are accessible for active dishes.

## 6. POS Screen Guide

## 6.1 Sync banner

| Display | Meaning | Staff action |
| --- | --- | --- |
| `POS sync healthy` | POS database, Accounting connection, worker heartbeat, and queue are okay | Continue normally |
| `Checking POS sync health` | Diagnostics are still loading | Wait briefly before opening a new shift |
| `POS sync needs attention` | Accounting API, migration, worker, or queue needs manager attention | Tell manager; use the hot-situation section |
| `POS server connection needs attention` | Browser cannot read POS API | Do not assume an order was saved |

Managers can click `Open diagnostics`.

## 6.2 Sessions

### Open New Session fields

| Field | What to enter | Rule |
| --- | --- | --- |
| Register | Physical drawer being used | Choose the real counter drawer |
| Business Date | Date the shift belongs to | Use operating date, not automatically tomorrow after midnight |
| Shift | `AM`, `PM`, `DINNER`, or agreed label | Stay consistent |
| Opening Float | Cash physically placed in drawer | Count before entering |
| Opening Note | Handover or exception note | Use when float differs or cash was transferred |

### Close Session controls

| Button / field | What it does | Rule |
| --- | --- | --- |
| `Prepare Count` | Opens denomination and close controls | Disabled if drawer mapping is missing |
| `Counted cash` | Actual physical drawer amount | Count first |
| `Verified close` | Normal close after checking expected cash | Preferred |
| `Blind close` | Cashier submits count without relying on expected result | Use only under property policy |
| Denomination quantity fields | Calculates actual count from bills and coins | Enter physical quantities |
| `Variance note` | Explains over/short result | Required operationally when not zero |
| `Sign-off name` | Person accepting close | Use real name |
| `Sign-off role` | Person's role | Example: `Cashier`, `Supervisor` |
| `Close` | Finalizes session and queues Accounting reconciliation | Do not click until count is complete |
| `Reopen` | Reopens a closed drawer for correction | Manager reason required |

Sample close:

```text
Register: Main POS Drawer
Business Date: 2026-06-02
Shift: AM
Opening Float: 2,000.00
Counted cash: 7,350.00
Variance note: Short 50.00. Supervisor checked one cash refund receipt.
Sign-off name: Ana Cruz
Sign-off role: Supervisor
Reference note: VAR-MAINPOS-AM-20260602
```

## 6.3 POS terminal

### Order header fields

| Field | Meaning | Staff rule |
| --- | --- | --- |
| Register session | Active drawer shift | Confirm before taking payment |
| Order type | Dine-in, takeout, delivery, or room service | Match actual service |
| Guest | Guest or walk-in label | Use guest name for room service and special orders |
| Table | Physical table or service label | Required for dine-in service flow |
| Pax / seats | Guest count | Use real cover count |
| Note | Whole-order instruction | Use for timing or overall service notes |

### Main buttons

| Button | Use |
| --- | --- |
| `Add` / menu tile | Add an item or open variant choice |
| `Hold` | Save an unpaid order temporarily |
| `Resume` | Continue a held order |
| `Transfer Table` | Move an order to another table without creating a duplicate |
| `Merge Table` | Merge table service using the supported flow |
| `Payment` | Open tender and settlement controls |
| `Print Receipt` | Print the browser-formatted receipt |
| `Customer Display` | Open guest-facing display; separate devices use the server-backed channel |
| Menu availability controls | Mark sold-out or restore locally without editing Accounting menu master |

### Line controls

| Field / button | Meaning |
| --- | --- |
| Quantity | Number of portions |
| Note | Item-specific instruction, such as `no onions` |
| Discount | Manual line discount; larger values require manager override |
| Remove line | Remove before final payment |

## 6.4 Payment popup

| Field / button | What to enter or do | Rule |
| --- | --- | --- |
| `Due` | Read-only order total | Check before collecting |
| `Applied` | Sum allocated across tenders | Must equal Due |
| `Change` | Cash change preview | Return correct amount |
| `Folio Pending` | Amount routed to room charge | Front desk must later complete posting |
| `Cash remaining` | Adds remaining due as cash | Use only when actual tender is cash |
| `GCash remaining` | Adds remaining due as GCash | Enter trace reference |
| `Card remaining` | Adds remaining due as card | Enter terminal reference |
| `Room charge` | Adds remaining due to room folio queue | Match in-house booking |
| `Exact cash` | Uses full due as received cash | Verify guest handed exact amount |
| Tender | Cash, GCash, card, bank transfer, or room charge | Match reality |
| Applied | Portion of total paid by this tender | Split tender must add up |
| Received | Cash handed over | Room charge disables this |
| Reference | Trace number | Required operationally for non-cash |
| `Routing` | Advanced settlement account | Cashiers normally leave mapped defaults |
| `Pay` / final settle | Saves payment and finalizes order | Click once and wait for result |

Sample split payment:

```text
Order: ORD-20260602-0042
Due: 1,250.00
Tender 1: cash
Applied: 500.00
Received: 500.00
Tender 2: gcash
Applied: 750.00
Reference: GCASH-20260602-884211
Proof: GCASH-20260602-884211-JUAN-SANTOS.png
```

## 6.5 Room charge from POS

Use only for an in-house guest whose stay can be matched.

| Field / button | What to enter | Rule |
| --- | --- | --- |
| `Room or Guest` | Room, guest, or booking search | Search first |
| `Best Match` | Chooses strongest matching in-house snapshot | Verify before paying |
| Service Type | Room service, restaurant, minibar, or applicable type | Match charge |
| Stay Date | Guest stay date | Confirm correct date |
| Room Number | Room charged | Verify verbally |
| Guest / Booking | Guest label | Match booking |
| In-House Booking | Synced booking snapshot | Prefer snapshot over manual text |
| Bill To | Billing instruction | Use when company/group or special bill-to applies |
| Room Charge Note | Service and exception detail | Add useful context |

End-to-end result:

1. POS order becomes `folio_pending`.
2. POS creates a room-charge queue item.
3. Accounting receives the receivable safely through the sync worker.
4. Front desk manually posts to Beds24 using the queue.
5. Front desk saves Beds24 reference and later settlement status in POS.

Important: Beds24 posting is currently a tracked manual front-desk step. Do not assume POS has posted it automatically.

## 6.6 Room Charges queue

| Status | Meaning | Staff action |
| --- | --- | --- |
| Pending front-desk post | POS captured charge; Beds24 still needs posting | Front desk posts to correct folio |
| Posted to Beds24 | Front desk saved Beds24 posting reference | Wait for settlement or review |
| Settled at front desk | Guest payment or folio handling completed | No further routine action |
| Disputed | Needs investigation | Supervisor reviews proof |
| Rejected | Wrong guest, wrong booking, or invalid charge | Manager follows correction flow |

Sample front-desk proof:

```text
POS order: ORD-20260602-0048
Room: 204
Guest: Juan Santos
Service: Room service
Charge: 680.00
Beds24 reference: BEDS24-INV-204-20260602-01
Note: Posted to Room 204 folio at 14:35 by M. Reyes.
```

## 6.7 Cash Movements

Use for paid-in, paid-out, safe drop, bank deposit, and drawer transfer.

| Field | Meaning | Rule |
| --- | --- | --- |
| Session | Drawer shift | Pick the correct active session |
| Direction | In or out | Match real cash movement |
| Movement type | Paid in, paid out, safe drop, bank deposit, drawer transfer | Choose exact type |
| Category | Why cash moved | Use clear category |
| Amount | Physical amount | Count first |
| From Account | Source drawer mapping | Normally mapped drawer |
| To Account | Safe, bank, or destination | Required for transfer-style movements |
| Destination Register | Receiving drawer | Use for drawer transfer |
| Reference | Handover or deposit proof | Add whenever available |
| Note | Context and handler | Include who received cash |

## 6.8 Kitchen

| Button | Meaning |
| --- | --- |
| Acknowledge | Kitchen has seen the ticket |
| Start / In Progress | Preparation has started |
| Partial Ready | Some quantity is ready |
| Ready | Item is ready for pass |
| Served | Service completed |

Kitchen rule: never create a replacement ticket because the first ticket looks delayed. Update the existing ticket or ask cashier to check the order.

## 6.9 Recipes

POS `Recipes` is a staff reference library linked to dishes synced from Accounting.

| Control | Use |
| --- | --- |
| Search dishes | Search Accounting dish, category, or variant |
| Category filter | Narrow recipe list |
| PDF status | Show ready or missing documents |
| Open PDF Reader | Read the current recipe PDF |
| Open in New Tab | Use a larger reader |
| Upload / Replace PDF | Manager updates one current file per Accounting dish |
| Remove PDF | Manager removes incorrect file |

Do not create a second dish in POS. Add or correct dishes in Accounting, sync catalog, then upload the POS staff PDF.

## 6.10 Customer display

1. Cashier clicks `Customer Display`.
2. The opened page uses channel `main`.
3. A separate tablet or screen may open `/customer-display?channel=main`.
4. Green `Live order` means the display is reading the POS server.
5. Yellow `Local display fallback` means it is only reading same-browser storage.

## 7. Accounting ERP Screen Guide

## 7.1 Start of Day

Open `Start of Day` before daily encoding.

Review:

- receivables needing follow-up
- payables due
- deliveries requiring receiving
- cash accounts requiring count
- booking and Beds24 exceptions

## 7.2 Bookings, guests, and calendar

Accounting calendar shows occupied nights and intentionally excludes checkout dates. A stay from June 2 to June 3 is one night.

| Field | Meaning |
| --- | --- |
| Find Guest | Search existing CRM guest first |
| Guest | Existing guest record |
| Room Type | Booked room category |
| Room | Physical room |
| Rate Plan | Agreed room package or rate |
| Channel | Direct, OTA, corporate, or other source |
| Check In | Arrival date |
| Check Out | Departure date; not an occupied night |
| Gross Amount | Full booking value |
| Deposit | Already received amount |
| Breakfast Included | Included meals based on package |
| Auto Post Accounting | Staff normally leave off unless policy says otherwise |
| Notes | Requests, source references, and exceptions |

If Beds24 is the booking master, do not manually recreate a synced booking.

## 7.3 Folios

Use Room Folios for charges, deposits, payments, refunds, and balances.

| Field | Meaning |
| --- | --- |
| Booking | Related booking |
| Guest override | Use carefully only when needed |
| Folio No | Folio reference |
| Line Type | Charge, payment, deposit, refund, adjustment |
| Description | Human-readable reason |
| Date | Real transaction date |
| Quantity | Units |
| Unit Price | Price each |
| Amount Override | Use only for justified correction |
| Reference | OR, booking, Beds24, or proof reference |
| Notes | Exception context |

## 7.4 Receivables: collect later and receive payment

Use `Cashflow > To Receive`.

### Add Balance to Collect

| Field | Enter |
| --- | --- |
| Customer / Source | Guest, OTA, event client, or company |
| Type | Guest, OTA, event, or company/group balance |
| Date | Creation date |
| Due Date | Expected collection date |
| Total Amount | Full amount owed |
| Already Collected | Amount already received before this record |
| Status | Usually open for a new unpaid balance |
| Include in BIR | Ask manager/accounting if unsure |
| Notes | Source and agreement details |

### Collect popup

| Field | Enter |
| --- | --- |
| Amount | Amount received now |
| Account | Drawer, bank, GCash, or actual money location |
| Method | Actual payment method |
| Reference | OR or trace number |
| Note | Partial or exception detail |

## 7.5 Payables: bill now and pay later

Use `Cashflow > To Pay`.

| Field | Enter |
| --- | --- |
| Supplier | Existing supplier |
| Type | Supplier, utility, payroll/government, tax, or service bill |
| Bill Date | Invoice date |
| Due Date | Payment due |
| Bill Amount | Full invoice |
| Already Paid | Prepaid portion, otherwise 0 |
| Status | Usually open |
| Include in BIR | Ask manager/accounting |
| Notes | Invoice and receiving detail |

When paying, enter actual amount, source account, method, reference, and note.

## 7.6 Purchasing and receiving

Normal flow:

1. Staff creates Purchase Request.
2. Supervisor reviews and approves.
3. Purchasing converts or creates Purchase Order.
4. Supplier delivers.
5. Receiving checks actual quantity and cost.
6. Receiving posts delivery.
7. Inventory updates through FIFO.
8. Supplier payable is created when selected.

### Receiving fields

| Field | Enter |
| --- | --- |
| Supplier | Delivering supplier |
| PO | Related purchase order |
| Delivery Date | Actual arrival date |
| Reference | Supplier DR or invoice |
| Create Supplier Bill | Yes when delivery should create payable |
| Item | Inventory item delivered |
| Qty Received | Actual accepted quantity |
| Unit Cost | Actual accepted cost |
| Notes | Damage, short delivery, substitutions |

Never post expected PO quantity when physical delivery differs.

## 7.7 Menu, recipes, and bulk upload

Accounting is the menu source of truth.

Use:

- `Menu & Recipes` for normal item edits
- `Menu Categories` for grouping
- `Excel Setup Import` for bulk upload
- `Restaurant Ops` advanced tools for components and controlled fallback work

Bulk upload:

1. Download menu-only or full setup `.xlsx` template.
2. Fill required columns.
3. Upload workbook.
4. Run validate-first dry run.
5. Review row-level results.
6. Correct errors.
7. Apply import.
8. Sync POS catalog.

Upsert behavior avoids duplicate setup records. For recipe refresh, use replace-recipe-lines behavior for included items.

## 7.8 Events

Current safe workflow:

1. Create one event record for client, date, package, add-ons, and notes.
2. Create one event receivable for the deposit or balance to collect.
3. Collect deposits and balances from `To Receive`.
4. Add proof references to both the event context and money record.

Sample event:

```text
Event record: EVT-SANTOS-20260718
Client: Santos Family
Event date: 2026-07-18
Package: Garden dinner for 60 pax
Add-on: Projector rental
Contract value: 85,000.00
Deposit receivable: 25,000.00
Deposit reference: BDO-TRX-20260602-112233
Proof: EVT-SANTOS-20260718-CONTRACT.pdf
```

Do not create multiple event records for quote, deposit, and balance. Keep one event context and linked receivable activity.

## 7.9 Attachments

Attach proof to the relevant operational or accounting record:

- invoice
- delivery receipt
- signed contract
- payment screenshot
- deposit slip
- variance note
- refund approval

Use a filename from section 3 so staff can find proof later.

## 7.10 Reports

Use Reports for management KPIs, exceptions, aging, settlements, and CSV export. Formal accountant-grade P&L, Balance Sheet, Cash Flow Statement, and one-click PDF/Excel packs remain accounting/reporting work that must be reviewed before external use.

## 8. End-of-Shift Checklist

### Cashier

1. Finish or hand over held orders.
2. Print needed receipts.
3. Check POS sync banner.
4. Record cash movements.
5. Open `Sessions`.
6. Click `Prepare Count`.
7. Count denominations.
8. Add variance note if needed.
9. Add sign-off name and role.
10. Click `Close`.

### Front desk

1. Open Room Charges queue.
2. Post pending room charges to Beds24.
3. Save posting references.
4. Mark settled items when completed.
5. Escalate disputed or rejected charges with proof.

### Kitchen

1. Confirm active tickets are acknowledged or handed over.
2. Mark ready and served items correctly.
3. Record missing recipe PDFs for manager update.

### Manager

1. Check sync banner.
2. Open diagnostics if not green.
3. Review failed and blocked rows.
4. Review drawer variances.
5. Review room-charge pending queue.
6. Review Accounting Start of Day / closing exceptions as appropriate.

## 9. Hot Situations

## 9.1 Sync banner is yellow or red

Do:

1. Tell manager.
2. Manager opens `Sync Queue`.
3. Read diagnostics before retrying.
4. Check database migration, Accounting API, sync worker, failed rows, and blocked rows.
5. Use `Retry` only after the cause is fixed.

Do not:

- click retry repeatedly
- re-enter a paid order in Accounting
- create a duplicate cashflow transaction

## 9.2 Drawer mapping is missing

Symptom:

- Session open is disabled or close shows `Cannot close yet`.

Do:

1. Manager opens `Registers`.
2. Use Accounting Account Picker.
3. Search the real drawer.
4. Click `Use`.
5. Click `Validate Mapping`.
6. Save register.
7. Return to Sessions.

Do not:

- type a random numeric ID
- map to a bank account just to pass validation

## 9.3 Internet to Accounting is down but POS still works

Do:

1. Continue using POS only if the POS server remains reachable and the manager approves.
2. Keep non-cash proof references.
3. Let POS queue Accounting sync.
4. Manager monitors banner and diagnostics.

Do not:

- re-enter the same sale manually in Accounting
- repeatedly force worker retries

## 9.4 POS server itself is unreachable

Do:

1. Stop assuming browser actions are saved.
2. Tell manager immediately.
3. Use the manager-approved manual outage log with time, items, amount, tender, proof, and staff initials.
4. After recovery, manager uses the controlled outage-only Accounting fallback process once.

Do not:

- keep clicking Pay
- enter the same sale in multiple places

Sample outage log:

```text
OUTAGE-20260602-01
Time: 19:42
Guest/table: L2
Items: 2 x Iced Coffee, 1 x Club Sandwich
Total: 680.00
Tender: cash
Cashier: Ana Cruz
Proof: handwritten receipt OR-OUTAGE-20260602-01
```

## 9.5 Guest changes tender after payment

Do:

1. Do not create a new order.
2. Tell supervisor.
3. Review the paid order and proof.
4. Use approved refund/correction procedure.
5. Record the corrected payment with traceable reference.

## 9.6 Wrong room charge guest or room

Do:

1. Mark the queue item disputed or rejected with reason.
2. Keep the POS order number and Beds24 reference if already posted.
3. Supervisor corrects the folio using front-desk process.
4. Attach or note proof.

Do not:

- quietly post a second charge and leave the wrong one open

## 9.7 Drawer over or short

Do:

1. Recount denominations.
2. Review paid-out, safe-drop, refund, and cash orders.
3. Enter variance note.
4. Add sign-off.
5. Close with the actual count.

Do not:

- alter a valid sale to make the drawer balance

## 9.8 Duplicate-looking sale or payment

Do:

1. Search order number, reference, guest, amount, and date.
2. Check whether it is a replay-safe synced record.
3. Escalate before deleting or reversing.

## 9.9 Supplier delivery is short, damaged, or substituted

Do:

1. Receive only accepted quantity.
2. Note rejected quantity and reason.
3. Attach DR photo.
4. Keep PO open for remainder when applicable.

## 9.10 Recipe PDF is missing or wrong

Do:

1. Staff tells manager the Accounting dish name.
2. Manager opens POS `Recipes`.
3. Search dish.
4. Upload or replace PDF.
5. Staff reopens PDF Reader.

Do not:

- create a duplicate dish in POS

## 9.11 Customer display is yellow

Yellow `Local display fallback` means separate-device updates are unavailable.

Do:

1. Confirm POS server banner.
2. Refresh guest display.
3. Continue verbally confirming order if needed.

## 9.12 Printer is unavailable

Current receipt printing uses the browser print flow.

Do:

1. Keep the order number visible.
2. Retry browser print once.
3. Use manager-approved manual receipt if hardware remains unavailable.
4. Keep order number on the manual receipt.

## 10. Manager Daily Readiness Check

Before declaring staff-ready:

- [ ] POS database migrations are at current head.
- [ ] POS health route works.
- [ ] Accounting health route works.
- [ ] POS sync banner is green.
- [ ] Sync worker heartbeat is current.
- [ ] Active registers have valid Accounting drawer IDs.
- [ ] Failed retry storm rows are resolved or archived after review.
- [ ] POS catalog loads.
- [ ] Recipe PDFs open.
- [ ] Separate-device customer display updates.
- [ ] Test cashier order syncs to Accounting.
- [ ] Test room charge reaches front-desk queue.
- [ ] Staff know outage procedure.
- [ ] Staff know not to duplicate records.

## 11. Training Practice Run

Managers should run this with training data before the first live shift:

1. Open mapped POS register `TRAINING`.
2. Add one `Iced Coffee`.
3. Hold and resume the order.
4. Pay using practice cash amount.
5. Confirm kitchen ticket.
6. Confirm customer display.
7. Confirm order sync in Accounting.
8. Create a room-service practice order and route to a training in-house booking only.
9. Confirm queue workflow and reference entry.
10. Close session with denomination count.
11. Confirm reconciliation sync.
12. Delete or reverse training data only through approved cleanup.

Done when:

- one complete restaurant flow is proven
- staff can explain where proof belongs
- no transaction was encoded twice

## 12. Staff Operating Notes Added for Current Version

### 12.1 Login and access

Expected behavior:

1. If no valid session exists, the app opens the login page.
2. If the user is logged in but does not have permission, the app shows `Access Restricted`.
3. The sidebar should show only pages the user can use.
4. Staff should not share accounts. Every exception needs the correct actor in the audit trail.

What staff should do:

- If the login page appears, sign in with the assigned account.
- If `Access Restricted` appears after login, ask a manager to confirm the role or permission.
- If a shared tablet still shows another user's page, press `Logout`, then sign in again.

### 12.2 Tablet layout rules

Use tablets in landscape mode for POS cashier work whenever possible.

Accounting ERP tablet rules:

- Tables may scroll inside their card when there are many columns.
- Forms collapse into fewer columns so field labels and inputs stay readable.
- Do not rotate repeatedly while saving a form.

POS tablet rules:

- The POS order screen may stack cart and menu sections at smaller widths.
- Use `Spaces` to select the table or room service context first.
- Use the payment popup only after reviewing the cart total and selected tender.
- If a popup feels crowded, close it and reopen after correcting the cart.

### 12.3 All old booking folio classification

Use this when old Beds24 folio rows look like the wrong charge type.

Where to go for all old bookings:

```text
Accounting ERP > Beds24 Integration > All Old Booking Folio Classification
```

Buttons:

| Button | Meaning | Rule |
| --- | --- | --- |
| Preview All Old Bookings | Scans old rows and shows suggested type changes | Always run this first |
| Apply Previewed Corrections | Applies the last reviewed suggestions | Manager checks balance adjustment first |

Where to go for one booking:

```text
Accounting ERP > Bookings > open booking > Review Existing Folio Classifications
```

Fields:

| Field | Meaning | Rule |
| --- | --- | --- |
| Include Staff Manual Lines | Includes manually entered historical rows | Keep off unless manager wants manual rows reviewed |
| Review Old Payments / Deposits | Allows repair of mislabeled payment/deposit rows | Keep on for old Beds24 import cleanup |
| Scan Limit | Maximum rows reviewed in one pass | Use a practical limit, then rerun if needed |

Before applying:

1. Read `Would Update`.
2. Read `Balance Adjustment`.
3. Review sample lines.
4. Open a few affected bookings if the adjustment is large.
5. Apply only once.

After applying:

1. Open affected folios.
2. Confirm charges, payments, deposits, refunds, and balance.
3. Add an attachment or note when the correction is part of a manager review.

### 12.4 Offline-aware POS use

The POS can help preserve order details during a temporary browser/server connection problem, but it should not pretend a payment or room charge is complete while offline.

Use offline emergency drafts only for order-taking continuity:

1. Keep the cart, table, guest, and notes accurate.
2. Save an offline emergency draft when the server is unreachable.
3. Do not click Pay repeatedly.
4. Do not mark room charges as posted or settled offline.
5. When connection returns, restore the draft and save or settle it normally.

Manager rule:

- If money was collected during a confirmed outage, use the outage log and recovery checklist. Encode once after recovery, with the original proof and the manager note.

### 12.5 Final daily close

At the end of the day or before manager turnover:

1. POS sessions are closed or intentionally left open with note.
2. Drawer variance has a note.
3. Room-charge queue has no unexplained pending or disputed items.
4. POS sync queue has no unresolved failed critical rows.
5. Accounting receivables and payables due today were reviewed.
6. Deliveries received today were posted or left pending with reason.
7. Attachments for major payments, supplier bills, events, and corrections were uploaded.
