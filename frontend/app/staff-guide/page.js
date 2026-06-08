import Link from 'next/link';

const DAILY_FLOW = [
  {
    title: 'Start the day or shift',
    page: 'Start of Day',
    href: '/start-of-day',
    steps: [
      'Open the Start of Day page.',
      'Check today, payments to receive, bills to pay, deliveries, and cash drawers.',
      'Only check banks when a manager asks or when closing a period.',
    ],
    done: 'Staff knows what needs attention before serving guests.',
  },
  {
    title: 'Receive a payment',
    page: 'Cashflow > To Receive',
    href: '/cashflow/receivables',
    steps: [
      'Find the guest, OTA, event, company, or group balance.',
      'Click Receive or Collect.',
      'Enter amount, account, method, and reference if available.',
      'Save the payment.',
    ],
    done: 'The open balance is reduced and the money account is updated.',
  },
  {
    title: 'Create a balance to collect later',
    page: 'Cashflow > To Receive',
    href: '/cashflow/receivables',
    steps: [
      'Click Add Balance to Collect.',
      'Enter customer or source, type, date, due date, and total amount.',
      'Leave Already Collected as 0 if no payment was received yet.',
      'Save the balance.',
    ],
    done: 'The balance appears in Payments to Receive for follow-up.',
  },
  {
    title: 'Record an expense',
    page: 'Cashflow > Money Out',
    href: '/cashflow/money-out?preset=operating-expense',
    steps: [
      'Choose date and account used.',
      'Choose the area and reason.',
      'Enter amount, method, payee, and reference if available.',
      'Attach proof if available.',
      'Save Money Out.',
    ],
    done: 'The expense is recorded and the account balance changes.',
  },
  {
    title: 'Pay a supplier or bill',
    page: 'Cashflow > To Pay',
    href: '/cashflow/payables',
    steps: [
      'Find the open bill.',
      'Click Pay.',
      'Enter amount, account used, method, and reference if available.',
      'Save the supplier payment.',
    ],
    done: 'The bill balance is reduced and the money account is updated.',
  },
  {
    title: 'Create a bill to pay later',
    page: 'Cashflow > To Pay',
    href: '/cashflow/payables',
    steps: [
      'Click Add Bill to Pay.',
      'Enter supplier, bill type, date, due date, and bill amount.',
      'Leave Already Paid as 0 if nothing was paid yet.',
      'Save the bill.',
    ],
    done: 'The bill appears in Bills to Pay for follow-up.',
  },
  {
    title: 'Receive a delivery',
    page: 'Receiving',
    href: '/receiving',
    steps: [
      'Open Receiving.',
      'Enter or open the delivery record.',
      'Check supplier, items, quantities, costs, and reference.',
      'Keep Create Supplier Bill as Yes when the delivery should become a bill.',
      'Post the delivery.',
    ],
    done: 'Stock updates and a supplier bill is created when needed.',
  },
  {
    title: 'Count cash',
    page: 'Cashflow > Cash Count',
    href: '/cashflow/daily-cash',
    steps: [
      'Choose the drawer, petty cash, safe, bank, or e-wallet account.',
      'Enter date, shift, and counted amount.',
      'Check the difference shown by the system.',
      'Add a note if there is a difference.',
      'Save Count.',
    ],
    done: 'The cash count is saved for manager review.',
  },
  {
    title: 'Move money between accounts',
    page: 'Cashflow > Transfers',
    href: '/cashflow/transfers',
    steps: [
      'Choose the date.',
      'Choose From and To accounts.',
      'Enter amount and reference if available.',
      'Save Transfer.',
    ],
    done: 'Money is moved between accounts in the system.',
  },
  {
    title: 'Check banks or exceptions',
    page: 'Cashflow > Periodic Checks',
    href: '/cashflow/reconciliation?tab=bank',
    steps: [
      'Open Periodic Checks.',
      'Use Cash, Bank, OTA, To Receive, or To Pay tabs.',
      'Review only what needs checking.',
      'Use this for manager review or period closing, not normal daily work.',
    ],
    done: 'Open issues are visible for follow-up.',
  },
];

const FRONT_DESK_FLOW = [
  {
    title: 'Check booking sync',
    page: 'Beds24 Integration',
    href: '/integrations/beds24',
    steps: [
      'Open Beds24 Integration.',
      'Check that sync is healthy.',
      'Run manual sync only when needed or instructed.',
    ],
    done: 'Arrivals, bookings, and folios are based on the latest available sync.',
  },
  {
    title: 'Use bookings, guests, and folios',
    page: 'Rooms & Guests',
    href: '/workspace/rooms',
    steps: [
      'Use Bookings for reservation work.',
      'Use Guests for guest details.',
      'Use Folios for charges, payments, deposits, refunds, and balances.',
    ],
    done: 'Guest records and balances stay connected.',
  },
  {
    title: 'Repair old booking charge types',
    page: 'Booking Detail or Beds24 Integration',
    href: '/integrations/beds24',
    steps: [
      'Use Booking Detail when repairing one reservation.',
      'Use Beds24 Integration > Folio Line Classification when reviewing all old Beds24 bookings.',
      'Always run Preview first and read the sample changes.',
      'Apply only after the balance adjustment makes sense.',
      'Open the folio after applying and confirm charges, deposits, payments, refunds, and balances.',
    ],
    done: 'Old folio rows are classified by context without changing amounts or creating duplicate lines.',
  },
  {
    title: 'Track events',
    page: 'Events',
    href: '/events',
    steps: [
      'Create the event quote with client details, date, venue, package, and quote lines.',
      'Confirm the event when it is accepted so Accounting creates the receivable and journal entry.',
      'Record deposits or balance payments on the event page so the payment settles the receivable.',
    ],
    done: 'Event details, balances, payments, and accounting links stay together.',
  },
];

const POS_FLOW = [
  {
    title: 'Take a restaurant order',
    page: 'Dedicated POS > POS',
    href: '/staff-guide',
    steps: [
      'Select or open the correct register session.',
      'Choose the service area, table, room service, or takeout.',
      'Add menu items, variations, quantities, and item notes.',
      'Hold the order only when the guest is not paying yet.',
      'Use Pay when the order is ready to settle.',
    ],
    done: 'The order is saved once in POS and appears in the kitchen/service queue.',
  },
  {
    title: 'Send a room charge from POS',
    page: 'Dedicated POS > POS and Room Charges',
    href: '/staff-guide',
    steps: [
      'Choose Room Charge in the payment popup.',
      'Match the in-house booking by room or guest.',
      'Finalize the order to create a pending room-charge queue item.',
      'Front desk manually posts the charge to Beds24 and records the posting reference.',
      'Mark settled only when final payment or folio settlement is confirmed.',
    ],
    done: 'Service date, folio posting status, and payment date stay separate.',
  },
  {
    title: 'Work with limited connection',
    page: 'Dedicated POS > POS',
    href: '/staff-guide',
    steps: [
      'Check the POS sync banner and browser connection badge.',
      'If connection is down, save only an emergency offline draft for order-taking continuity.',
      'Do not mark payments or room charges as completed while offline.',
      'Restore the draft after connection returns, then save or settle normally.',
    ],
    done: 'Staff keep the order details without pretending money or folio posting has synced.',
  },
];

const BACK_OFFICE_FLOW = [
  {
    title: 'Request or order supplies',
    page: 'Inventory & Purchasing',
    href: '/workspace/inventory',
    steps: [
      'Use Purchase Requests when staff need approval before buying.',
      'Use Purchase Orders when ordering from suppliers.',
      'Use Receiving when items actually arrive.',
    ],
    done: 'Purchasing, delivery, stock, and supplier bills stay connected.',
  },
  {
    title: 'Manage staff payroll work',
    page: 'People & Payroll',
    href: '/workspace/payroll',
    steps: [
      'Use Employees for staff records.',
      'Use Attendance for attendance input and review.',
      'Use Payroll Periods for payroll runs.',
      'Use Approvals for items waiting for review.',
    ],
    done: 'Staff records, attendance, payroll, and approvals stay in one flow.',
  },
  {
    title: 'Manage menu and stock setup',
    page: 'Restaurant & F&B',
    href: '/workspace/restaurant',
    steps: [
      'Use Menu Items for menu setup.',
      'Use Menu Categories for menu grouping.',
      'Use Recipes for costing and ingredient links.',
      'Use Staff Meals to record internal meal consumption.',
    ],
    done: 'F&B setup stays connected to POS and inventory logic.',
  },
];

const SAFETY_RULES = [
  'If the entry is wrong and Edit is available, edit it first.',
  'Use More only for manager actions like reverse, write off, cancel, or delete.',
  'Do not post accounting now unless manager/accounting tells you to.',
  'Do not create duplicate guests, suppliers, products, or accounts just because you cannot find one. Search first.',
  'Always add a note when cash count, payment, bill, or delivery does not match expected amount.',
];

const HOT_SITUATIONS = [
  {
    title: 'POS sync banner is not green',
    page: 'POS > Sync Queue',
    href: '/staff-guide',
    steps: [
      'Tell the manager before forcing any retry.',
      'Manager checks database migration, Accounting reachability, worker heartbeat, and failed rows.',
      'Do not re-enter paid POS sales in Accounting.',
    ],
    done: 'The cause is fixed before retrying, with no duplicate sale or payment.',
  },
  {
    title: 'Drawer mapping is missing',
    page: 'POS > Registers',
    href: '/staff-guide',
    steps: [
      'Ask a manager to open POS Registers.',
      'Use the Accounting account picker and validate the real drawer.',
      'Do not type a random ID just to open or close the shift.',
    ],
    done: 'The register is linked to its real Accounting drawer.',
  },
  {
    title: 'Wrong room charge or folio',
    page: 'POS > Room Charges',
    href: '/staff-guide',
    steps: [
      'Mark the queue item disputed or rejected with a reason.',
      'Keep the POS order and Beds24 references.',
      'Supervisor corrects the folio and records proof.',
    ],
    done: 'The wrong charge is traceable and the correct folio is updated once.',
  },
  {
    title: 'POS server is unavailable',
    page: 'Manual outage log',
    href: '/staff-guide',
    steps: [
      'Stop assuming browser actions are saved.',
      'Record time, items, amount, tender, proof, and staff initials once in the approved outage log.',
      'Manager encodes controlled outage fallback only after recovery.',
    ],
    done: 'Recovery encoding happens once without duplicate POS sales.',
  },
];

function ProcessCard({ item }) {
  return (
    <article className="guide-card">
      <div className="row" style={{ justifyContent: 'space-between', gap: 10 }}>
        <div>
          <h3>{item.title}</h3>
          <p className="small muted">{item.page}</p>
        </div>
        <Link className="button-link secondary-link" href={item.href}>Open</Link>
      </div>
      <ol className="guide-steps">
        {item.steps.map((step) => <li key={step}>{step}</li>)}
      </ol>
      <p className="guide-done"><strong>Done when:</strong> {item.done}</p>
    </article>
  );
}

function ProcessSection({ title, subtitle, items }) {
  return (
    <section className="section">
      <h2>{title}</h2>
      <p className="muted">{subtitle}</p>
      <div className="guide-grid">
        {items.map((item) => <ProcessCard key={item.title} item={item} />)}
      </div>
    </section>
  );
}

export default function StaffGuidePage() {
  return (
    <div className="stack">
      <section className="section">
        <h1>Staff Process Guide</h1>
        <p className="muted">
          Simple steps for the processes that already exist in this app. Use this when training new staff or when someone is unsure where to start.
        </p>
        <div className="row wrap" style={{ marginTop: 12 }}>
          <a className="button-link" href="/guides/HIDDEN_OASIS_STAFF_READY_GUIDE.md" download>Download Full Staff Handbook</a>
        </div>
      </section>

      <ProcessSection
        title="Daily Staff Work"
        subtitle="The most common tasks for front desk, cashier, finance, purchasing, and shift staff."
        items={DAILY_FLOW}
      />

      <ProcessSection
        title="Front Desk and Events"
        subtitle="Use these when working with guests, room balances, booking sync, and event balances."
        items={FRONT_DESK_FLOW}
      />

      <ProcessSection
        title="Dedicated POS"
        subtitle="Use these for cashier, room-service, kitchen, and offline-aware order-taking flows."
        items={POS_FLOW}
      />

      <ProcessSection
        title="Back Office"
        subtitle="Use these for purchasing, inventory, payroll, menu setup, and approvals."
        items={BACK_OFFICE_FLOW}
      />

      <ProcessSection
        title="Hot Situations"
        subtitle="Use these when operations are under pressure. The downloadable handbook includes the full exception playbook, exact fields, and step-by-step examples."
        items={HOT_SITUATIONS}
      />

      <section className="section">
        <h2>Safety Rules</h2>
        <div className="guide-rules">
          {SAFETY_RULES.map((rule, index) => (
            <div key={rule} className="guide-rule">
              <span>{index + 1}</span>
              <p>{rule}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
