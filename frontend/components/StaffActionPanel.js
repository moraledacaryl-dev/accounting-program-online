import Link from 'next/link';

const DEFAULT_ACTIONS = [
  {
    href: '/start-of-day',
    label: 'Start of Day',
    note: 'Open the staff checklist for today, cash, receivables, bills, and deliveries.',
  },
  {
    href: '/cashflow/receivables?action=collect',
    label: 'Receive Payment',
    note: 'Collect guest, OTA, event, or company balances.',
  },
  {
    href: '/cashflow/money-out?preset=operating-expense',
    label: 'Record Expense',
    note: 'Record spending from petty cash, bank, GCash, or card.',
  },
  {
    href: '/cashflow/payables?action=pay',
    label: 'Pay Supplier',
    note: 'Pay an open supplier bill and update the balance.',
  },
  {
    href: '/receiving',
    label: 'Receive Delivery',
    note: 'Receive items, update stock, and create supplier bills if needed.',
  },
  {
    href: '/cashflow/daily-cash',
    label: 'Count Cash',
    note: 'Count drawer, petty cash, safe, or periodic bank balances.',
  },
];

export default function StaffActionPanel({ actions = DEFAULT_ACTIONS, title = 'Staff Actions' }) {
  return (
    <section className="section">
      <h2>{title}</h2>
      <div className="staff-action-grid">
        {actions.map((action) => (
          <Link key={action.href} href={action.href} className="staff-action-card">
            <strong>{action.label}</strong>
            <span>{action.note}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
