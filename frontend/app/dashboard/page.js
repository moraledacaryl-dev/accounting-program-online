'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { canAccess } from '../../lib/permissions';
import { getDashboard } from '../../lib/api';
import { useAppShell } from '../../components/app-shell/AppShellContext';
import './dashboard.css';

function currency(value, decimals = 0) {
  return `₱${Number(value || 0).toLocaleString('en-PH', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`;
}

function plain(value) {
  if (value === null || typeof value === 'undefined') return '—';
  if (typeof value === 'number') return Number(value).toLocaleString('en-PH');
  return String(value);
}

function firstName(user) {
  const raw = String(user?.full_name || user?.username || 'User').trim();
  return raw.split(/\s+/)[0] || 'User';
}

function timeGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

function movementRows(commandCenter, activeTab) {
  if (activeTab === 'departures') return commandCenter.departures || [];
  if (activeTab === 'in_house') return commandCenter.in_house || [];
  return commandCenter.arrivals || [];
}

function DashboardTable({ card }) {
  return (
    <section className="dashboard-panel dashboard-secondary-panel">
      <div className="dashboard-panel-head">
        <div>
          <h2>{card.label}</h2>
          {!!card.description && <p>{card.description}</p>}
        </div>
      </div>
      <div className="dashboard-widget-table">
        <table className="table dense-table">
          <thead><tr>{(card.columns || []).map((column) => <th key={`${card.key}-${column}`}>{String(column).replaceAll('_', ' ')}</th>)}</tr></thead>
          <tbody>
            {(card.rows || []).map((row, index) => (
              <tr key={`${card.key}-${index}`}>
                {(card.columns || []).map((column) => <td key={`${card.key}-${index}-${column}`}>{plain(row?.[column])}</td>)}
              </tr>
            ))}
            {!(card.rows || []).length && <tr><td colSpan={(card.columns || []).length || 1} className="muted">No records in this view.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function DashboardPage() {
  const { user } = useAppShell();
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState('');
  const financeView = canAccess(user, 'reports.view') || canAccess(user, 'journals.view');
  const [activeTab, setActiveTab] = useState('arrivals');

  useEffect(() => {
    getDashboard().then(setSummary).catch((requestError) => setError(requestError.message || 'Failed to load dashboard.'));
  }, []);

  const tableCards = useMemo(() => {
    const cards = Array.isArray(summary?.dashboard_widget_cards) ? summary.dashboard_widget_cards : [];
    return cards.filter((card) => card.type === 'table').slice(0, 4);
  }, [summary]);

  const commandCenter = summary?.command_center || {};
  const rows = movementRows(commandCenter, activeTab);
  const beds24 = commandCenter.beds24_sync || {};
  const pendingReview = Number(summary?.pending_by_workflow?.integration_review ?? summary?.pending_review ?? 0);
  const openFolioAlerts = commandCenter.open_folio_alerts || [];

  const primaryMetrics = financeView ? [
    { label: 'Cash and bank', value: currency(Number(summary?.cash_on_hand || 0) + Number(summary?.bank_balance || 0), 2), note: 'Current cash and bank balances', href: '/cashflow' },
    { label: 'Receivables due', value: currency(summary?.receivables_due, 2), note: `${plain(summary?.receivables_overdue || 0)} overdue receivables`, href: '/cashflow/receivables' },
    { label: 'Bills to pay', value: currency(summary?.payables_due, 2), note: `${plain(summary?.payables_overdue || 0)} overdue bills`, href: '/cashflow/payables' },
    { label: 'Reconciliation needed', value: plain(summary?.unreconciled_accounts || 0), note: 'Accounts requiring reconciliation', href: '/cashflow/reconciliation' },
  ] : [
    {
      label: 'Arrivals today',
      value: plain((commandCenter.arrivals || []).length),
      note: 'Confirmed arrivals requiring front-desk attention',
      href: '/bookings?view=arrivals',
    },
    {
      label: 'Departures today',
      value: plain((commandCenter.departures || []).length),
      note: 'Stays due for settlement and checkout',
      href: '/bookings?view=departures',
    },
    {
      label: 'Occupancy tonight',
      value: `${Number(summary?.occupancy_rate || 0).toLocaleString('en-PH', { maximumFractionDigits: 1 })}%`,
      note: `${plain(summary?.in_house_guests || summary?.bookings_checked_in || 0)} in-house guests`,
      href: '/bookings?view=in-house',
    },
    {
      label: 'Balances needing follow-up',
      value: currency(openFolioAlerts.reduce((total, folio) => total + Number(folio.balance || 0), 0), 2),
      note: `${plain(openFolioAlerts.length)} guest folios surfaced as exceptions`,
      href: '/room-folios',
    },
  ];

  const actionItems = [
    ...(financeView ? [{ href: '/approvals', title: 'Review pending approvals', note: `${plain(summary?.pending_approvals || 0)} items awaiting approval`, tone: summary?.pending_approvals ? 'warn' : 'ok', label: summary?.pending_approvals ? 'Review' : 'Clear' }] : []),
    {
      href: '/review-inbox',
      title: 'Validate connected-app events',
      note: `${plain(pendingReview)} event${pendingReview === 1 ? '' : 's'} waiting for Accounting review`,
      tone: pendingReview > 0 ? 'warn' : 'ok',
      label: pendingReview > 0 ? 'Review' : 'Clear',
    },
    {
      href: '/room-folios',
      title: 'Resolve guest balances',
      note: `${plain(openFolioAlerts.length)} open folio exception${openFolioAlerts.length === 1 ? '' : 's'}`,
      tone: openFolioAlerts.length ? 'warn' : 'ok',
      label: openFolioAlerts.length ? 'Due' : 'Clear',
    },
    {
      href: '/channel-payouts',
      title: 'Reconcile channel settlements',
      note: 'Compare expected payout, commission, received amount, and variance',
      tone: 'info',
      label: 'Open',
    },
    {
      href: '/cashflow/daily-cash',
      title: 'Complete cash close',
      note: 'Count drawers, explain variances, and submit the daily close',
      tone: 'info',
      label: 'Open',
    },
  ];

  const integrations = [
    {
      name: 'Inventory & Procurement',
      status: 'Not verified',
      tone: 'info',
      text: `${plain(summary?.low_stock_count || 0)} low-stock alert${Number(summary?.low_stock_count || 0) === 1 ? '' : 's'}. Inventory remains the source of truth for stock.`,
      href: '/inventory-items',
    },
    {
      name: 'Staff & Payroll',
      status: 'Not verified',
      tone: 'info',
      text: `${plain(summary?.people_payroll?.payroll_periods_pending || 0)} payroll period${Number(summary?.people_payroll?.payroll_periods_pending || 0) === 1 ? '' : 's'} pending.`,
      href: '/payroll-periods',
    },
    {
      name: 'POS Cloud',
      status: 'Not verified',
      tone: 'info',
      text: `${plain((commandCenter.room_charge_review || []).length)} recent room-charge line${(commandCenter.room_charge_review || []).length === 1 ? '' : 's'} available for review.`,
      href: '/restaurant-ops',
    },
    {
      name: 'Beds24',
      status: beds24.status ? `Last event: ${beds24.status}` : 'No sync recorded',
      tone: String(beds24.status || '').toLowerCase().includes('fail') ? 'danger' : 'info',
      text: beds24.processed_at ? `Last processed: ${beds24.processed_at}. Check integration logs for current status.` : 'No successful sync time is available. Check integration logs.',
      href: '/integrations/beds24',
    },
  ];

  return (
    <div className="dashboard-page dashboard-page--operational">
      <section className="dashboard-hero dashboard-hero--compact">
        <div>
          <div className="dashboard-eyebrow">Today at Hidden Oasis</div>
          <h1>{timeGreeting()}, {firstName(user)}</h1>
          <p>{financeView ? 'Review cash, outstanding balances, approvals, and period-close work.' : 'Review guest movements, folio balances, and daily cash close.'}</p>
          {!!error && <div className="notice danger" style={{ marginTop: 12 }}>{error}</div>}
        </div>
        <div className="dashboard-actions">
          {financeView ? <Link href="/reports" className="button-link primary-link">Review financial reports</Link> : <Link href="/bookings?create=1" className="button-link primary-link">New booking</Link>}
          {financeView ? <Link href="/cashflow/daily-cash" className="button-link secondary-link">Daily cash close</Link> : <Link href="/bookings/calendar" className="button-link secondary-link">Open calendar</Link>}
          <Link href="/start-of-day" className="button-link secondary-link">Start-of-day checks</Link>
        </div>
      </section>

      {!summary && !error && <div className="dashboard-panel dashboard-loading">Loading today’s accounting overview…</div>}

      {!!summary && (
        <>
          <section className="dashboard-metrics" aria-label="Today’s key indicators">
            {primaryMetrics.map((metric) => (
              <Link href={metric.href} className="dashboard-metric dashboard-metric--link" key={metric.label}>
                <div className="dashboard-metric-label">{metric.label}</div>
                <div className="dashboard-metric-value">{metric.value}</div>
                <div className="dashboard-metric-note">{metric.note}</div>
              </Link>
            ))}
          </section>

          <section className={financeView ? "dashboard-main-grid dashboard-main-grid--finance" : "dashboard-main-grid"}>
            <article className="dashboard-panel">
              <div className="dashboard-panel-head">
                <div>
                  <h2>Today’s guest movement</h2>
                  <p>Hospitality context for collections and settlement.</p>
                </div>
                <Link href="/bookings/calendar" className="button-link secondary-link">Calendar</Link>
              </div>
              <div className="movement-tabs" role="group" aria-label="Guest movement">
                {[
                  ['arrivals', 'Arrivals', commandCenter.arrivals || []],
                  ['departures', 'Departures', commandCenter.departures || []],
                  ['in_house', 'In-house', commandCenter.in_house || []],
                ].map(([key, label, items]) => (
                  <button key={key} type="button" aria-pressed={activeTab === key} className={activeTab === key ? 'movement-tab active' : 'movement-tab'} onClick={() => setActiveTab(key)}>
                    {label} <span className="badge">{items.length}</span>
                  </button>
                ))}
              </div>
              <div className="movement-list">
                {rows.slice(0, 8).map((row) => (
                  <Link href={`/bookings/${row.id}`} className="movement-row" key={`${activeTab}-${row.id}`}>
                    <span><strong>{row.guest_name || 'Guest not set'}</strong><small>{row.booking_ref || row.reference_no || `Booking #${row.id}`}</small></span>
                    <span><strong>{row.room_name || 'Room pending'}</strong><small>{row.check_in || '—'} to {row.check_out || '—'}</small></span>
                    <span><strong>{row.channel || 'Direct'}</strong><small>{String(row.status || activeTab).replaceAll('_', ' ')}</small></span>
                    <span className="movement-amount">{currency(row.folio_balance || 0)}<small>balance</small></span>
                  </Link>
                ))}
                {!rows.length && <div className="empty-state"><strong>No {activeTab.replaceAll('_', '-')} records today</strong><span>There are no records requiring action in this view.</span></div>}
              </div>
            </article>

            <aside className="dashboard-panel dashboard-action-center">
              <div className="dashboard-panel-head"><div><h2>Action center</h2><p>Only items that can block service, settlement, or posting.</p></div></div>
              <div className="action-list">
                {actionItems.map((action) => (
                  <Link href={action.href} className="action-item" key={action.href}>
                    <span><strong>{action.title}</strong><small>{action.note}</small></span>
                    <span className={`badge ${action.tone}`}>{action.label}</span>
                  </Link>
                ))}
              </div>
            </aside>
          </section>

          <section className="dashboard-panel dashboard-integrations-panel">
            <div className="dashboard-panel-head">
              <div><h2>Connected applications</h2><p>Retained records do not prove a live connection. Open an integration to verify its latest activity.</p></div>
              <Link href="/review-inbox" className="button-link secondary-link">Open Review Inbox</Link>
            </div>
            <div className="dashboard-integrations">
              {integrations.map((item) => (
                <article className="integration-card" key={item.name}>
                  <div className="integration-card-head"><strong>{item.name}</strong><span className={`badge ${item.tone}`}>{item.status}</span></div>
                  <p>{item.text}</p>
                  <Link href={item.href} className="button-link secondary-link">Open</Link>
                </article>
              ))}
            </div>
          </section>

          {!!tableCards.length && (
            <details className="dashboard-secondary-details">
              <summary>Additional management widgets</summary>
              <div className="dashboard-secondary-grid">
                {tableCards.map((card) => <DashboardTable key={card.key} card={card} />)}
              </div>
            </details>
          )}
        </>
      )}
    </div>
  );
}
