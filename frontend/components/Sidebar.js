'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useMemo, useRef, useState } from 'react';
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

const SIDEBAR_KEY = 'accounting_sidebar_collapsed_v5';
const ACTIVE_GROUP_KEY = 'accounting_sidebar_active_group_v3';
const SCROLL_KEY = 'accounting_sidebar_scroll_v1';
const MIN_SEARCH_LENGTH = 2;

function hasAnyPermission(user, keys = []) {
  if (!keys.length) return true;
  return keys.some((key) => canAccess(user, key));
}

function roleName(user) {
  const raw = String(user?.role || user?.roles?.[0]?.code || 'user');
  return raw.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function isItemActive(pathname, href) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function activeGroupForPath(pathname) {
  return navigationGroups.find((group) => group.items.some((item) => isItemActive(pathname, item.href)))?.id || 'overview';
}

function SidebarSkeleton({ collapsed }) {
  return (
    <div className={collapsed ? 'sidebar-nav-skeleton collapsed-skeleton' : 'sidebar-nav-skeleton'} role="status" aria-label="Loading permitted navigation">
      {!collapsed && <div className="sidebar-skeleton-eyebrow" />}
      {[0, 1, 2, 3, 4].map((index) => (
        <div className="sidebar-skeleton-group" key={index}>
          <span className="sidebar-skeleton-icon" />
          {!collapsed && (
            <span className="sidebar-skeleton-copy">
              <span className="sidebar-skeleton-title" />
              <span className="sidebar-skeleton-subtitle" />
            </span>
          )}
        </div>
      ))}
      <span className="sr-only">Loading access…</span>
    </div>
  );
}

export default function Sidebar() {
  const pathname = usePathname();
  const { user, loaded, mobileNavOpen, closeMobileNav } = useAppShell();
  const scrollRef = useRef(null);
  const activeItemRef = useRef(null);
  const searchInputRef = useRef(null);
  const preSearchScrollRef = useRef(0);
  const previousSearchActiveRef = useRef(false);
  const [collapsed, setCollapsed] = useState(false);
  const [openGroupId, setOpenGroupId] = useState(() => activeGroupForPath(pathname));
  const [filter, setFilter] = useState('');

  const normalizedFilter = filter.trim().toLowerCase();
  const searchActive = normalizedFilter.length > 0;
  const searchReady = normalizedFilter.length >= MIN_SEARCH_LENGTH;

  useEffect(() => {
    try {
      setCollapsed(window.localStorage.getItem(SIDEBAR_KEY) === '1');
      const storedGroup = window.localStorage.getItem(ACTIVE_GROUP_KEY);
      const routeGroup = activeGroupForPath(pathname);
      if (storedGroup === routeGroup && navigationGroups.some((group) => group.id === storedGroup)) {
        setOpenGroupId(storedGroup);
      } else {
        setOpenGroupId(routeGroup);
      }
      const storedScroll = Number(window.sessionStorage.getItem(SCROLL_KEY) || 0);
      window.requestAnimationFrame(() => {
        if (scrollRef.current && Number.isFinite(storedScroll)) scrollRef.current.scrollTop = storedScroll;
      });
    } catch {
      // Storage can be unavailable in private browsing.
    }
  }, [pathname]);

  useEffect(() => {
    document.documentElement.style.setProperty('--sidebar-width', collapsed ? '76px' : '304px');
    try {
      window.localStorage.setItem(SIDEBAR_KEY, collapsed ? '1' : '0');
    } catch {
      // Keep in-memory preference when storage is unavailable.
    }
  }, [collapsed]);

  useEffect(() => {
    closeMobileNav();
    setFilter('');
    const activeGroupId = activeGroupForPath(pathname);
    setOpenGroupId(activeGroupId);
    try {
      window.localStorage.setItem(ACTIVE_GROUP_KEY, activeGroupId);
    } catch {
      // Route-aware state still updates.
    }
    window.requestAnimationFrame(() => activeItemRef.current?.scrollIntoView({ block: 'nearest' }));
  }, [pathname, closeMobileNav]);

  useEffect(() => {
    const wasSearching = previousSearchActiveRef.current;
    if (searchActive && !wasSearching) {
      preSearchScrollRef.current = scrollRef.current?.scrollTop || 0;
      window.requestAnimationFrame(() => {
        if (scrollRef.current) scrollRef.current.scrollTop = 0;
      });
    }
    if (!searchActive && wasSearching) {
      window.requestAnimationFrame(() => {
        if (scrollRef.current) scrollRef.current.scrollTop = preSearchScrollRef.current;
      });
    }
    previousSearchActiveRef.current = searchActive;
  }, [searchActive]);

  const visibleGroups = useMemo(() => navigationGroups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => hasAnyPermission(user, item.permissionsAny)),
    }))
    .filter((group) => group.items.length), [user]);

  const searchResults = useMemo(() => {
    if (!searchReady) return [];
    return visibleGroups.flatMap((group) => group.items
      .filter((item) => {
        const pageLabel = item.label.toLowerCase();
        const hrefTerms = item.href.replaceAll('/', ' ').replaceAll('-', ' ').toLowerCase();
        return pageLabel.includes(normalizedFilter) || hrefTerms.includes(normalizedFilter);
      })
      .map((item) => ({ ...item, groupId: group.id, groupLabel: group.label })));
  }, [normalizedFilter, searchReady, visibleGroups]);

  function toggleGroup(groupId) {
    setOpenGroupId((current) => {
      const next = current === groupId ? null : groupId;
      try {
        if (next) window.localStorage.setItem(ACTIVE_GROUP_KEY, next);
        else window.localStorage.removeItem(ACTIVE_GROUP_KEY);
      } catch {
        // Visible accordion state still updates.
      }
      return next;
    });
  }

  function rememberScroll(event) {
    if (searchActive) return;
    try {
      window.sessionStorage.setItem(SCROLL_KEY, String(event.currentTarget.scrollTop));
    } catch {
      // Scroll remains stable for this mounted session.
    }
  }

  function clearFilter() {
    setFilter('');
    window.requestAnimationFrame(() => searchInputRef.current?.focus());
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
        className={`${collapsed ? 'sidebar collapsed' : 'sidebar'} ${mobileNavOpen ? 'mobile-open' : ''} ${searchActive ? 'search-active' : ''}`}
        aria-label="Accounting navigation"
      >
        <div className="brand">
          <Link href="/dashboard" className="brand-home" aria-label="Hidden Oasis Accounting dashboard">
            <div className="brand-badge" aria-hidden="true">HO</div>
            {!collapsed && (
              <div className="brand-copy">
                <h2>Accounting</h2>
                <div className="small muted-on-dark">Hidden Oasis</div>
              </div>
            )}
          </Link>
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

        {!collapsed && (
          <div className="sidebar-filter" role="search">
            <NavIcon name="search" size={15} />
            <input
              ref={searchInputRef}
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
              placeholder="Find a page"
              aria-label="Filter navigation"
              autoComplete="off"
              spellCheck="false"
            />
            {searchActive && <button type="button" onClick={clearFilter} aria-label="Clear navigation filter"><NavIcon name="close" size={14} /></button>}
          </div>
        )}

        <div className="sidebar-scroll" ref={scrollRef} onScroll={rememberScroll}>
          {!loaded ? <SidebarSkeleton collapsed={collapsed} /> : searchActive && !collapsed ? (
            <div className="sidebar-search-results" role="region" aria-live="polite" aria-label="Navigation search results">
              <div className="sidebar-search-summary">
                <span>{searchReady ? 'Search results' : 'Find a page'}</span>
                {searchReady && <strong>{searchResults.length}</strong>}
              </div>
              {!searchReady ? (
                <div className="sidebar-no-results">
                  <strong>Keep typing</strong>
                  <span>Enter at least two letters to search page names.</span>
                </div>
              ) : searchResults.length ? (
                <nav className="sidebar-search-list" aria-label="Matching pages">
                  {searchResults.map((item) => {
                    const active = isItemActive(pathname, item.href);
                    return (
                      <Link
                        key={`${item.groupId}-${item.href}`}
                        href={item.href}
                        className={active ? 'sidebar-search-result active' : 'sidebar-search-result'}
                        aria-current={active ? 'page' : undefined}
                      >
                        <span className="nav-symbol"><NavIcon name={item.icon} size={16} /></span>
                        <span className="sidebar-search-result-copy">
                          <strong>{item.label}</strong>
                          <small>{item.groupLabel}</small>
                        </span>
                      </Link>
                    );
                  })}
                </nav>
              ) : (
                <div className="sidebar-no-results">
                  <strong>No pages found</strong>
                  <span>Try a page name such as bookings, payroll, reports, or suppliers.</span>
                </div>
              )}
            </div>
          ) : (
            <>
              {!collapsed && <div className="sidebar-eyebrow">Workspace</div>}
              <nav aria-label="Primary navigation">
                {visibleGroups.map((group) => {
                  const groupActive = group.items.some((item) => isItemActive(pathname, item.href));
                  const expanded = openGroupId === group.id;
                  const regionId = `sidebar-group-${group.id}`;
                  return (
                    <section key={group.id} className={`nav-group ${groupActive ? 'active-group' : ''}`} aria-label={group.label}>
                      {!collapsed ? (
                        <button
                          type="button"
                          className="nav-group-toggle"
                          aria-expanded={expanded}
                          aria-controls={regionId}
                          onClick={() => toggleGroup(group.id)}
                        >
                          <span className="nav-group-heading">
                            <span className="nav-group-icon"><NavIcon name={group.icon} size={16} /></span>
                            <span><strong>{group.label}</strong><small>{group.description}</small></span>
                          </span>
                          <NavIcon name="down" size={13} className={expanded ? '' : 'rotate-negative-90'} />
                        </button>
                      ) : (
                        <button
                          type="button"
                          className={groupActive ? 'collapsed-group-button active' : 'collapsed-group-button'}
                          aria-label={group.label}
                          title={group.label}
                          aria-expanded={expanded}
                          onClick={() => toggleGroup(group.id)}
                        >
                          <NavIcon name={group.icon} size={17} />
                        </button>
                      )}
                      <div id={regionId} className="nav-group-items" hidden={!expanded}>
                        {group.items.map((item) => {
                          const active = isItemActive(pathname, item.href);
                          return (
                            <Link
                              key={item.href}
                              href={item.href}
                              ref={active ? activeItemRef : undefined}
                              className={active ? 'active' : ''}
                              title={collapsed ? item.label : undefined}
                              aria-label={collapsed ? item.label : undefined}
                              aria-current={active ? 'page' : undefined}
                            >
                              <span className="nav-symbol"><NavIcon name={item.icon} size={16} /></span>
                              {!collapsed && <span className="nav-text">{item.label}</span>}
                            </Link>
                          );
                        })}
                      </div>
                    </section>
                  );
                })}

                {connectedApps.length > 0 && (
                  <section className="nav-group connected-apps" aria-label="Connected Apps">
                    {!collapsed && <div className="nav-group-static-label">Connected Apps</div>}
                    {!collapsed && (
                      <div className="nav-group-items">
                        {connectedApps.map((item) => (
                          <a key={item.label} href={item.href} rel="noreferrer">
                            <span className="nav-symbol"><NavIcon name="app" size={16} /></span>
                            <span className="nav-text">{item.label}</span><span className="external-mark" aria-hidden="true">↗</span>
                          </a>
                        ))}
                      </div>
                    )}
                  </section>
                )}
              </nav>
            </>
          )}
        </div>

        {!searchActive && (
          <div className={loaded ? 'sidebar-user' : 'sidebar-user sidebar-user-loading'}>
            <div className="user-avatar" aria-hidden="true">{loaded ? String(user?.full_name || user?.username || 'U').slice(0, 1).toUpperCase() : ''}</div>
            {!collapsed && (
              <div className="sidebar-user-copy">
                {loaded ? <><strong>{user?.full_name || user?.username || 'User'}</strong><span>{roleName(user)}</span></> : <><span className="sidebar-user-skeleton wide" /><span className="sidebar-user-skeleton" /></>}
              </div>
            )}
          </div>
        )}
      </aside>
    </>
  );
}
