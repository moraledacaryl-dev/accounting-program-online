'use client';

import { useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { useAppShell } from './app-shell/AppShellContext';

const PERMISSION_RULES = [
  { prefix: '/dashboard', any: ['dashboard.view'] },
  { prefix: '/start-of-day', any: ['dashboard.view', 'cashflow.view'] },
  { prefix: '/review-inbox', any: ['approvals.view', 'integrations.view'] },
  { prefix: '/staff-guide', any: ['dashboard.view', 'cashflow.view', 'bookings.view', 'guests.view', 'folios.view', 'inventory.view', 'receiving.view', 'payroll_periods.view', 'restaurant.view'] },
  { prefix: '/events', any: ['events.view', 'bookings.view', 'cashflow.view'] },
  { prefix: '/bookings', any: ['bookings.view'] },
  { prefix: '/guests', any: ['guests.view'] },
  { prefix: '/room-folios', any: ['folios.view'] },
  { prefix: '/room-types', any: ['room_setup.view'] },
  { prefix: '/rooms', any: ['room_setup.view'] },
  { prefix: '/rate-plans', any: ['room_setup.view'] },
  { prefix: '/booking-channels', any: ['room_setup.view'] },
  { prefix: '/channels', any: ['room_setup.view'] },
  { prefix: '/room-setup', any: ['room_setup.view'] },
  { prefix: '/room-package-rules', any: ['room_setup.view'] },
  { prefix: '/channel-payouts', any: ['bookings.view', 'cashflow.view', 'reports.view'] },
  { prefix: '/restaurant-ops', any: ['restaurant.view'] },
  { prefix: '/menu-items', any: ['menu.view'] },
  { prefix: '/menu-categories', any: ['menu.view'] },
  { prefix: '/recipes', any: ['recipes.manage', 'menu.view'] },
  { prefix: '/staff-meals', any: ['staff_meals.view'] },
  { prefix: '/setup-imports', any: ['inventory.view', 'menu.view', 'recipes.manage'] },
  { prefix: '/inventory-items', any: ['inventory.view'] },
  { prefix: '/stock-movements', any: ['inventory.view'] },
  { prefix: '/inventory-reconciliation', any: ['inventory_reconciliation.manage'] },
  { prefix: '/suppliers', any: ['suppliers.view'] },
  { prefix: '/purchase-requests', any: ['purchase_requests.view'] },
  { prefix: '/purchase-orders', any: ['purchase_orders.view'] },
  { prefix: '/receiving', any: ['receiving.view'] },
  { prefix: '/employees', any: ['employees.view'] },
  { prefix: '/attendance', any: ['attendance.view'] },
  { prefix: '/payroll-periods', any: ['payroll_periods.view'] },
  { prefix: '/payroll', any: ['payroll_periods.view'] },
  { prefix: '/approvals', any: ['approvals.view'] },
  { prefix: '/treasury', any: ['cashflow.view'] },
  { prefix: '/cashflow', any: ['cashflow.view'] },
  { prefix: '/journals', any: ['journals.view'] },
  { prefix: '/reports', any: ['reports.view'] },
  { prefix: '/assets', any: ['assets.view'] },
  { prefix: '/bir', any: ['bir.view'] },
  { prefix: '/attachments', any: ['reports.view', 'cashflow.view', 'inventory.view', 'bookings.view', 'assets.view', 'bir.view'] },
  { prefix: '/master-data', any: ['master_data.manage'] },
  { prefix: '/taxonomy-admin', any: ['taxonomy.manage'] },
  { prefix: '/users', any: ['users.manage'] },
  { prefix: '/roles-permissions', any: ['roles.manage'] },
  { prefix: '/chart-of-accounts', any: ['chart_of_accounts.manage'] },
  { prefix: '/account-mapping', any: ['account_mapping.manage'] },
  { prefix: '/system-settings', any: ['system_settings.manage'] },
  { prefix: '/integrations/beds24', any: ['integrations.view'] },
  { prefix: '/records', any: ['bookings.view', 'restaurant.view', 'inventory.view', 'payroll_periods.view', 'cashflow.view'] },
];

function pathHasAccess(pathname, can) {
  if (!pathname || pathname === '/login' || pathname.startsWith('/workspace/')) return true;
  const match = PERMISSION_RULES.find((rule) => pathname === rule.prefix || pathname.startsWith(`${rule.prefix}/`));
  if (!match) return true;
  return (match.any || []).some((key) => can(key));
}

function defaultRouteForUser(can) {
  const preferred = [
    ['/dashboard', ['dashboard.view']],
    ['/start-of-day', ['dashboard.view', 'cashflow.view']],
    ['/bookings', ['bookings.view']],
    ['/restaurant-ops', ['restaurant.view']],
    ['/inventory-items', ['inventory.view']],
    ['/payroll-periods', ['payroll_periods.view']],
    ['/cashflow', ['cashflow.view']],
    ['/reports', ['reports.view']],
    ['/system-settings', ['system_settings.manage']],
  ];
  const match = preferred.find(([, permissions]) => permissions.some((key) => can(key)));
  return match?.[0] || '/login';
}

export default function RouteGuard({ children }) {
  const pathname = usePathname();
  const { loaded, can, user } = useAppShell();

  useEffect(() => {
    if (!loaded || !user || pathname === '/login' || pathHasAccess(pathname, can)) return;
    const target = defaultRouteForUser(can);
    if (target && target !== pathname) window.location.replace(target);
  }, [loaded, user, pathname, can]);

  if (!loaded && pathname !== '/login') {
    return (
      <section className="section" aria-live="polite">
        <h1>Checking access</h1>
        <p className="muted">Loading your permitted work areas…</p>
      </section>
    );
  }

  if (pathname !== '/login' && !user) {
    return (
      <section className="section" aria-live="polite">
        <h1>Opening sign in</h1>
        <p className="muted">Your session is not active.</p>
      </section>
    );
  }

  if (pathHasAccess(pathname, can)) return children;

  return (
    <section className="section" role="status">
      <h1>Access restricted</h1>
      <p className="muted">Your account cannot open this page. Redirecting to the first work area available to you…</p>
    </section>
  );
}
