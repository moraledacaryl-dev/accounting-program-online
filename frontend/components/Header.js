'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { clearToken, globalSearch, logout } from '../lib/api';
import { useAppShell } from './app-shell/AppShellContext';
import NavIcon from './app-shell/NavIcon';

const titles = {
  '/dashboard': ['Dashboard', 'Unified resort operations snapshot'],
  '/start-of-day': ['Start of Day', 'Opening checks for cash, receivables, deliveries, and sync'],
  '/review-inbox': ['Review Inbox', 'Validate connected-app financial events before posting'],
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
  '/approvals': ['Approvals', 'Authorization queue for operational and financial actions'],
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

function SearchResults({ results, error, onOpen }) {
  return (
    <div className="search-results" role="listbox" aria-label="Search results">
      {results.map((row, index) => (
        <button
          type="button"
          key={`${row.type}-${row.id || index}-${row.href}`}
          className="search-result"
          role="option"
          aria-selected="false"
          onMouseDown={(event) => {
            event.preventDefault();
            onOpen(row);
          }}
        >
          <span className="badge">{row.type}</span>
          <span><strong>{row.label}</strong><small>{row.subtitle}</small></span>
        </button>
      ))}
      {!results.length && !error && <div className="search-empty">No matches</div>}
      {!!error && <div className="search-empty error-text" role="alert">{error}</div>}
    </div>
  );
}

export default function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const { openMobileNav, user } = useAppShell();
  const profileRef = useRef(null);
  const desktopSearchRef = useRef(null);
  const mobileSearchRef = useRef(null);
  const mobileInputRef = useRef(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searchError, setSearchError] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const found = Object.entries(titles).find(([key]) => pathname === key || pathname.startsWith(`${key}/`));
  const [title, subtitle] = found ? found[1] : ['Hospitality ERP', 'Connected operations, finance, and compliance'];
  const showBack = pathname && pathname !== '/dashboard' && pathname !== '/login' && pathname !== '/';
  const showSearch = pathname && pathname !== '/login' && pathname !== '/';
  const displayName = user?.full_name || user?.username || 'User';
  const initials = displayName.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase() || 'U';

  useEffect(() => {
    function closeOnOutside(event) {
      if (profileRef.current && !profileRef.current.contains(event.target)) setProfileOpen(false);
      const outsideDesktopSearch = !desktopSearchRef.current || !desktopSearchRef.current.contains(event.target);
      const outsideMobileSearch = !mobileSearchRef.current || !mobileSearchRef.current.contains(event.target);
      if (outsideDesktopSearch && outsideMobileSearch) setSearchOpen(false);
    }
    function closeOnEscape(event) {
      if (event.key !== 'Escape') return;
      setProfileOpen(false);
      setSearchOpen(false);
      setMobileSearchOpen(false);
    }
    document.addEventListener('mousedown', closeOnOutside);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('mousedown', closeOnOutside);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, []);

  useEffect(() => {
    setProfileOpen(false);
    setSearchOpen(false);
    setMobileSearchOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!mobileSearchOpen) return;
    const timer = window.setTimeout(() => mobileInputRef.current?.focus(), 0);
    return () => window.clearTimeout(timer);
  }, [mobileSearchOpen]);

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
        .catch((error) => {
          if (!alive) return;
          setSearchResults([]);
          setSearchError(error.message || 'Search failed.');
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
    setMobileSearchOpen(false);
    setSearchTerm('');
    router.push(row.href);
  }

  function updateSearch(value) {
    setSearchTerm(value);
    setSearchOpen(true);
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

  const shouldShowResults = searchOpen && searchTerm.trim().length >= 2;

  return (
    <header className="topbar" aria-label="Page toolbar">
      <div className="topbar-left">
        <button type="button" className="mobile-menu-button mobile-only" onClick={openMobileNav} aria-label="Open navigation">
          <NavIcon name="menu" size={19} />
        </button>
        {showBack && (
          <button type="button" className="secondary topbar-back" onClick={goBack} aria-label="Go back">
            <NavIcon name="back" size={17} /><span>Back</span>
          </button>
        )}
        <div className="topbar-copy">
          <div className="topbar-title" title={title}>{title}</div>
          <div className="topbar-subtitle">{subtitle}</div>
        </div>
      </div>

      <div className="topbar-actions">
        {showSearch && (
          <div className="topbar-search desktop-search" ref={desktopSearchRef}>
            <NavIcon name="search" size={16} className="search-leading-icon" />
            <input
              aria-label="Search guests, bookings, folios, and records"
              className="search-input"
              value={searchTerm}
              onChange={(event) => updateSearch(event.target.value)}
              onFocus={() => setSearchOpen(true)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && searchResults[0]) openResult(searchResults[0]);
              }}
              placeholder="Search guests, bookings, folios…"
            />
            {shouldShowResults && <SearchResults results={searchResults} error={searchError} onOpen={openResult} />}
          </div>
        )}

        {showSearch && (
          <button
            type="button"
            className="header-icon-button mobile-search-trigger mobile-only"
            aria-label="Open search"
            aria-expanded={mobileSearchOpen}
            onClick={() => setMobileSearchOpen((value) => !value)}
          >
            <NavIcon name="search" size={18} />
          </button>
        )}

        <Link href="/review-inbox" className="header-icon-button" aria-label="Open Review Inbox" title="Review Inbox">
          <NavIcon name="review" size={18} />
        </Link>

        <div className="profile-menu-wrap" ref={profileRef}>
          <button
            type="button"
            className="profile-trigger"
            aria-haspopup="menu"
            aria-expanded={profileOpen}
            onClick={() => setProfileOpen((value) => !value)}
          >
            <span className="profile-avatar">{initials}</span>
            <span className="profile-copy"><strong>{displayName}</strong><span>{roleName(user)}</span></span>
            <NavIcon name="down" size={14} />
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

      {mobileSearchOpen && showSearch && (
        <div className="mobile-search-panel" ref={mobileSearchRef} role="search">
          <div className="mobile-search-field">
            <NavIcon name="search" size={17} className="search-leading-icon" />
            <input
              ref={mobileInputRef}
              aria-label="Search guests, bookings, folios, and records"
              className="search-input"
              value={searchTerm}
              onChange={(event) => updateSearch(event.target.value)}
              onFocus={() => setSearchOpen(true)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && searchResults[0]) openResult(searchResults[0]);
              }}
              placeholder="Search records…"
            />
            <button type="button" className="mobile-search-close" onClick={() => setMobileSearchOpen(false)} aria-label="Close search">
              <NavIcon name="close" size={17} />
            </button>
          </div>
          {shouldShowResults && <SearchResults results={searchResults} error={searchError} onOpen={openResult} />}
          <span className="sr-only" aria-live="polite">{searchResults.length} search results</span>
        </div>
      )}
    </header>
  );
}
