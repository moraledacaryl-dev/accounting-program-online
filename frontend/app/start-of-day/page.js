import Link from 'next/link';

const START_STEPS = [
  {
    title: 'Check Today',
    detail: 'Review arrivals, departures, pending approvals, low stock, cash movement, and anything already overdue.',
    href: '/dashboard',
    action: 'Open Dashboard',
  },
  {
    title: 'Confirm Booking Sync',
    detail: 'For front desk or manager: make sure Beds24 sync is healthy before staff rely on arrivals and folios.',
    href: '/integrations/beds24',
    action: 'Check Beds24',
  },
  {
    title: 'Review Payments to Receive',
    detail: 'Look for guest, OTA, event, company, or group balances that need collection today.',
    href: '/cashflow/receivables',
    action: 'Open Payments',
  },
  {
    title: 'Review Bills to Pay',
    detail: 'Check supplier, utility, payroll/government, tax, and service provider bills due soon.',
    href: '/cashflow/payables',
    action: 'Open Bills',
  },
  {
    title: 'Check Deliveries',
    detail: 'Post received deliveries so stock updates and supplier bills are created when needed.',
    href: '/receiving',
    action: 'Receive Delivery',
  },
  {
    title: 'Count Cash Drawers',
    detail: 'Count active drawers, petty cash, and safes at shift start or handover. Banks can be checked periodically.',
    href: '/cashflow/daily-cash',
    action: 'Count Cash',
  },
];

export default function StartOfDayPage() {
  return (
    <div className="stack">
      <section className="section">
        <h1>Start of Day</h1>
        <p className="muted">
          Use this as the morning or shift-opening checklist. It points staff to the actual pages that create records,
          collect balances, receive deliveries, and count cash.
        </p>
      </section>

      <section className="section">
        <h2>Opening Checklist</h2>
        <div className="process-list">
          {START_STEPS.map((step, index) => (
            <div key={step.title} className="process-step">
              <div className="process-step-number">{index + 1}</div>
              <div>
                <strong>{step.title}</strong>
                <p className="small muted">{step.detail}</p>
              </div>
              <Link href={step.href} className="secondary">{step.action}</Link>
            </div>
          ))}
        </div>
      </section>

      <section className="section">
        <h2>Manager Notes</h2>
        <div className="card-grid" style={{ marginTop: 10 }}>
          <div className="card">
            <strong>Bank checks</strong>
            <p className="small muted">Check banks periodically or when closing a reporting period, not necessarily every day.</p>
          </div>
          <div className="card">
            <strong>Bookings</strong>
            <p className="small muted">Use Beds24 as the booking source when that is the operational plan, then verify sync here.</p>
          </div>
          <div className="card">
            <strong>Products</strong>
            <p className="small muted">Menu and inventory setup should stay in accounting as the source for POS and operations.</p>
          </div>
        </div>
      </section>
    </div>
  );
}
