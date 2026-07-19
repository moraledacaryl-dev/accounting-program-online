'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { getDashboard } from '../../lib/api';
import { useAppShell } from '../../components/app-shell/AppShellContext';
import './dashboard.css';

const WORKSPACES = [
  ['/bookings', 'Hotel Operations', 'Bookings, guests, folios, rooms, rates, and Beds24 context'],
  ['/events', 'Events', 'Commercial event bookings, deposits, balances, and Operations handoff'],
  ['/cashflow', 'Cash & Treasury', 'Accounts, authoritative ledger, daily close, and reconciliation'],
  ['/approvals', 'Review Inbox', 'Approvals and connected-app financial items requiring review'],
  ['/reports', 'Reports', 'Hotel, financial, compliance, and management reporting'],
  ['/system-settings', 'Setup', 'Hotel setup, accounting mappings, access, and integrations'],
];

function currency(value, decimals = 0) {
  return `₱${Number(value || 0).toLocaleString('en-PH', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`;
}

function plain(value) {
  if (value === null || typeof value === 'undefined') return '—';
  if (typeof value === 'number') return Number(value).toLocaleString('en-PH');
  return String(value);
}

function firstName(user) {
  const raw = String(user?.full_name || user?.username || 'Caryl').trim();
  return raw.split(/\s+/)[0] || 'Caryl';
}

function timeGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

function metricValue(key, summary) {
  const map = {
    revenue_today: currency(summary?.revenue_today),
    outstanding_receivables: currency(summary?.outstanding_receivables || summary?.open_receivables || summary?.receivables_total),
    occupancy_rate: `${Number(summary?.occupancy_rate || 0).toLocaleString('en-PH', { maximumFractionDigits: 1 })}%`,
    pending_approvals: plain(summary?.pending_approvals || summary?.unposted_integrations || 0),
  };
  return map[key];
}

function movementRows(commandCenter, activeTab) {
  if (activeTab === 'departures') return commandCenter.departures || [];
  if (activeTab === 'in_house') return commandCenter.in_house || [];
  return commandCenter.arrivals || [];
}

function DashboardTable({ card }) {
  return (
    <section className="dashboard-panel">
      <div className="dashboard-panel-head">
        <div>
          <h2>{card.label}</h2>
          {!!card.description && <p>{card.description}</p>}
        </div>
      </div>
      <div className="dashboard-widget-table">
        <table className="table dense-table">
          <thead>
            <tr>{(card.columns || []).map((col) => <th key={`${card.key}-${col}`}>{String(col).replaceAll('_', ' ')}</th>)}</tr>
          </thead>
          <tbody>
            {(card.rows || []).map((row, idx) => (
              <tr key={`${card.key}-${idx}`}>
                {(card.columns || []).map((col) => <td key={`${card.key}-${idx}-${col}`}>{plain(row?.[col])}</td>)}
              </tr>
            ))}
            {!(card.rows || []).length && <tr><td colSpan={(card.columns || []).length || 1} className="muted">No data yet.</td></tr>}
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
  const [activeTab, setActiveTab] = useState('arrivals');

  useEffect(() => {
    getDashboard().then(setSummary).catch((err) => setError(err.message || 'Failed to load dashboard.'));
  }, []);

  const widgetCards = useMemo(() => {
    const incoming = Array.isArray(summary?.dashboard_widget_cards) ? summary.dashboard_widget_cards : [];
    return incoming;
  }, [summary]);

  const tableCards = widgetCards.filter((card) => card.type === 'table');
  const commandCenter = summary?.command_center || {};
  const rows = movementRows(commandCenter, activeTab);
  const beds24 = commandCenter.beds24_sync || {};

  const primaryMetrics = [
    {
      key: 'revenue_today',
      label: 'Today’s recognized revenue',
      note: summary?.cash_in_today ? `${currency(summary.cash_in_today)} cash received today` : 'Based on posted hotel and accounting activity',
    },
    {
      key: 'outstanding_receivables',
      label: 'Outstanding receivables',
      note: summary?.open_folio_balance ? `${currency(summary.open_folio_balance)} in open folios` : 'Guest, event, company, and channel balances',
    },
    {
      key: 'occupancy_rate',
      label: 'Occupancy tonight',
      note: `${plain(summary?.in_house_guests || summary?.bookings_checked_in || 0)} in-house guests`,
    },
    {
      key: 'pending_approvals',
      label: 'Unposted integrations',
      note: `${plain(summary?.pending_approvals || 0)} items requiring review`,
    },
  ];

  const actions = [
    {
      href: '/approvals',
      title: 'Connected-app items ready for review',
      note: `${plain(summary?.pending_approvals || 0)} pending approvals and posting decisions`,
      tone: Number(summary?.pending_approvals || 0) > 0 ? 'warn' : 'ok',
      label: Number(summary?.pending_approvals || 0) > 0 ? 'Review' : 'Clear',
    },
    {
      href: '/room-folios',
      title: 'Open folio balances',
      note: `${plain((commandCenter.open_folio_alerts || []).length)} folios currently surfaced by the command center`,
      tone: (commandCenter.open_folio_alerts || []).length ? 'warn' : 'ok',
      label: (commandCenter.open_folio_alerts || []).length ? 'Due' : 'Clear',
    },
    {
      href: '/channel-payouts',
      title: 'Channel settlement review',
      note: 'Validate expected OTA payouts, fees, and receiving-account matches',
      tone: 'info',
      label: 'Open',
    },
    {
      href: '/journals',
      title: 'Journal and close controls',
      note: 'Review drafts, source-linked journals, and locked-period exceptions',
      tone: 'info',
      label: 'Open',
    },
  ];

  const integrations = [
    {
      name: 'Inventory & Procurement',
      status: summary?.low_stock_count > 0 ? 'Review' : 'Connected',
      tone: summary?.low_stock_count > 0 ? 'warn' : 'ok',
      text: `${plain(summary?.low_stock_count || 0)} low-stock alerts. Purchase and receiving records remain authoritative in Inventory.`,
      href: '/workspace/inventory',
    },
    {
      name: 'Staff & Payroll',
      status: summary?.people_payroll?.payroll_periods_pending ? 'Review' : 'Connected',
      tone: summary?.people_payroll?.payroll_periods_pending ? 'warn' : 'ok',
      text: `${plain(summary?.people_payroll?.payroll_periods_pending || 0)} payroll periods pending. Accounting receives approved financial packages only.`,
      href: '/workspace/payroll',
    },
    {
      name: 'POS Cloud',
      status: 'Connected',
      tone: 'ok',
      text: `${plain((commandCenter.room_charge_review || []).length)} recent room-charge lines available for folio and settlement review.`,
      href: '/workspace/restaurant',
    },
    {
      name: 'Beds24',
      status: beds24.status || 'Connected',
      tone: String(beds24.status || '').toLowerCase().includes('fail') ? 'danger' : 'ok',
      text: beds24.event_type ? `Latest event: ${String(beds24.event_type).replaceAll('_', ' ')}.` : 'Booking, room, and folio context synchronized with Accounting.',
      href: '/integrations/beds24',
    },
  ];

  return (
    <div className="dashboard-page">
      <section className="dashboard-hero">
        <div>
          <div className="dashboard-eyebrow">Unified hospitality finance</div>
          <h1>{timeGreeting()}, {firstName(user)}</h1>
          <p>Financial control, hotel movement, receivables, and connected-app posting in one focused workspace.</p>
          {!!summary?.dashboard_role && <div className="small muted" style={{ marginTop: 8 }}>Current layout: {String(summary.dashboard_role).replaceAll('_', ' ')}</div>}
          {!!error && <div className="notice danger" style={{ marginTop: 12 }}>{error}</div>}
        </div>
        <div className="dashboard-actions">
          <Link href="/integrations/beds24" className="button-link secondary-link">Beds24 sync</Link>
          <Link href="/cashflow" className="button-link primary-link">Receive payment</Link>
          <Link href="/system-settings" className="button-link secondary-link">Customize dashboard</Link>
        </div>
      </section>

      {!summary && !error && <div className="dashboard-panel dashboard-loading">Loading the hospitality command center…</div>}

      {!!summary && (
        <>
          <section className="dashboard-metrics" aria-label="Key performance indicators">
            {primaryMetrics.map((metric) => (
              <article className="dashboard-metric" key={metric.key}>
                <div className="dashboard-metric-label">{metric.label}</div>
                <div className="dashboard-metric-value">{metricValue(metric.key, summary)}</div>
                <div className="dashboard-metric-note">{metric.note}</div>
              </article>
            ))}
          </section>

          <section className="dashboard-main-grid">
            <article className="dashboard-panel">
              <div className="dashboard-panel-head">
                <div>
                  <h2>Today’s hotel movement</h2>
                  <p>Arrivals, departures, in-house stays, rooms, channels, and balances from the live booking workflow.</p>
                </div>
                <Link href="/bookings" className="button-link secondary-link">Open calendar</Link>
              </div>
              <div className="movement-tabs" role="tablist" aria-label="Hotel movement">
                {[
                  ['arrivals', 'Arrivals', commandCenter.arrivals || []],
                  ['departures', 'Departures', commandCenter.departures || []],
                  ['in_house', 'In-house', commandCenter.in_house || []],
                ].map(([key, label, items]) => (
                  <button key={key} type="button" className={activeTab === key ? 'movement-tab active' : 'movement-tab'} onClick={() => setActiveTab(key)}>
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
                {!rows.length && <div className="empty-state"><strong>No {activeTab.replaceAll('_', '-')} records today</strong><span>The live command-center feed has no items in this view.</span></div>}
              </div>
            </article>

            <aside className="dashboard-panel">
              <div className="dashboard-panel-head">
                <div><h2>Action center</h2><p>Accounting, commercial, and posting exceptions only.</p></div>
              </div>
              <div className="action-list">
                {actions.map((action) => (
                  <Link href={action.href} className="action-item" key={action.href}>
                    <span><strong>{action.title}</strong><small>{action.note}</small></span>
                    <span className={`badge ${action.tone}`}>{action.label}</span>
                  </Link>
                ))}
              </div>
            </aside>
          </section>

          <section className="dashboard-panel">
            <div className="dashboard-panel-head">
              <div>
                <h2>Connected applications</h2>
                <p>Operational systems remain authoritative. Accounting receives financial events, balances, and source references.</p>
              </div>
              <Link href="/approvals" className="button-link secondary-link">Open Review Inbox</Link>
            </div>
            <div className="dashboard-integrations">
              {integrations.map((item) => (
                <article className="integration-card" key={item.name}>
                  <div className="integration-card-head"><strong>{item.name}</strong><span className={`badge ${item.tone}`}>{item.status}</span></div>
                  <p>{item.text}</p>
                  <Link href={item.href} className="button-link secondary-link">Open workspace</Link>
                </article>
              ))}
            </div>
          </section>

          {!!tableCards.length && (
            <section className="dashboard-secondary-grid">
              {tableCards.slice(0, 4).map((card) => <DashboardTable key={card.key} card={card} />)}
            </section>
          )}

          <section className="dashboard-panel">
            <div className="dashboard-panel-head"><div><h2>Workspaces</h2><p>Continue into the full operational and accounting modules.</p></div></div>
            <div className="dashboard-workspaces">
              {WORKSPACES.map(([href, label, note]) => (
                <Link key={href} href={href} className="workspace-link">
                  <span><strong>{label}</strong><small>{note}</small></span><span>→</span>
                </Link>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
