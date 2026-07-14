'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { canAccess } from '../lib/permissions';
import { useAppShell } from './app-shell/AppShellContext';
import { navigationGroups } from './app-shell/navigation';


const connectedApps = [
  { label: 'Staff & Payroll', href: process.env.NEXT_PUBLIC_STAFF_PAYROLL_APP_URL, short: 'SP' },
  { label: 'Operations', href: process.env.NEXT_PUBLIC_OPERATIONS_APP_URL, short: 'OP' },
  { label: 'POS Cloud', href: process.env.NEXT_PUBLIC_POS_APP_URL, short: 'PS' },
  { label: 'Inventory', href: process.env.NEXT_PUBLIC_INVENTORY_APP_URL, short: 'IV' },
].filter((item) => item.href);

const SIDEBAR_KEY = 'accounting_sidebar_collapsed_v3';

function hasAnyPermission(user, keys = []) {
  if (!keys.length) return true;
  return keys.some((key) => canAccess(user, key));
}

function roleName(user) {
  const raw = String(user?.role || user?.roles?.[0]?.code || 'user');
  return raw.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export default function Sidebar() {
  const pathname = usePathname();
  const { user, loaded, mobileNavOpen, closeMobileNav } = useAppShell();
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const stored = window.localStorage.getItem(SIDEBAR_KEY);
    setCollapsed(stored === '1');
  }, []);

  useEffect(() => {
    document.documentElement.style.setProperty('--sidebar-width', collapsed ? '88px' : '272px');
    window.localStorage.setItem(SIDEBAR_KEY, collapsed ? '1' : '0');
  }, [collapsed]);

  useEffect(() => closeMobileNav(), [pathname, closeMobileNav]);

  const visibleGroups = useMemo(() => navigationGroups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => hasAnyPermission(user, item.permissionsAny)),
    }))
    .filter((group) => group.items.length), [user]);

  return (
    <>
      <button
        type="button"
        className={mobileNavOpen ? 'sidebar-scrim visible' : 'sidebar-scrim'}
        aria-label="Close navigation"
        onClick={closeMobileNav}
      />
      <aside className={`${collapsed ? 'sidebar collapsed' : 'sidebar'} ${mobileNavOpen ? 'mobile-open' : ''}`}>
        <div className="brand">
          <div className="brand-badge">HO</div>
          {!collapsed && (
            <div className="brand-copy">
              <h2>Accounting</h2>
              <div className="small muted-on-dark">Hotel operations & finance</div>
            </div>
          )}
          <button
            type="button"
            className="sidebar-toggle desktop-only"
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            onClick={() => setCollapsed((value) => !value)}
          >
            {collapsed ? '›' : '‹'}
          </button>
          <button type="button" className="sidebar-toggle mobile-only" onClick={closeMobileNav} aria-label="Close navigation">×</button>
        </div>

        <nav aria-label="Primary navigation">
          {visibleGroups.map((group) => (
            <div key={group.label} className="nav-group">
              {!collapsed && <div className="nav-group-label">{group.label}</div>}
              {group.items.map((item) => {
                const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
                return (
                  <Link key={item.href} href={item.href} className={active ? 'active' : ''} title={collapsed ? item.label : undefined}>
                    <span className="nav-symbol">{item.short}</span>
                    {!collapsed && <span className="nav-text">{item.label}</span>}
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
                  <span className="nav-symbol">{item.short}</span>
                  {!collapsed && <span className="nav-text">{item.label}</span>}
                </a>
              ))}
            </div>
          )}
          {!loaded && <div className="sidebar-loading">Loading access…</div>}
        </nav>

        <div className="sidebar-user">
          <div className="user-avatar">{String(user?.full_name || user?.username || 'U').slice(0, 1).toUpperCase()}</div>
          {!collapsed && (
            <div className="sidebar-user-copy">
              <strong>{user?.full_name || user?.username || 'User'}</strong>
              <span>{roleName(user)}</span>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
