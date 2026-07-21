'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { canAccess } from '../lib/permissions';
import { useAppShell } from './app-shell/AppShellContext';
import NavIcon from './app-shell/NavIcon';
import { navigationGroups } from './app-shell/navigation';

const connectedApps = [
  { label: 'Staff & Payroll', href: process.env.NEXT_PUBLIC_STAFF_PAYROLL_APP_URL },
  { label: 'Operations', href: process.env.NEXT_PUBLIC_OPERATIONS_APP_URL },
  { label: 'POS Cloud', href: process.env.NEXT_PUBLIC_POS_APP_URL },
  { label: 'Inventory', href: process.env.NEXT_PUBLIC_INVENTORY_APP_URL },
].filter((item) => item.href);

const SIDEBAR_KEY = 'accounting_sidebar_collapsed_v4';
const GROUPS_KEY = 'accounting_sidebar_groups_v1';

function hasAnyPermission(user, keys = []) {
  if (!keys.length) return true;
  return keys.some((key) => canAccess(user, key));
}

function roleName(user) {
  const raw = String(user?.role || user?.roles?.[0]?.code || 'user');
  return raw.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function defaultGroupState() {
  return Object.fromEntries(navigationGroups.map((group) => [group.id, true]));
}

export default function Sidebar() {
  const pathname = usePathname();
  const { user, loaded, mobileNavOpen, closeMobileNav } = useAppShell();
  const [collapsed, setCollapsed] = useState(false);
  const [openGroups, setOpenGroups] = useState(defaultGroupState);

  useEffect(() => {
    try {
      setCollapsed(window.localStorage.getItem(SIDEBAR_KEY) === '1');
      const storedGroups = JSON.parse(window.localStorage.getItem(GROUPS_KEY) || '{}');
      setOpenGroups((current) => ({ ...current, ...storedGroups }));
    } catch {
      // Storage can be unavailable in private browsing; the defaults remain usable.
    }
  }, []);

  useEffect(() => {
    document.documentElement.style.setProperty('--sidebar-width', collapsed ? '88px' : '282px');
    try {
      window.localStorage.setItem(SIDEBAR_KEY, collapsed ? '1' : '0');
    } catch {
      // Keep the in-memory preference when storage is unavailable.
    }
  }, [collapsed]);

  useEffect(() => {
    closeMobileNav();
    const activeGroup = navigationGroups.find((group) => group.items.some((item) => pathname === item.href || pathname.startsWith(`${item.href}/`)));
    if (activeGroup) setOpenGroups((current) => ({ ...current, [activeGroup.id]: true }));
  }, [pathname, closeMobileNav]);

  const visibleGroups = useMemo(() => navigationGroups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => hasAnyPermission(user, item.permissionsAny)),
    }))
    .filter((group) => group.items.length), [user]);

  function toggleGroup(groupId) {
    setOpenGroups((current) => {
      const next = { ...current, [groupId]: !current[groupId] };
      try {
        window.localStorage.setItem(GROUPS_KEY, JSON.stringify(next));
      } catch {
        // The visible state still updates when storage is unavailable.
      }
      return next;
    });
  }

  if (pathname === '/login') return null;

  return (
    <>
      <button
        type="button"
        className={mobileNavOpen ? 'sidebar-scrim visible' : 'sidebar-scrim'}
        aria-label="Close navigation"
        aria-hidden={!mobileNavOpen}
        tabIndex={mobileNavOpen ? 0 : -1}
        onClick={closeMobileNav}
      />
      <aside
        className={`${collapsed ? 'sidebar collapsed' : 'sidebar'} ${mobileNavOpen ? 'mobile-open' : ''}`}
        aria-label="Application navigation"
      >
        <div className="brand">
          <div className="brand-badge" aria-hidden="true">HO</div>
          {!collapsed && (
            <div className="brand-copy">
              <h2>Accounting & Hotel</h2>
              <div className="small muted-on-dark">Hidden Oasis finance system</div>
            </div>
          )}
          <button
            type="button"
            className="sidebar-toggle desktop-only"
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-pressed={collapsed}
            onClick={() => setCollapsed((value) => !value)}
          >
            <NavIcon name="chevron" size={17} className={collapsed ? '' : 'rotate-180'} />
          </button>
          <button type="button" className="sidebar-toggle mobile-only" onClick={closeMobileNav} aria-label="Close navigation">
            <NavIcon name="close" size={18} />
          </button>
        </div>

        <div className="sidebar-scroll">
          <nav aria-label="Primary navigation">
            {visibleGroups.map((group) => {
              const expanded = collapsed || openGroups[group.id] !== false;
              const regionId = `sidebar-group-${group.id}`;
              return (
                <section key={group.id} className="nav-group" aria-label={group.label}>
                  {!collapsed && (
                    <button
                      type="button"
                      className="nav-group-toggle"
                      aria-expanded={expanded}
                      aria-controls={regionId}
                      onClick={() => toggleGroup(group.id)}
                    >
                      <span>{group.label}</span>
                      <NavIcon name="down" size={14} className={expanded ? '' : 'rotate-negative-90'} />
                    </button>
                  )}
                  <div id={regionId} className="nav-group-items" hidden={!expanded}>
                    {group.items.map((item) => {
                      const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
                      return (
                        <Link
                          key={item.href}
                          href={item.href}
                          className={active ? 'active' : ''}
                          title={collapsed ? item.label : undefined}
                          aria-label={collapsed ? item.label : undefined}
                          aria-current={active ? 'page' : undefined}
                        >
                          <span className="nav-symbol"><NavIcon name={item.icon} size={17} /></span>
                          {!collapsed && <span className="nav-text">{item.label}</span>}
                        </Link>
                      );
                    })}
                  </div>
                </section>
              );
            })}

            {connectedApps.length > 0 && (
              <section className="nav-group" aria-label="Connected Apps">
                {!collapsed && <div className="nav-group-static-label">Connected Apps</div>}
                <div className="nav-group-items">
                  {connectedApps.map((item) => (
                    <a key={item.label} href={item.href} rel="noreferrer" title={collapsed ? item.label : undefined} aria-label={collapsed ? item.label : undefined}>
                      <span className="nav-symbol"><NavIcon name="app" size={17} /></span>
                      {!collapsed && <span className="nav-text">{item.label}</span>}
                    </a>
                  ))}
                </div>
              </section>
            )}
          </nav>

          {!collapsed && (
            <div className="sidebar-status" role="status">
              <strong><span className="sidebar-status-dot" />System status</strong>
              Core services operational. Connected-app events remain subject to Accounting review.
            </div>
          )}
          {!loaded && <div className="sidebar-loading" role="status">Loading access…</div>}
        </div>

        <div className="sidebar-user">
          <div className="user-avatar" aria-hidden="true">{String(user?.full_name || user?.username || 'U').slice(0, 1).toUpperCase()}</div>
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
