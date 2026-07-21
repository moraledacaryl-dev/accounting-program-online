'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const links = [
  { href: '/cashflow', label: 'Overview' },
  { href: '/cashflow?tab=ledger', label: 'Ledgers' },
  { href: '/cashflow/daily-cash', label: 'Daily close' },
  { href: '/cashflow/payables', label: 'Payables' },
  { href: '/cashflow/receivables', label: 'Receivables' },
  { href: '/cashflow/reconciliation', label: 'Reconciliation' },
  { href: '/journals', label: 'Journals' },
  { href: '/bir', label: 'Tax & close' },
  { href: '/assets', label: 'Fixed assets' },
  { href: '/reports', label: 'Reports' },
];

const prefixes = ['/cashflow', '/journals', '/bir', '/assets', '/reports', '/attachments'];

function activeFor(pathname, href) {
  const base = href.split('?')[0];
  if (href === '/cashflow') return pathname === '/cashflow';
  if (href.startsWith('/cashflow?tab=ledger')) return false;
  return pathname === base || pathname.startsWith(`${base}/`);
}

export default function FinanceOperationsNav() {
  const pathname = usePathname();
  if (!prefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`))) return null;

  return (
    <nav className="finance-context-nav" aria-label="Finance and accounting sections">
      <div className="finance-context-nav__label">Finance & accounting</div>
      <div className="finance-context-nav__links">
        {links.map((item) => {
          const active = activeFor(pathname, item.href);
          return (
            <Link key={item.href} href={item.href} className={active ? 'finance-context-link is-active' : 'finance-context-link'} aria-current={active ? 'page' : undefined}>
              {item.label}
            </Link>
          );
        })}
      </div>
      <div className="finance-context-nav__actions" aria-label="Common finance actions">
        <Link href="/cashflow?action=money-in" className="finance-action finance-action--in">Money in</Link>
        <Link href="/cashflow?action=money-out" className="finance-action">Money out</Link>
        <Link href="/cashflow?action=transfer" className="finance-action">Transfer</Link>
      </div>
    </nav>
  );
}
