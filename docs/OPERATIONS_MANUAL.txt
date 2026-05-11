# Resort Accounting ERP - Staff Playbook

Last updated: 2026-04-18
Version: 2.0 (SOP and Scenario Edition)

## 1) What this document is for

This playbook is written for real daily use by staff, supervisors, and accounting.

It gives you:

- Daily SOP checklists
- Step-by-step scenario workflows
- Field-by-field instructions
- What to do, what not to do, and what result to expect
- Reconciliation and close procedures

Use this as your operations manual, accounting guide, and training script.

## 2) Core operating rules (read this first)

1. Encode once, in the correct module.
- Do not duplicate the same transaction in multiple pages unless intentionally required.

2. Operations and Treasury are different layers.
- Operations pages record business activity (booking, sale, staff meal, stock movement, payroll run).
- Treasury page records real money movement across drawers and banks.

3. Be intentional with auto-post accounting toggles.
- `auto_post_accounting = true` creates accounting links automatically.
- Keep it off when your policy is manual accounting posting.

4. Always include references.
- Use booking ref, OR number, PO number, payout ref, invoice number, and counterparty.

5. Lock only after review.
- BIR period lock should happen only after reconciliation and final checks.

## 3) Role map and responsibilities

### 3.1 Staff encoder

- Encode bookings, sales, breakfast, staff meals, stock movements, and attendance.
- Must follow field standards and reference format.
- Must not post manual journals unless authorized.

### 3.2 Supervisor / manager

- Reviews daily encoding completeness.
- Ensures no missing references and no invalid dates.
- Handles exception corrections.

### 3.3 Accountant

- Reviews posted records and treasury movements.
- Performs reconciliations.
- Posts payroll run to journal.
- Controls BIR inclusion list and period lock.

### 3.4 Admin / owner

- Maintains users, roles, taxonomy, and master data controls.
- Approves close and lock schedule.

## 4) Daily SOP (checklist style)

## 4.1 Opening shift SOP (front office + cashier + kitchen)

1. Open `Dashboard` and note baseline KPIs.
2. Open `Treasury` and confirm drawer opening balances are correct.
3. Open `Bookings` and review arrivals and expected check-outs.
4. Open `Restaurant Ops` and review low-stock alerts.
5. Open `Staff Meals` and verify yesterday logs were completed.
6. Open `Channel Payouts` and check pending OTA payouts.

Output expected:
- All teams start with clear opening balances and pending workload.

## 4.2 During shift SOP

Front office:
1. Encode new bookings immediately.
2. Update booking status when check-in/check-out/cancel happens.
3. Post breakfast logs after serving.

Restaurant/kitchen:
1. Post sales in `Restaurant Ops` as they happen (or end of service batch if policy allows).
2. Post restock receipts immediately after receiving supplies.
3. Post staff meals before end of shift.

Cashier/treasury encoder:
1. Record treasury movements for all in/out/transfer events.
2. Use reference and counterparty on every movement.

Accounting support:
1. Review exception errors from all modules.
2. Verify no duplicate postings.

Output expected:
- Real-time data integrity with minimal backlogs.

## 4.3 End of day SOP

1. Confirm all bookings and breakfast postings are complete.
2. Confirm all sales/restocks/staff meals for the day are posted.
3. Confirm all drawer movements are encoded in Treasury.
4. Run drawer reconciliation in Treasury for each active drawer.
5. Review errors and resolve immediately.
6. Leave notes for unresolved exceptions.

Output expected:
- Operational activity and treasury logs are complete for the day.

## 5) Weekly SOP

1. Inventory spot count for critical items.
2. Compare physical count vs system on-hand for top-value stock.
3. Review OTA payout statuses and settlement delays.
4. Reconcile at least one bank account fully.
5. Review records pending approval.
6. Validate staff meal consumption reasonableness.

## 6) Month-end SOP

1. Ensure all operational modules are complete for month.
2. Finalize treasury reconciliations (all drawers + banks).
3. Post payroll run(s) and verify payroll liabilities.
4. Post asset depreciation/maintenance/disposal entries as needed.
5. In `BIR`:
   - review candidate list
   - include/exclude intentionally
   - save selection list
   - generate books
6. Lock period after final sign-off.

## 7) Field standards (all staff must follow)

## 7.1 Date fields

- Use `YYYY-MM-DD` format.
- Never leave date blank if event date is known.
- For payroll period and BIR, always confirm correct month/year.

## 7.2 Amount fields

- Use positive values unless workflow explicitly creates reversals.
- Avoid blank amount on financial-impact entries.
- Use 2 decimal places for money fields.

## 7.3 Reference fields

- Use meaningful references (examples: `OR-10288`, `PO-447`, `BOOK-193`, `PAYOUT-AGD-2401`).
- Never use generic text like `test` in production.

## 7.4 Counterparty fields

- Fill supplier/guest/platform name where applicable.
- Required for audit clarity and reconciliation.

## 7.5 Notes fields

Use notes for:
- exceptions
- manual override reasons
- correction rationale
- missing document explanation

## 8) Module SOP and field guide

## 8.1 Bookings (`/bookings`)

### Purpose
- Manage booking lifecycle and optional accounting linkage.

### Booking form fields and how to fill

| Field | What to enter | Required | Notes |
|---|---|---|---|
| `guest_name` | Guest full name | Yes | Avoid initials only |
| `room_name` | Room number/name | No | Recommended |
| `room_type` | Type (Deluxe, Family, etc.) | No | Useful for reporting |
| `channel` | Walk-in / Agoda / etc. | Yes | Drives OTA behavior |
| `status` | confirmed / checked_in / checked_out / cancelled | Yes | Update over lifecycle |
| `check_in` | Arrival date | No | Must be <= check_out |
| `check_out` | Departure date | No | Cannot be earlier than check_in |
| `gross_amount` | Total booking amount | Yes | Use contract value |
| `deposit_amount` | Deposit received | No | Use 0 if none |
| `breakfast_included` | Number of included breakfasts | No | Integer recommended |
| `payment_method` | cash/gcash/card/bank_transfer/ota_payout/on_account | Yes | OTA typically `ota_payout` |
| `effective_date` | Date for adjustment posting | No | Use today for status adjustments |
| `auto_post_accounting` | true/false | Yes | Keep per policy |
| `auto_reverse_on_cancel` | true/false | No | Recommended true |
| `notes` | booking remarks | No | Put agreement details |

### Daily booking SOP

1. Open `Bookings`.
2. Create booking with complete guest and amount data.
3. If policy requires immediate accounting link, set `auto_post_accounting = true`.
4. Save booking.
5. On lifecycle change, use `Edit`, `Check Out`, or `Cancel`.
6. Recheck linked accounting rows in booking list.

Expected result:
- Booking record is current.
- Accounting links exist only when intentionally posted.

## 8.2 Room Breakfast (`/bookings` lower section)

### Purpose
- Record breakfast consumption and deduct inventory.

### Field guide

| Field | What to enter | Required | Notes |
|---|---|---|---|
| `booking_id` | Linked booking | No | Recommended when tied to room stay |
| `meal_date` | Service date | Yes | Must match service date |
| `guest_name` | Guest receiving breakfast | No | Auto-fills when booking selected |
| `menu_item_id` | Breakfast menu item | Yes | Required |
| `sku_id` | SKU variant | No | Use for size/variant recipes |
| `quantity` | Servings count | Yes | Must be > 0 |
| `charge_to_room` | true/false | Yes | Controls revenue logic |
| `charged_amount` | Total charge | No | Auto if blank and charge_to_room=true |
| `payment_method` | Payment context | Yes | For optional accounting |
| `auto_post_accounting` | true/false | Yes | Optional linkage |
| `notes` | service notes | No | Add exceptions |

### SOP

1. Select booking if applicable.
2. Choose menu item and SKU if needed.
3. Enter quantity.
4. Set charge behavior.
5. Save breakfast posting.

Expected result:
- Inventory deducted.
- COGS calculated.
- Optional accounting links created when enabled.

## 8.3 Restaurant Ops (`/restaurant-ops`)

This is your main restaurant control page.

### 8.3.1 Quick Sale field guide

| Field | What to enter | Required | Notes |
|---|---|---|---|
| `order_no` | Unique order ref | No | Auto if blank |
| `order_date` | Transaction date | Yes | Daily service date |
| `payment_method` | cash/gcash/card/bank_transfer/on_account | Yes | Impacts accounting mapping |
| `channel` | dine-in, delivery, etc. | No | Reporting use |
| `counterparty` | customer name/account | No | Recommended for charge sales |
| `strict_inventory` | true/false | Yes | Keep true for accuracy |
| `auto_post_accounting` | true/false | Yes | Policy-driven |

Sale line fields:

| Field | What to enter | Required | Notes |
|---|---|---|---|
| `menu_item_id` | Dish/product | Yes | Required |
| `sku_id` | Variant | No | Optional |
| `quantity` | Units sold | Yes | Must be > 0 |
| `unit_price` | Sell price | No | Auto fallback from menu/SKU |
| `discount_amount` | Line discount total | No | Use valid discount only |

### Quick Sale SOP

1. Enter sale header values.
2. Add line(s) one by one.
3. Review computed gross/discount/net.
4. Click `Post Sale`.

Expected result:
- Sale order created.
- Inventory deducted FIFO from recipe/component requirements.
- COGS computed.
- Optional accounting links created when enabled.

### 8.3.2 Quick Restock field guide

| Field | What to enter | Required | Notes |
|---|---|---|---|
| `item_id` | Inventory item | Yes | Required |
| `quantity` | Received qty | Yes | Must be > 0 |
| `unit_cost` | Purchase cost per unit | Yes for stock-in | Use supplier invoice basis |
| `reason` | Purchase/restock reason | Yes | Example: Purchase |
| `reference_no` | PO/DR/Invoice ref | No | Strongly recommended |
| `movement_date` | Receipt date | Yes | Required for FIFO timeline |
| `supplier` | Vendor name | No | Recommended |
| `log_expense` | true/false | Yes | Controls accounting link |
| `expense_module_slug` | procurement/inventory/finance | No | default by process |
| `expense_payment_method` | cash/bank/etc | No | for linked record |
| `expense_counterparty` | vendor | No | defaults to supplier |

### Quick Restock SOP

1. Fill restock details from supplier document.
2. Decide if linked expense should be auto-created.
3. Save restock.

Expected result:
- Stock in movement created.
- Inventory on-hand and average cost updated.
- Optional expense record linked.

### 8.3.3 Catalog Builder SOP

Menu tab:
1. Create/update menu items with module and base price.

Components tab:
1. Create component with yield quantity and unit.
2. Add component recipe lines.
3. Use costing button to validate unit cost.

SKUs tab:
1. Select menu item.
2. Define SKU variant and price.
3. Add SKU recipe lines (inventory or component).
4. Use costing button to validate margin.

Promos tab:
1. Choose target (`sku` or `menu_item`).
2. Set promo type (`percent_off`, `fixed_discount`, `set_price`).
3. Define validity period and activation.

## 8.4 Staff Meals (`/staff-meals`)

### Purpose
- Capture internal consumption and keep inventory/accounting accurate.

### Field guide

| Field | What to enter | Required | Notes |
|---|---|---|---|
| `meal_no` | Ref number | No | Auto if blank |
| `meal_date` | Date served | Yes | Required |
| `dish_name` | Dish description | Yes | Required |
| `menu_item_id` | Menu item | No | Optional if manual ingredients only |
| `sku_id` | Variant | No | Optional |
| `quantity` | Meal quantity | Yes | Must be > 0 |
| `served_to` | Staff group | Yes | Kitchen/Service/Office |
| `strict_inventory` | true/false | Yes | Keep true by default |
| `payment_method` | accounting source | No | default inventory |
| `auto_post_accounting` | true/false | Yes | optional expense link |
| `notes` | explanation | No | optional |

Ingredient line fields:
- inventory item
- quantity
- unit
- notes

### SOP

1. Enter meal header.
2. Add menu item/SKU and/or manual ingredient lines.
3. Save entry.

Expected result:
- Inventory deducted.
- COGS amount stored.
- Optional accounting expense record linked.

## 8.5 Inventory Items (`/inventory-items`)

### Purpose
- Maintain inventory master list.

### Field guide

| Field | Meaning |
|---|---|
| `name` | Ingredient/supply name |
| `category_name` | High-level grouping |
| `subcategory_name` | More specific grouping |
| `unit` | pcs, kg, g, L, etc. |
| `reorder_level` | Alert threshold |
| `notes` | classification notes |

SOP:
1. Create standardized naming format.
2. Ensure unit consistency.
3. Set reorder levels.

## 8.6 Stock Movements (`/stock-movements`)

### Purpose
- Post explicit stock in/out and maintain FIFO costing.

### Field guide

| Field | Required | Notes |
|---|---|---|
| `item_id` | Yes | inventory item |
| `movement_type` | Yes | `in` or `out` |
| `quantity` | Yes | > 0 |
| `unit_cost` | Required for `in` | disabled for out in UI |
| `reason` | Recommended | Purchase, Orders, Count Loss, etc |
| `module_slug` | Recommended | tracking source module |
| `reference_no` | Recommended | source document |
| `movement_date` | Recommended | transaction date |
| `supplier` | optional | mainly for stock-in |
| `log_expense` | optional | create linked accounting expense |

### SOP

Stock in:
1. Select item, type `in`.
2. Enter quantity and unit cost.
3. Add source reference.
4. Save.

Stock out:
1. Select item, type `out`.
2. Enter quantity and reason.
3. Save.

Expected result:
- FIFO batches updated.
- Outbound fails if insufficient stock.

## 8.7 Treasury (`/treasury`)

### Purpose
- Official ledger for drawer/bank in/out/transfer and reconciliation.

### 8.7.1 Treasury account fields

| Field | Required | Notes |
|---|---|---|
| `code` | Yes | unique code |
| `name` | Yes | readable name |
| `account_type` | Yes | drawer or bank |
| `opening_balance` | optional | numeric |
| `currency` | optional | default PHP |
| `sort_order` | optional | display order |
| `is_active` | optional | true/false |

### 8.7.2 Treasury movement fields

| Field | Required | Rules |
|---|---|---|
| `movement_type` | Yes | in/out/transfer |
| `from_account_id` | depends | required for out/transfer |
| `to_account_id` | depends | required for in/transfer |
| `amount` | Yes | > 0 |
| `movement_date` | Yes | lock-sensitive |
| `reference_no` | recommended | reconciliation key |
| `counterparty` | recommended | who paid/received |
| `create_finance_record` | optional | creates linked record |

Validation behavior:
- `in`: no from account
- `out`: no to account
- `transfer`: from and to both required and must differ

### 8.7.3 Reconciliation fields

| Field | Required | Notes |
|---|---|---|
| `account_id` | Yes | account to reconcile |
| `as_of_date` | Yes | cut-off date |
| `statement_balance` | Yes | external statement/cash count |
| `notes` | optional | discrepancy notes |

System computes:
- `system_balance`
- `variance`

### Treasury daily SOP

1. Encode each movement as it happens.
2. Do not postpone end-of-day movement entry.
3. Reconcile drawers before shift close.
4. Escalate variance immediately.

## 8.8 Channel Payouts (`/channel-payouts`)

### Purpose
- Track OTA gross, commissions, and settlement timing.

### Field guide

| Field | Required | Notes |
|---|---|---|
| `channel` | Yes | Agoda/Booking/etc |
| `booking_ref` | recommended | tie to booking |
| `gross_amount` | Yes | booking gross |
| `commission_amount` | Yes | platform fee |
| `net_amount` | Yes | expected payout |
| `expected_payout_date` | optional | schedule tracking |
| `actual_payout_date` | optional | settlement date |
| `status` | Yes | pending/scheduled/paid/cancelled |
| `auto_post_accounting` | optional | link records |

### SOP

1. Add payout row once OTA amount is known.
2. Update status as payout progresses.
3. Use `Settle` when paid.
4. Reconcile payout with bank movement and treasury record.

## 8.9 Employees and Attendance (`/employees`)

### Purpose
- Manage employee profiles and attendance source data.

Employee fields:
- full_name
- department
- job_title
- compensation_type
- rate, daily_rate, hourly_rate

Attendance fields:
- employee_id
- work_date
- time_in/time_out
- overtime_hours
- night_diff_hours
- day_type

SOP:
1. Keep employee profile updated before payroll period.
2. Encode attendance daily.
3. Fix errors before payroll run generation.

## 8.10 Payroll Runs (`/payroll`)

### Purpose
- Build payroll by period and post payroll JE.

### Manual period input fields (recommended for your setup)

Line buckets:
- regular hours
- OT hours
- regular holiday hours
- special holiday hours
- night diff hours

Compensation and deductions:
- hourly rate
- benefits/allowances
- cash advance
- other deductions
- SSS/PhilHealth/Pag-IBIG employee and employer values

### Manual payroll SOP

1. Prepare external payroll report.
2. Create manual run header.
3. Add one employee line at a time.
4. Validate gross/net totals.
5. Create run.
6. Review run table.
7. Post run to journal when approved.

Expected result:
- Balanced payroll journal with statutory and other deduction payables.

## 8.11 Journals (`/journals`)

### Purpose
- Manual accounting entries only when needed.

Line fields:
- account_code
- account_name
- debit
- credit
- memo

Rules:
- Total debit must equal total credit.

SOP:
1. Create header.
2. Add line pairs.
3. Check balance indicator.
4. Save entry.

## 8.12 BIR (`/bir`)

### Purpose
- Selective inclusion, generation, and lock control.

Candidate row fields:
- include_in_bir checkbox
- book_type
- tax_type
- notes

SOP:
1. Choose period.
2. Review all candidate rows.
3. Check include only for intended entries.
4. Save inclusion list.
5. Generate books.
6. Lock period after sign-off.

## 8.13 Assets (`/assets`)

### Purpose
- Track full asset lifecycle.

### Acquisition fields
- name, class, location, cost, date, payment, counterparty, useful life, salvage

### Depreciation fields
- asset/period/date/amount/auto_post

### Maintenance fields
- asset/date/vendor/amount/payment/auto_post

### Disposal fields
- asset/date/proceeds/writeoff/payment/auto_post

SOP:
1. Register asset on acquisition.
2. Run monthly depreciation.
3. Log maintenance as incurred.
4. Process disposal when asset retired.

## 9) Scenario playbook (step-by-step)

Each scenario includes:
- trigger
- exact steps
- expected result
- verification checks

## Scenario 1 - New walk-in booking with deposit

Trigger:
- Guest books directly and pays deposit.

Steps:
1. Open `Bookings`.
2. Fill booking fields:
   - `guest_name`
   - `room_name`
   - `channel = Walk-in`
   - `status = confirmed`
   - `check_in`, `check_out`
   - `gross_amount`
   - `deposit_amount`
   - `payment_method = cash` (or actual method)
3. If policy requires immediate accounting linkage, set `auto_post_accounting = true`.
4. Click `Save Booking`.

Expected result:
- Booking appears in list.
- If auto-post enabled, accounting link rows appear for room income and deposit liability.

Verification:
- No date error.
- Gross/deposit values match agreement.

## Scenario 2 - OTA booking (no immediate cash received)

Trigger:
- Booking comes from Agoda/Booking etc.

Steps:
1. Create booking with `channel` set to OTA platform.
2. Set `payment_method = ota_payout`.
3. Save booking.
4. Optional accounting linkage according to policy.

Expected result:
- Booking tracked with OTA context.
- Channel payout can later be matched via `booking_ref`.

## Scenario 3 - Guest checkout with deposit clearing

Trigger:
- Guest checks out.

Steps:
1. In booking list, click `Check Out` or edit status to `checked_out`.
2. Set `effective_date` as actual checkout date when needed.
3. Keep `auto_reverse_on_cancel` unchanged (not relevant for checkout).
4. Save update.

Expected result:
- Status updated.
- If accounting linkage enabled in update flow, deposit clearing entry may be created.

Verification:
- Booking status = checked_out.
- Linked accounting entries are sensible and not duplicated.

## Scenario 4 - Booking cancellation with reversal

Trigger:
- Confirmed booking gets cancelled.

Steps:
1. Open booking row and click `Cancel` (or update status).
2. Ensure `auto_reverse_on_cancel = true` if reversal should happen.
3. Save.

Expected result:
- Booking status cancelled.
- Optional reversal liability entries created if accounting automation enabled.

## Scenario 5 - Included room breakfast claimed

Trigger:
- Room guest consumes included breakfast.

Steps:
1. Go to `Bookings` > `Room Breakfast Posting`.
2. Select `booking_id`.
3. Set `meal_date`, choose menu/SKU, set quantity.
4. Set `charge_to_room = true` and leave charged amount blank for auto charge logic when appropriate.
5. Post breakfast.

Expected result:
- Inventory deducted.
- Breakfast log created.
- Optional linked accounting records if enabled.

## Scenario 6 - Paid extra breakfast to room

Trigger:
- Guest consumes paid breakfast not included in package.

Steps:
1. Post breakfast log with `charge_to_room = true`.
2. Enter exact `charged_amount` if overriding auto value.
3. Enable auto accounting if policy requires immediate posting.
4. Save.

Expected result:
- Revenue + COGS linkage possible.
- Booking can reference linked breakfast accounting entries.

## Scenario 7 - Restaurant sale (strict inventory, no auto accounting)

Trigger:
- Daily normal sale where accounting is posted later manually.

Steps:
1. Open `Restaurant Ops`.
2. In `Quick Sale`, enter header fields.
3. Keep `strict_inventory = true`.
4. Set `auto_post_accounting = false`.
5. Add line(s): menu/SKU, quantity, unit price/discount.
6. Click `Post Sale`.

Expected result:
- Sale order posted.
- Inventory deducted FIFO.
- COGS computed.
- No automatic accounting records.

## Scenario 8 - Restaurant sale with auto accounting

Trigger:
- Policy allows immediate accounting linkage for sale.

Steps:
1. Same as Scenario 7.
2. Set `auto_post_accounting = true` before posting.

Expected result:
- Sale order posted.
- Inventory deduction and COGS.
- Income and COGS records linked automatically.

## Scenario 9 - Restock with linked expense

Trigger:
- Supply delivery received and should hit accounting.

Steps:
1. In `Quick Restock`, select item and quantity.
2. Enter `unit_cost`, `reference_no`, `supplier`, `movement_date`.
3. Set `log_expense = true`.
4. Choose expense module/payment/counterparty.
5. Save.

Expected result:
- Stock-in movement saved.
- Inventory and average cost updated.
- Expense record linked to movement.

## Scenario 10 - Staff meal with mixed recipe + manual ingredient

Trigger:
- Staff dish uses standard recipe plus extra ingredient.

Steps:
1. Open `Staff Meals`.
2. Fill header including dish name and quantity.
3. Select menu item/SKU if recipe exists.
4. Add manual ingredient line(s).
5. Set `strict_inventory = true`.
6. Save log.

Expected result:
- Combined requirements deducted from stock.
- COGS captured.
- Optional expense record linked if enabled.

## Scenario 11 - Stock-out for spoilage/breakage

Trigger:
- Inventory loss discovered.

Steps:
1. Open `Stock Movements`.
2. Select `movement_type = out`.
3. Enter quantity and reason (`Count Loss`, `Spoilage`, etc.).
4. Add reference and date.
5. Save.

Expected result:
- FIFO stock reduced.
- Optional expense record if enabled.

## Scenario 12 - Drawer to bank cash transfer

Trigger:
- Cash drop from drawer to bank.

Steps:
1. Open `Treasury` > `New Movement`.
2. Set `movement_type = transfer`.
3. Set `from_account_id = drawer`, `to_account_id = bank`.
4. Enter amount, date, reference.
5. Optional linked finance record toggle.
6. Save.

Expected result:
- Drawer decreases, bank increases.
- Single treasury movement with both account sides.

## Scenario 13 - Cash expense paid from drawer

Trigger:
- Petty expense paid physically from drawer.

Steps:
1. Treasury movement type `out`.
2. Set `from_account_id` drawer.
3. Enter amount, reference, counterparty.
4. Optional create linked finance record with direction `expense`.
5. Save.

Expected result:
- Drawer balance reduced.
- Optional linked expense record created.

## Scenario 14 - Daily drawer reconciliation

Trigger:
- End-of-day drawer balancing.

Steps:
1. In `Treasury`, open `Reconciliation` section.
2. Select drawer account.
3. Set `as_of_date`.
4. Enter physical count in `statement_balance`.
5. Save.

Expected result:
- System balance and variance computed.
- Variance tracked for investigation.

## Scenario 15 - Payroll run from external payroll summary

Trigger:
- Payroll period closed in external payroll system.

Steps:
1. Open `Payroll`.
2. Fill run header (name, period start/end, release date).
3. Add each employee payroll line with hour buckets and deductions.
4. Review run totals.
5. Create run.
6. Click `Post to Journal` after approval.

Expected result:
- Payroll run saved.
- Balanced journal entry posted.
- Statutory and other deduction liabilities captured.

## Scenario 16 - BIR selective inclusion and period lock

Trigger:
- Month-end compliance preparation.

Steps:
1. Open `BIR`.
2. Select target period.
3. Review each candidate row.
4. Check include only on intended rows.
5. Set `book_type` and `tax_type` where needed.
6. Save inclusion list.
7. Generate books.
8. After final review, lock period.

Expected result:
- Generated books include only selected entries.
- Locked period blocks accidental backdated changes.

## Scenario 17 - Asset acquisition with accounting linkage

Trigger:
- New equipment purchased.

Steps:
1. Open `Assets` and add asset profile.
2. Fill acquisition cost/date/payment/counterparty.
3. Set useful life and salvage.
4. Set `auto_post_accounting = true` if policy requires immediate capitalization entry.
5. Save.

Expected result:
- Asset record stored.
- Optional linked acquisition accounting entry.

## Scenario 18 - Monthly depreciation run

Trigger:
- End-of-month depreciation posting.

Steps:
1. Open `Assets` > `Depreciation`.
2. For single asset: select asset, period key, optional amount override.
3. For all assets: use `Batch Depreciation`.
4. Set auto accounting by policy.
5. Run.

Expected result:
- Depreciation logs created.
- Optional expense entries created.

## Scenario 19 - Asset maintenance

Trigger:
- Repair or preventive maintenance incurred.

Steps:
1. Open `Assets` > `Maintenance`.
2. Select asset, date, vendor, amount.
3. Choose payment method and accounting toggle.
4. Save.

Expected result:
- Maintenance log created.
- Optional linked expense record.

## Scenario 20 - Asset disposal

Trigger:
- Asset sold/scrapped.

Steps:
1. Open `Assets` > `Disposal`.
2. Select asset and disposal date.
3. Fill proceeds and writeoff values.
4. Set accounting toggle as policy.
5. Save.

Expected result:
- Asset status set to Disposed.
- Disposal log created.
- Optional proceeds/writeoff accounting entries linked.

## Scenario 21 - OTA payout lifecycle

Trigger:
- OTA booking commission and payout flow.

Steps:
1. Create payout row in `Channel Payouts`.
2. Enter gross, commission, net, expected payout date.
3. Update status as it progresses.
4. On payout receipt, click `Settle`.
5. Reconcile against bank treasury movement.

Expected result:
- Payout status traceable end-to-end.
- Optional accounting links for commission and settlement.

## 10) Field-level error prevention guide

Use this before clicking Save on any page:

1. Date is correct and not future/past by mistake.
2. Amount fields are not accidentally zero.
3. Quantity and unit match each other.
4. Counterparty and reference are filled when money is involved.
5. Auto-post toggles reflect current policy.
6. For inventory flows, strict mode is intentionally set.

## 11) Reconciliation matrix (what to compare)

### Daily

- Treasury drawer movement total vs physical cash
- Restaurant sales posted vs POS summary (if external POS exists)
- Breakfast logs vs served count

### Weekly

- Inventory usage vs actual consumption trend
- Channel payout pending vs expected schedule
- Treasury bank movement vs online bank balance

### Monthly

- Payroll run totals vs external payroll source
- BIR inclusion list vs management-approved set
- Generated books vs period lock state

## 12) What to do when something is wrong

## 12.1 Wrong amount encoded

1. If editable in page, update record immediately.
2. Add correction note with reason.
3. If linked accounting already posted, coordinate with accountant for proper reversal/adjustment.

## 12.2 Wrong date encoded

1. Correct before period lock.
2. If period locked, escalate to accountant/admin for unlock decision per policy.

## 12.3 Duplicate entry suspected

1. Search by reference number.
2. Compare timestamps and counterparties.
3. Keep one valid entry; reverse/delete according to permission and policy.
4. Document what was corrected.

## 12.4 Inventory mismatch

1. Verify recent stock movements for item.
2. Check staff meal and sale postings.
3. Post adjustment movement only after count confirmation.
4. Add note with investigation reference.

## 12.5 Treasury variance

1. Recount physical cash.
2. Re-check movements for missing/incorrect line.
3. Verify transfer pairings.
4. Escalate unresolved variance to supervisor + accountant same day.

## 13) Training checklist for new staff

Day 1:
- Login and navigation
- Booking encode + edit
- Breakfast posting

Day 2:
- Restaurant quick sale + restock
- Staff meal logging
- Inventory item and stock movement basics

Day 3:
- Treasury movement and reconciliation
- Channel payout update
- Error correction standards

Day 4:
- Record page taxonomy usage
- Workflow and approvals
- BIR inclusion concept

Day 5:
- Shadow real daily close using this playbook

## 14) Supervisor sign-off checklist

Use this each end-of-day:

- [ ] Bookings complete and statuses updated
- [ ] Breakfast logs complete
- [ ] Sales/restocks/staff meals complete
- [ ] Treasury movements complete
- [ ] Drawer reconciliation done
- [ ] Exceptions documented
- [ ] No unresolved high-risk errors

Use this each month-end:

- [ ] All modules reviewed
- [ ] Payroll posted and checked
- [ ] Assets events posted
- [ ] BIR selections finalized
- [ ] Books generated
- [ ] Period lock applied

## 15) Quick page index

- `Bookings`: room lifecycle and breakfast posting
- `Restaurant Ops`: sales, restock, menu/component/sku/promo management
- `Staff Meals`: internal meal inventory usage
- `Inventory Items`: item master
- `Stock Movements`: FIFO stock in/out
- `Treasury`: drawer/bank movement + reconciliation
- `Payroll`: period payroll run creation and posting
- `Employees`: employee master and attendance
- `Channel Payouts`: OTA commission and settlement tracking
- `Assets`: acquisition, depreciation, maintenance, disposal
- `Journals`: manual balanced entries
- `BIR`: selective inclusion, generation, lock
- `Master Data`: reusable setup values
- `Taxonomy Admin`: accounting classification tree
- `Users`: user access control

## 16) Final instruction to all encoders

If unsure:
1. Stop and do not guess.
2. Check the matching scenario section in this playbook.
3. Ask supervisor before posting with auto accounting enabled.
4. Keep all references and notes clean.

Good encoding discipline is what makes reports accurate.
