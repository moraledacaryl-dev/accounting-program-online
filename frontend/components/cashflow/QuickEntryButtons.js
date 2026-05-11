import Link from 'next/link';

const DEFAULT_ACTIONS = [
  ['/cashflow/receivables?action=collect', 'Receive Payment'],
  ['/cashflow/money-out?preset=operating-expense', 'Record Expense'],
  ['/cashflow/payables?action=pay', 'Pay Supplier'],
  ['/receiving', 'Receive Delivery'],
  ['/cashflow/daily-cash', 'Count Cash'],
  ['/cashflow/transfers', 'Transfer Money'],
  ['/cashflow/reconciliation?tab=bank', 'Check Banks'],
];

export default function QuickEntryButtons({ actions = DEFAULT_ACTIONS }) {
  return (
    <div className="row wrap">
      {actions.map(([href, label]) => (
        <Link key={href} href={href} className="button-link secondary-link">{label}</Link>
      ))}
    </div>
  );
}
