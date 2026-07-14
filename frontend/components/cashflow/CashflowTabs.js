'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const TABS = [
  ['/cashflow', 'Cash & Treasury'],
  ['/cashflow/receivables', 'Receivables'],
  ['/cashflow/payables', 'Payables'],
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
