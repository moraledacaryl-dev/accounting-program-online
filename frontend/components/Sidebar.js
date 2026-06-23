'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { canAccess } from '../lib/permissions';
import { useCurrentUser } from '../lib/useCurrentUser';

const groups = [
  {
    label: 'Main',
    items: [
      { href: '/dashboard', label: 'Dashboard', permissionsAny: ['dashboard.view'] },
      { href: '/start-of-day', label: 'Start of Day', permissionsAny: ['dashboard.view', 'cashflow.view'] },
      { href: '/staff-guide', label: 'Staff Guide', permissionsAny: ['dashboard.view', 'cashflow.view', 'bookings.view', 'guests.view', 'folios.view', 'inventory.view', 'receiving.view', 'payroll_periods.view', 'restaurant.view'] },
    ],
  },
  {
    label: 'Workspaces',
    items: [
      { href: '/workspace/rooms', label: 'Rooms & Guests', permissionsAny: ['bookings.view', 'guests.view', 'folios.view'] },
      { href: '/events', label: 'Events', permissionsAny: ['events.view', 'bookings.view', 'cashflow.view'] },
      { href: '/workspace/restaurant', label: 'Restaurant & F&B', permissionsAny: ['restaurant.view', 'menu.view', 'staff_meals.view'] },
      { href: '/workspace/inventory', label: 'Inventory & Purchasing', permissionsAny: ['inventory.view', 'suppliers.view', 'purchase_requests.view', 'purchase_orders.view', 'receiving.view'] },
      { href: '/workspace/payroll', label: 'People & Payroll', permissionsAny: ['employees.view', 'attendance.view', 'payroll_periods.view', 'approvals.view'] },
      { href: '/workspace/finance', label: 'Finance & Accounting', permissionsAny: ['cashflow.view', 'journals.view', 'reports.view', 'assets.view', 'bir.view'] },
      {
        href: '/workspace/settings',
        label: 'Settings',
        permissionsAny: [
          'master_data.manage',
          'taxonomy.manage',
          'users.manage',
          'roles.manage',
          'chart_of_accounts.manage',
          'account_mapping.manage',
          'system_settings.manage',
          'integrations.view',
          'integrations.manage',
          'integrations.sync',
          'integrations.logs.view',
        ],
      },
    ],
  },
];

const connectedApps = [
  { label: 'Staff & Payroll', href: process.env.NEXT_PUBLIC_STAFF_PAYROLL_APP_URL },
  { label: 'Operations', href: process.env.NEXT_PUBLIC_OPERATIONS_APP_URL },
  { label: 'POS', href: process.env.NEXT_PUBLIC_POS_APP_URL },
].filter((item) => item.href);

const SIDEBAR_KEY = 'erp_sidebar_collapsed_v2';

function collapsedLabel(label) {
  return label
    .split('&')[0]
    .trim()
    .split(' ')
    .map((part) => part.slice(0, 1).toUpperCase())
    .join('')
    .slice(0, 2);
}

function hasAnyPermission(user, keys = []) {
  if (!keys || !keys.length) return true;
  return keys.some((key) => canAccess(user, key));
}

export default function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const { user: currentUser } = useCurrentUser();

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const stored = window.localStorage.getItem(SIDEBAR_KEY);
    setCollapsed(stored === '1');
  }, []);

  useEffect(() => {
    if (typeof document === 'undefined') return;
    document.documentElement.style.setProperty('--sidebar-width', collapsed ? '94px' : '286px');
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(SIDEBAR_KEY, collapsed ? '1' : '0');
    }
  }, [collapsed]);

  const visibleGroups = useMemo(() => {
    return groups
      .map((group) => ({
        ...group,
        items: group.items.filter((item) => hasAnyPermission(currentUser, item.permissionsAny || [])),
      }))
      .filter((group) => group.items.length > 0);
  }, [currentUser]);

  return (
    <aside className={collapsed ? 'sidebar collapsed' : 'sidebar'}>
      <div className="brand">
        <div className="brand-badge">AP</div>
        {!collapsed && (
          <div>
            <h2>Accounting Program</h2>
            <div className="small muted-on-dark">Simple, connected hospitality ERP</div>
          </div>
        )}
        <button
          type="button"
          className="sidebar-toggle"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          onClick={() => setCollapsed((v) => !v)}
        >
          {collapsed ? '>' : '<'}
        </button>
      </div>
      <nav>
        {visibleGroups.map((group) => (
          <div key={group.label} className="nav-group">
            {!collapsed && <div className="nav-group-label">{group.label}</div>}
            {group.items.map((item) => {
              const active = pathname === item.href || pathname.startsWith(item.href + '/');
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={active ? 'active' : ''}
                  title={collapsed ? item.label : undefined}
                >
                  {collapsed ? collapsedLabel(item.label) : item.label}
                </Link>
              );
            })}
          </div>
        ))}
        {connectedApps.length > 0 && (
          <div className="nav-group">
            {!collapsed && <div className="nav-group-label">Connected Apps</div>}
            {connectedApps.map((item) => (
              <a key={item.label} href={item.href} rel="noreferrer" title={collapsed ? item.label : undefined}>
                {collapsed ? collapsedLabel(item.label) : item.label}
              </a>
            ))}
          </div>
        )}
      </nav>
    </aside>
  );
}
