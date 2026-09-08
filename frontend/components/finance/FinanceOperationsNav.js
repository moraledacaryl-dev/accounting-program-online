'use client';

import Link from 'next/link';
import { usePathname, useSearchParams } from 'next/navigation';
import { useCurrentUser } from '../../lib/useCurrentUser';

const cashLinks = [
  { href: '/cashflow', label: 'Overview', permission: 'cashflow.view' },
  { href: '/cashflow?tab=ledger', label: 'Ledgers', permission: 'cashflow.view' },
  { href: '/cashflow?tab=close', label: 'Close & reconciliation', permission: 'cashflow.view' },
  { href: '/cashflow/payables', label: 'Payables', permission: 'cashflow.view' },
  { href: '/cashflow/receivables', label: 'Receivables', permission: 'cashflow.view' },
];
const accountingLinks = [
  { href: '/journals', label: 'Journals', permission: 'journals.view' },
  { href: '/reports', label: 'Reports', permission: 'reports.view' },
  { href: '/bir', label: 'Tax & close', permission: 'bir.view' },
  { href: '/assets', label: 'Fixed assets', permission: 'assets.view' },
  { href: '/attachments', label: 'Files & evidence', permission: 'reports.view' },
];

export default function FinanceOperationsNav() {
  const pathname = usePathname();
  const search = useSearchParams();
  const { can } = useCurrentUser();
  const cash = pathname.startsWith('/cashflow');
  const links = cash ? cashLinks : accountingLinks;
  if (!cash && !accountingLinks.some(item => pathname === item.href || pathname.startsWith(`${item.href}/`))) return null;
  return (
    <nav className="finance-context-nav" aria-label="Finance and accounting sections">
      <div className="finance-context-nav__label">{cash ? 'Cash & treasury' : 'Accounting'}</div>
      <div className="finance-context-nav__links">
        {links.filter(item => can(item.permission)).map(item => {
          const [base, query] = item.href.split('?');
          const active = pathname === base && (query ? search.get('tab') === new URLSearchParams(query).get('tab') : base !== '/cashflow' || (!search.get('action') && (!search.get('tab') || search.get('tab') === 'overview')));
          return <Link key={item.href} href={item.href} className={`finance-context-link${active ? ' is-active' : ''}`} aria-current={active ? 'page' : undefined}>{item.label}</Link>;
        })}
      </div>
    </nav>
  );
}
