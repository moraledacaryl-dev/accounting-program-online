'use client';

import { useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { useAppShell } from './app-shell/AppShellContext';

import { pathHasAccess } from '../lib/routeAccess';

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
    if (!loaded || pathname === '/login') return;
    if (!user) { window.location.replace('/login'); return; }
    if (pathHasAccess(pathname, can)) return;
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
