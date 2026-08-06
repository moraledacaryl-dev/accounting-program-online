import Link from 'next/link';
import './start-of-day.css';

const START_STEPS = [
  {
    title: 'Check today',
    detail: 'Review arrivals, departures, pending approvals, low stock, cash movement, and anything already overdue.',
    href: '/dashboard',
    action: 'Open dashboard',
  },
  {
    title: 'Confirm booking sync',
    detail: 'Verify Beds24 sync health before staff rely on arrivals, room assignments, and folios.',
    href: '/integrations/beds24',
    action: 'Check Beds24',
  },
  {
    title: 'Review payments to receive',
    detail: 'Check guest, OTA, event, company, and group balances that need collection today.',
    href: '/cashflow/receivables',
    action: 'Open receivables',
  },
  {
    title: 'Review bills to pay',
    detail: 'Check supplier, utility, payroll, government, tax, and service-provider obligations due soon.',
    href: '/cashflow/payables',
    action: 'Open payables',
  },
  {
    title: 'Check deliveries',
    detail: 'Post received deliveries so stock and supplier obligations remain current.',
    href: '/receiving',
    action: 'Open receiving',
  },
  {
    title: 'Count cash drawers',
    detail: 'Count active drawers, petty cash, and safes at shift start or handover.',
    href: '/cashflow/daily-cash',
    action: 'Count cash',
  },
];

const OPERATING_NOTES = [
  ['Bank checks', 'Check bank balances when needed or during period close rather than forcing a daily ritual.'],
  ['Booking source', 'Beds24 remains the operational booking source; Accounting verifies the synchronized financial result.'],
  ['Product source', 'Menu and inventory setup remain authoritative in Accounting for connected POS and operations workflows.'],
];

export default function StartOfDayPage() {
  return (
    <div className="start-day-page">
      <header className="start-day-header">
        <div>
          <div className="start-day-eyebrow">Shift opening</div>
          <h1>Start of Day</h1>
          <p>Move through the checks that can affect guest service, settlement, stock, and cash before the day gets busy.</p>
        </div>
        <Link href="/dashboard" className="button-link secondary-link">Back to dashboard</Link>
      </header>

      <div className="start-day-layout">
        <section className="start-day-checklist" aria-labelledby="opening-checklist-title">
          <div className="start-day-section-head">
            <div>
              <h2 id="opening-checklist-title">Opening checklist</h2>
              <p>Six operational checks, ordered by daily impact.</p>
            </div>
            <span className="start-day-count">6 checks</span>
          </div>

          <div className="start-day-steps">
            {START_STEPS.map((step, index) => (
              <article key={step.title} className="start-day-step">
                <div className="start-day-step-number" aria-hidden="true">{index + 1}</div>
                <div className="start-day-step-copy">
                  <strong>{step.title}</strong>
                  <p>{step.detail}</p>
                </div>
                <Link href={step.href} className="start-day-step-action">{step.action}</Link>
              </article>
            ))}
          </div>
        </section>

        <aside className="start-day-notes" aria-labelledby="operating-notes-title">
          <div className="start-day-section-head">
            <div>
              <h2 id="operating-notes-title">Operating notes</h2>
              <p>Context that prevents unnecessary daily work.</p>
            </div>
          </div>

          <div className="start-day-note-list">
            {OPERATING_NOTES.map(([title, detail]) => (
              <div className="start-day-note" key={title}>
                <strong>{title}</strong>
                <p>{detail}</p>
              </div>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}
