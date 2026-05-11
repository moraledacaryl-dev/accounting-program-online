'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const TABS = [
  ['/cashflow', 'Overview'],
  ['/cashflow/accounts', 'Accounts'],
  ['/cashflow/money-in', 'Money In'],
  ['/cashflow/money-out', 'Money Out'],
  ['/cashflow/transfers', 'Transfers'],
  ['/cashflow/daily-cash', 'Cash Count'],
  ['/cashflow/receivables', 'To Receive'],
  ['/cashflow/payables', 'To Pay'],
  ['/cashflow/reconciliation', 'Periodic Checks'],
  ['/cashflow/templates', 'Templates'],
];

export default function CashflowTabs() {
  const pathname = usePathname();
  return (
    <section className="section">
      <div className="tabs" style={{ marginTop: 0 }}>
        {TABS.map(([href, label]) => {
          const active = pathname === href || pathname.startsWith(href + '/');
          return (
            <Link key={href} href={href} className={active ? 'tab active' : 'tab'}>
              {label}
            </Link>
          );
        })}
      </div>
    </section>
  );
}
