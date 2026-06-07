'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { clearToken, globalSearch, logout } from '../lib/api';

const titles = {
  '/dashboard': ['Dashboard', 'Unified resort operations snapshot'],
  '/start-of-day': ['Start of Day', 'Opening checks for cash, receivables, deliveries, and sync'],
  '/staff-guide': ['Staff Guide', 'Simple steps for staff processes that exist in the system'],

  '/workspace/rooms': ['Rooms & Guests', 'Bookings, guests, folios, and room setup'],
  '/workspace/events': ['Events', 'Event records, balances, deposits, and payment follow-up'],
  '/events': ['Events', 'Quotes, confirmed AR, deposits, balances, and completion'],
  '/bookings': ['Bookings', 'Guest booking flow with linked rooms/channels/rates'],
  '/guests': ['Guests', 'Guest CRM list with VIP and returning guest context'],
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

  '/workspace/inventory': ['Inventory & Purchasing', 'Stock control, suppliers, PR/PO/Receiving'],
  '/inventory-items': ['Inventory Items', 'Item master and stock controls'],
  '/stock-movements': ['Stock Movements', 'FIFO movements and inventory impacts'],
  '/inventory-reconciliation': ['Inventory Reconciliation', 'Actual count variance and adjustments'],
  '/suppliers': ['Suppliers', 'Supplier master and procurement linkages'],
  '/purchase-requests': ['Purchase Requests', 'PR workflow and approvals'],
  '/purchase-orders': ['Purchase Orders', 'PO workflow and receiving progress'],
  '/receiving': ['Receiving', 'Receiving workflow and stock/payable integration'],

  '/workspace/payroll': ['People & Payroll', 'Employees, attendance, payroll periods, approvals'],
  '/employees': ['Employees', 'Employee registry and profile maintenance'],
  '/attendance': ['Attendance', 'Attendance logs, import, and review'],
  '/payroll-periods': ['Payroll Periods', 'Payroll period input/import/posting'],
  '/payroll': ['Payroll', 'Legacy payroll run view (secondary)'],
  '/approvals': ['Approvals', 'Cross-module approval queue'],

  '/workspace/finance': ['Finance & Accounting', 'Cashflow, journals, reports, assets, and BIR'],
  '/cashflow': ['Cashflow', 'Money in, money out, transfers, checks, payments, and bills'],
  '/journals': ['Journals', 'Journal entries and trial balance'],
  '/reports': ['Reports', 'Management and accounting reports'],
  '/assets': ['Assets', 'Asset lifecycle and accounting linkage'],
  '/bir': ['BIR', 'Selection, books, and period locks'],
  '/attachments': ['Attachments', 'Operational and accounting support files'],

  '/workspace/settings': ['Settings', 'Admin setup and controls'],
  '/master-data': ['Master Data', 'Generic reusable setup values only'],
  '/taxonomy-admin': ['Accounting Taxonomy', 'Accounting classification tree'],
  '/users': ['Users', 'User accounts and assigned roles'],
  '/roles-permissions': ['Roles & Permissions', 'Checklist permissions per role'],
  '/chart-of-accounts': ['Chart of Accounts', 'Account structure setup'],
  '/account-mapping': ['Account Mapping', 'Posting rule mapping by module/category'],
  '/system-settings': ['System Settings', 'System controls and workflow defaults'],
  '/integrations/beds24': ['Beds24 Integration', 'Beds24 API sync and webhook operations'],
};

export default function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const [searchTerm, setSearchTerm] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searchError, setSearchError] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const found = Object.entries(titles).find(([k]) => pathname === k || pathname.startsWith(k + '/'));
  const [title, subtitle] = found
    ? found[1]
    : ['Hospitality ERP', 'Connected operations, cashflow, payroll, and compliance'];
  const showBack = pathname && pathname !== '/dashboard' && pathname !== '/login' && pathname !== '/';
  const showSearch = pathname && pathname !== '/login' && pathname !== '/';

  useEffect(() => {
    let alive = true;
    const term = searchTerm.trim();
    setSearchError('');
    if (!showSearch || term.length < 2) {
      setSearchResults([]);
      return () => {
        alive = false;
      };
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
    if (typeof window !== 'undefined' && window.history.length > 1) {
      router.back();
      return;
    }
    router.push('/dashboard');
  }

  function openResult(row) {
    if (!row?.href) return;
    setSearchOpen(false);
    setSearchTerm('');
    router.push(row.href);
  }

  return (
    <header className="topbar">
      <div className="topbar-left">
        {showBack && (
          <button type="button" className="secondary topbar-back" onClick={goBack}>
            Back
          </button>
        )}
        <div>
          <div className="topbar-title">{title}</div>
          <div className="topbar-subtitle">{subtitle}</div>
        </div>
      </div>
      <div className="topbar-actions">
        {showSearch && (
          <div className="topbar-search">
            <input
              aria-label="Search"
              className="search-input"
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setSearchOpen(true);
              }}
              onFocus={() => setSearchOpen(true)}
              onKeyDown={(e) => {
                if (e.key === 'Escape') setSearchOpen(false);
                if (e.key === 'Enter' && searchResults[0]) openResult(searchResults[0]);
              }}
              placeholder="Search"
            />
            {searchOpen && searchTerm.trim().length >= 2 && (
              <div className="search-results">
                {searchResults.map((row, idx) => (
                  <button
                    type="button"
                    key={`${row.type}-${row.id || idx}-${row.href}`}
                    className="search-result"
                    onMouseDown={(e) => {
                      e.preventDefault();
                      openResult(row);
                    }}
                  >
                    <span className="badge">{row.type}</span>
                    <span>
                      <strong>{row.label}</strong>
                      <small>{row.subtitle}</small>
                    </span>
                  </button>
                ))}
                {!searchResults.length && !searchError && <div className="search-empty">No matches</div>}
                {!!searchError && <div className="search-empty error-text">{searchError}</div>}
              </div>
            )}
          </div>
        )}
        {showBack && <Link href="/dashboard" className="button-link secondary-link">Dashboard</Link>}
        <button
          className="secondary"
          onClick={async () => {
            try {
              await logout();
            } catch {
              // Local logout should still complete if the server session is already gone.
            }
            clearToken();
            if (typeof window !== 'undefined') window.location.href = '/login';
          }}
        >
          Logout
        </button>
      </div>
    </header>
  );
}
