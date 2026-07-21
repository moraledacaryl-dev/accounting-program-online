'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const links = [
  { href: '/employees', label: 'Employees' },
  { href: '/attendance', label: 'Attendance' },
  { href: '/payroll-periods', label: 'Payroll periods' },
  { href: '/approvals', label: 'Approvals' },
  { href: '/integrations/payroll', label: 'Payroll integration' },
  { href: '/users', label: 'User accounts' },
  { href: '/roles-permissions', label: 'Roles & permissions' },
  { href: '/staff-guide', label: 'Staff guide' },
];

const prefixes = ['/employees', '/attendance', '/payroll-periods', '/approvals', '/integrations/payroll', '/users', '/roles-permissions', '/staff-guide'];

export default function PeoplePayrollNav() {
  const pathname = usePathname();
  if (!prefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`))) return null;

  return (
    <nav className="people-context-nav" aria-label="People and payroll sections">
      <div className="people-context-nav__label">People & payroll</div>
      <div className="people-context-nav__links">
        {links.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link key={item.href} href={item.href} className={active ? 'people-context-link is-active' : 'people-context-link'} aria-current={active ? 'page' : undefined}>
              {item.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
