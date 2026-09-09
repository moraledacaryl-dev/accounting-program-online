# Accounting sidebar and complete navigation review

The sidebar is the primary navigation. The location trail uses the same route map and group names. Local tabs change views within the current workspace; they do not need separate sidebar entries unless they are independently useful destinations. Child-page links belong only to one sidebar destination.

## Changes

- Submenu text now starts at approximately x=44px, nearly aligned with main group labels. Group icons, stronger headings, a soft expanded background, and a vertical guide communicate hierarchy without deep indentation.
- Replaced five unrelated context-navigation registries with one sidebar-derived location component. Removed the obsolete CashflowTabs row from Receivables, account history and recurring templates.
- Payables stays under Purchases & Payables; Receivables under Sales & Receivables; Approvals under Overview; Staff Guide under Administration. None receives an unrelated payroll, inventory or finance menu.
- Added direct Cash Ledger and Cash Settings sidebar destinations. Transfers has a dedicated register view, rather than opening a create drawer under Daily Close. Browser back/forward and direct URL navigation select the correct cash view. Closing a URL-launched money drawer clears its stale action selection.
- Split Users and Roles & Permissions into explicit destinations and exposed Taxonomies separately. Sidebar, search, child links and route guards share access rules. Parents route to an accessible child when the user cannot access the default child.
- Child pages are searchable and highlight their parent sidebar entry. Inventory-owned meal/menu pages resolve under Inventory; Payroll history resolves under Payroll Integration.
- Status/view controls expose their selected state. Raw tax/approval keys are replaced with readable names. View buttons wrap on small screens instead of hiding labels offscreen.

## Every active view group

| Screen | Views | Decision |
| --- | --- | --- |
| Dashboard | Arrivals; Departures; In-house | Keep: filters one guest-movement card. |
| Cash & Treasury | Cash Overview; Cash Ledger; Transfers; Daily Close & Reconciliation; Cash Settings | Keep one row, matching sidebar destinations. Remove the extra finance bar. |
| Reports | Overview; Financial Statements; Rooms, F&B & Inventory; AR, AP & Settlements; Payroll & BIR | Keep: subdivisions of Reports, not navigation to operational apps. |
| Tax & Period Close | Review; Missing Documents; Candidate Records; Tax Books; Period Locks | Keep, with readable labels. |
| Approvals | Records; Procurement; Money Transactions; Payroll; Journal Entries; Reconciliations | Keep: different queues within Approvals. Remove People & Payroll bar. |
| Payroll Integration | For Review; Ready to Post; Posted; Rejected; Errors; Already Applied | Keep: status filters of the review table, exposed as pressed buttons. |
| Retained payroll period | Summary; Reports | Keep history views; remove Input, Import and Posting tabs whose mutation controls are blocked in Accounting. |

These are 32 active view buttons across seven groups. The four legacy Restaurant catalog builder tabs remain hidden by the existing read-only ownership boundary and are tested as hidden. Old ModuleWorkspace tab configurations are not mounted: workspace and record URLs redirect to canonical pages. Generic UI Tab exports have no current page consumers.

## Child-page navigation

| Sidebar parent | Related pages |
| --- | --- |
| Bookings | Bookings; Calendar |
| Rooms & Rates | Room Types; Rooms; Rate Plans; Package Rules; Booking Channels |
| Inventory | Items; Stock Movements; Menu & Recipes; Menu Categories; Staff Meals; Setup Imports |
| Payroll Integration | Payroll Review Queue; Employee History; Attendance History; Payroll Period History |
| Cash Settings | Cash Settings; Recurring Templates (cash workspace itself already has its local row) |

These links follow permissions and resolve to an existing route. Operational pages remain read-only handoffs/history; this navigation change does not add staff-meal entry or restore removed ownership permissions.

## Route-by-route inventory

All 71 page files are accounted for: the 68 route cases below, login covered by session-entry tests, and two dynamic legacy route templates covered with all ten configured module aliases. Detail pages use fixture IDs. Unknown workspace modules retain not-found behavior.

| Route | Sidebar group |
| --- | --- |
| `/dashboard` | overview |
| `/start-of-day` | overview |
| `/review-inbox` | overview |
| `/approvals` | overview |
| `/` | overview |
| `/cashflow` | money |
| `/cashflow/ledger` | money |
| `/cashflow/settings` | money |
| `/cashflow/money-in` | money |
| `/cashflow/money-out` | money |
| `/cashflow/transfers` | money |
| `/cashflow/daily-cash` | money |
| `/cashflow/reconciliation` | money |
| `/cashflow/accounts` | money |
| `/cashflow/templates` | money |
| `/cashflow/1` | money |
| `/treasury` | money |
| `/cashflow/receivables` | sales |
| `/bookings` | sales |
| `/bookings/calendar` | sales |
| `/bookings/1` | sales |
| `/guests` | sales |
| `/guests/1` | sales |
| `/room-folios` | sales |
| `/room-folios/1` | sales |
| `/channel-payouts` | sales |
| `/events` | sales |
| `/cashflow/payables` | purchases |
| `/suppliers` | purchases |
| `/purchase-requests` | purchases |
| `/purchase-orders` | purchases |
| `/receiving` | purchases |
| `/journals` | accounting |
| `/chart-of-accounts` | accounting |
| `/account-mapping` | accounting |
| `/bir` | accounting |
| `/assets` | accounting |
| `/reports` | accounting |
| `/attachments` | accounting |
| `/integrations/beds24` | integrations |
| `/integrations/payroll` | integrations |
| `/restaurant-ops` | integrations |
| `/inventory-items` | integrations |
| `/inventory-reconciliation` | integrations |
| `/stock-movements` | integrations |
| `/menu-items` | integrations |
| `/menu-categories` | integrations |
| `/recipes` | integrations |
| `/staff-meals` | integrations |
| `/setup-imports` | integrations |
| `/employees` | integrations |
| `/attendance` | integrations |
| `/payroll-periods` | integrations |
| `/payroll-periods/1` | integrations |
| `/payroll` | integrations |
| `/room-types` | administration |
| `/rooms` | administration |
| `/room-setup` | administration |
| `/rate-plans` | administration |
| `/room-package-rules` | administration |
| `/booking-channels` | administration |
| `/channels` | administration |
| `/users` | administration |
| `/roles-permissions` | administration |
| `/master-data` | administration |
| `/taxonomy-admin` | administration |
| `/system-settings` | administration |
| `/staff-guide` | administration |

## Verification scope

Final local validation: **149 browser tests passed**, production build and source contracts passed, and ten screenshot scenarios completed and were inspected.

The suite includes route ownership, exactly one current sidebar destination, tab/view switching, cash URL history, restricted-role link destinations, search for child pages, session entry, drawers, contrast and phone/tablet geometry. Production builds and UI source contracts are checked. Screenshots cover Reports, Transfers, Approvals, Rooms & Rates and Inventory at 390px and 1440px plus the phone sidebar.

Local route tests use mocked API data. They verify navigation, not every populated business workflow. Live post-deployment checks and release IDs are recorded in the workspace audit artifact.

## Dependency audit follow-up

The first CI run stopped at its production dependency audit. The release now pins Next.js 16.3.4 and resolves sharp 0.35.4, addressing the reviewed [Next.js image optimization advisory](https://github.com/advisories/GHSA-2xp9-vwfh-vxw4), [Windows-hosted Next.js advisory](https://github.com/advisories/GHSA-p293-qw3h-jr36), and [sharp/libheif advisory](https://github.com/advisories/GHSA-rgj7-g3m4-5g8c). The production dependency audit reports zero known vulnerabilities after the update. Navigation tests and the production build were rerun against the patched versions.
