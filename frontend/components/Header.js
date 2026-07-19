'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { clearToken, globalSearch, logout } from '../lib/api';
import { useAppShell } from './app-shell/AppShellContext';

const titles = {
  '/dashboard': ['Dashboard', 'Unified resort operations snapshot'],
  '/start-of-day': ['Start of Day', 'Opening checks for cash, receivables, deliveries, and sync'],
  '/staff-guide': ['Staff Guide', 'Simple steps for staff processes that exist in the system'],
  '/workspace/rooms': ['Rooms & Guests', 'Bookings, guests, folios, and room setup'],
  '/workspace/events': ['Events', 'Event records, balances, deposits, and payment follow-up'],
  '/events': ['Events', 'Quotes, confirmed AR, deposits, balances, and completion'],
  '/bookings': ['Bookings', 'Guest booking flow with linked rooms, channels, and rates'],
  '/guests': ['Guests', 'Guest CRM with VIP and returning-guest context'],
  '/room-folios': ['Room Folios', 'Charges, deposits, payments, refunds, and balances'],
  '/room-types': ['Room Types', 'Room type setup and occupancy defaults'],
  '/rooms': ['Rooms', 'Room master setup and availability profile'],
  '/rate-plans': ['Rate Plans', 'Rate plan setup and inclusions'],
  '/booking-channels': ['Booking Channels', 'Channel setup and payout defaults'],
  '/room-package-rules': ['Package Rules', 'Room package inclusion rules'],
  '/channel-payouts': ['Channel Payouts', 'OTA payout tracking and variance control'],
  '/workspace/restaurant': ['Restaurant & F&B', 'Restaurant operations, menu, recipes, and records'],
  '/workspace/breakfast': ['Breakfast', 'Breakfast operations and records'],
  '/workspace/cafe': ['Cafe', 'Cafe operations and records'],
  '/workspace/bar': ['Bar', 'Bar operations and records'],
  '/restaurant-ops': ['Restaurant Ops', 'Sales, SKU flow, and stock deduction'],
  '/menu-items': ['Menu & Recipes', 'Menu items, recipes, SKUs, and components'],
  '/menu-categories': ['Menu Categories', 'Category setup for menu and reporting'],
  '/recipes': ['Recipes', 'Recipe structure and costing management'],
  '/staff-meals': ['Staff Meals', 'Staff meal ingredient usage and costing'],
  '/setup-imports': ['Excel Setup Import', 'Inventory, menu, variation, and recipe workbook import'],
  '/workspace/inventory': ['Inventory & Purchasing', 'Stock control, suppliers, PR, PO, and receiving'],
  '/inventory-items': ['Inventory Items', 'Item master and stock controls'],
  '/stock-movements': ['Stock Movements', 'FIFO movements and inventory impacts'],
  '/inventory-reconciliation': ['Inventory Reconciliation', 'Actual count variance and adjustments'],
  '/suppliers': ['Suppliers', 'Supplier master and procurement linkages'],
  '/purchase-requests': ['Purchase Requests', 'PR workflow and approvals'],
  '/purchase-orders': ['Purchase Orders', 'PO workflow and receiving progress'],
  '/receiving': ['Receiving', 'Receiving workflow and stock/payable integration'],
  '/workspace/payroll': ['People & Payroll', 'Employees, attendance, payroll periods, and approvals'],
  '/employees': ['Employees', 'Employee registry and profile maintenance'],
  '/attendance': ['Attendance', 'Attendance logs, import, and review'],
  '/payroll-periods': ['Payroll Periods', 'Payroll period input, import, and posting'],
  '/payroll': ['Payroll', 'Legacy payroll run view'],
  '/approvals': ['Review Inbox', 'Approvals and connected-app financial review'],
  '/workspace/finance': ['Finance & Accounting', 'Cashflow, journals, reports, assets, and BIR'],
  '/cashflow': ['Cash & Treasury', 'Money accounts, ledger, daily close, and reconciliation'],
  '/journals': ['Journals', 'Journal entries and trial balance'],
  '/reports': ['Reports', 'Management and accounting reports'],
  '/assets': ['Financial Assets', 'Capitalization, depreciation, impairment, and disposal'],
  '/bir': ['BIR & Periods', 'Books, tax controls, and locked periods'],
  '/attachments': ['Attachments', 'Operational and accounting support files'],
  '/workspace/settings': ['Settings', 'Administration, setup, and controls'],
  '/master-data': ['Master Data', 'Reusable setup values'],
  '/taxonomy-admin': ['Accounting Taxonomy', 'Accounting classification tree'],
  '/users': ['Users', 'User accounts and assigned roles'],
  '/roles-permissions': ['Roles & Permissions', 'Permission controls by role'],
  '/chart-of-accounts': ['Chart of Accounts', 'Account structure setup'],
  '/account-mapping': ['Account Mapping', 'Posting rules by module and category'],
  '/system-settings': ['System Settings', 'System controls and workflow defaults'],
  '/integrations/beds24': ['Beds24 Integration', 'Beds24 synchronization and webhook operations'],
};

function roleName(user) {
  const raw = String(user?.role || user?.roles?.[0]?.code || 'user');
  return raw.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export default function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const { openMobileNav, user } = useAppShell();
  const menuRef = useRef(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searchError, setSearchError] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const found = Object.entries(titles).find(([key]) => pathname === key || pathname.startsWith(`${key}/`));
  const [title, subtitle] = found ? found[1] : ['Hospitality ERP', 'Connected operations, finance, and compliance'];
  const showBack = pathname && pathname !== '/dashboard' && pathname !== '/login' && pathname !== '/';
  const showSearch = pathname && pathname !== '/login' && pathname !== '/';
  const displayName = user?.full_name || user?.username || 'User';
  const initials = displayName.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase() || 'U';

  useEffect(() => {
    function closeOnOutside(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) setProfileOpen(false);
    }
    document.addEventListener('mousedown', closeOnOutside);
    return () => document.removeEventListener('mousedown', closeOnOutside);
  }, []);

  useEffect(() => {
    let alive = true;
    const term = searchTerm.trim();
    setSearchError('');
    if (!showSearch || term.length < 2) {
      setSearchResults([]);
      return () => { alive = false; };
    }
    const timer = setTimeout(() => {
      globalSearch(term, 8)
        .then((data) => {
          if (!alive) return;
          setSearchResults(Array.isArray(data?.results) ? data.results : []);
          setSearchOpen(true);
        })
        .catch((err) => {
          if (!alive) return;
          setSearchResults([]);
          setSearchError(err.message || 'Search failed.');
          setSearchOpen(true);
        });
    }, 220);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [searchTerm, showSearch]);

  function goBack() {
    if (typeof window !== 'undefined' && window.history.length > 1) router.back();
    else router.push('/dashboard');
  }

  function openResult(row) {
    if (!row?.href) return;
    setSearchOpen(false);
    setSearchTerm('');
    router.push(row.href);
  }

  async function signOut() {
    try {
      await logout();
    } catch {
      // Local logout still completes if the server session is already unavailable.
    }
    clearToken();
    if (typeof window !== 'undefined') window.location.href = '/login';
  }

  if (pathname === '/login' || pathname === '/') return null;

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button type="button" className="mobile-menu-button mobile-only" onClick={openMobileNav} aria-label="Open navigation">☰</button>
        {showBack && <button type="button" className="secondary topbar-back" onClick={goBack}>← Back</button>}
        <div>
          <div className="topbar-title">{title}</div>
          <div className="topbar-subtitle">{subtitle}</div>
        </div>
      </div>

      <div className="topbar-actions">
        {showSearch && (
          <div className="topbar-search">
            <input
              aria-label="Search guests, bookings, folios, and records"
              className="search-input"
              value={searchTerm}
              onChange={(event) => {
                setSearchTerm(event.target.value);
                setSearchOpen(true);
              }}
              onFocus={() => setSearchOpen(true)}
              onKeyDown={(event) => {
                if (event.key === 'Escape') setSearchOpen(false);
                if (event.key === 'Enter' && searchResults[0]) openResult(searchResults[0]);
              }}
              placeholder="Search guests, bookings, folios…"
            />
            {searchOpen && searchTerm.trim().length >= 2 && (
              <div className="search-results">
                {searchResults.map((row, index) => (
                  <button
                    type="button"
                    key={`${row.type}-${row.id || index}-${row.href}`}
                    className="search-result"
                    onMouseDown={(event) => {
                      event.preventDefault();
                      openResult(row);
                    }}
                  >
                    <span className="badge">{row.type}</span>
                    <span><strong>{row.label}</strong><small>{row.subtitle}</small></span>
                  </button>
                ))}
                {!searchResults.length && !searchError && <div className="search-empty">No matches</div>}
                {!!searchError && <div className="search-empty error-text">{searchError}</div>}
              </div>
            )}
          </div>
        )}

        <Link href="/approvals" className="header-icon-button" aria-label="Open Review Inbox" title="Review Inbox">
          ✓<span className="header-alert-dot" />
        </Link>

        <div className="profile-menu-wrap" ref={menuRef}>
          <button
            type="button"
            className="profile-trigger"
            aria-haspopup="menu"
            aria-expanded={profileOpen}
            onClick={() => setProfileOpen((value) => !value)}
          >
            <span className="profile-avatar">{initials}</span>
            <span className="profile-copy"><strong>{displayName}</strong><span>{roleName(user)}</span></span>
            <span aria-hidden="true">⌄</span>
          </button>
          {profileOpen && (
            <div className="profile-menu" role="menu">
              <Link href="/dashboard" role="menuitem" onClick={() => setProfileOpen(false)}>Dashboard</Link>
              <Link href="/system-settings" role="menuitem" onClick={() => setProfileOpen(false)}>System settings</Link>
              <button type="button" className="danger-action" role="menuitem" onClick={signOut}>Log out</button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
