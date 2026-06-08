'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import StaffActionPanel from '../../components/StaffActionPanel';
import { getDashboard } from '../../lib/api';

const WORKSPACES = [
  ['/workspace/rooms', 'Rooms & Guests', 'Bookings, room setup, guest profiles, folios'],
  ['/events', 'Events', 'Quotes, confirmations, deposits, balances, and completion'],
  ['/workspace/restaurant', 'Restaurant & F&B', 'Sales ops, menu/recipes, staff meals, outlets'],
  ['/workspace/inventory', 'Inventory & Purchasing', 'Stock, purchasing, receiving, and reconciliation'],
  ['/workspace/payroll', 'People & Payroll', 'Employees, attendance, payroll periods, approvals'],
  ['/workspace/finance', 'Finance & Accounting', 'Cashflow, journals, reports, BIR, and assets'],
  ['/workspace/settings', 'Settings', 'Master data, taxonomy, users, roles, and system setup'],
];

function formatValue(value) {
  if (typeof value === 'number') return Number(value).toLocaleString();
  if (value && typeof value === 'object') {
    if (Object.prototype.hasOwnProperty.call(value, 'locked_periods')) {
      return `${Number(value.locked_periods || 0).toLocaleString()} locked`;
    }
    if (
      Object.prototype.hasOwnProperty.call(value, 'employees')
      && Object.prototype.hasOwnProperty.call(value, 'payroll_periods_pending')
    ) {
      return `${Number(value.employees || 0).toLocaleString()} emp / ${Number(value.payroll_periods_pending || 0).toLocaleString()} pending`;
    }
    return JSON.stringify(value);
  }
  if (value === null || typeof value === 'undefined') return '-';
  return String(value);
}

function currency(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function typeLabel(value) {
  return String(value || '').replaceAll('_', ' ');
}

function toRowsFromWorkflowMap(map) {
  return Object.entries(map || {}).map(([workflow, pending]) => ({ workflow, pending }));
}

function BookingQueue({ title, rows, empty }) {
  return (
    <article className="card command-card">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <strong>{title}</strong>
        <span className="badge">{rows.length}</span>
      </div>
      <div className="stack" style={{ marginTop: 10 }}>
        {rows.map((row) => (
          <Link key={`${title}-${row.id}`} href={`/bookings/${row.id}`} className="command-row">
            <span>
              <strong>{row.room_name || 'No room'} · {row.guest_name}</strong>
              <small>{row.check_in || '-'} to {row.check_out || '-'} · {row.channel || 'Walk-in'}</small>
            </span>
            <span className="command-amount">{currency(row.folio_balance || 0)}</span>
          </Link>
        ))}
        {!rows.length && <p className="small muted">{empty}</p>}
      </div>
    </article>
  );
}

function FolioQueue({ rows }) {
  return (
    <article className="card command-card">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <strong>Open Folio Balances</strong>
        <Link className="button-link secondary-link" href="/room-folios">All</Link>
      </div>
      <div className="stack" style={{ marginTop: 10 }}>
        {rows.map((row) => (
          <Link key={`folio-${row.id}`} href={`/room-folios/${row.id}`} className="command-row">
            <span>
              <strong>{row.room_name || row.folio_no} · {row.guest_name || '-'}</strong>
              <small>{row.booking_ref} · deposits {currency(row.deposits || 0)} · payments {currency(row.payments || 0)}</small>
            </span>
            <span className="command-amount">{currency(row.balance || 0)}</span>
          </Link>
        ))}
        {!rows.length && <p className="small muted">No open folio balances needing attention.</p>}
      </div>
    </article>
  );
}

function FolioLineReview({ title, rows }) {
  return (
    <article className="card command-card">
      <strong>{title}</strong>
      <div className="stack" style={{ marginTop: 10 }}>
        {rows.map((row) => (
          <Link key={`${title}-${row.id}`} href={`/room-folios/${row.folio_id}`} className="command-row">
            <span>
              <strong>{typeLabel(row.line_type)} · {row.room_name || row.folio_no}</strong>
              <small>{row.description || row.reference_no || '-'} · {row.external_source || 'manual'}</small>
            </span>
            <span className="command-amount">{currency(row.amount || 0)}</span>
          </Link>
        ))}
        {!rows.length && <p className="small muted">No recent lines to review.</p>}
      </div>
    </article>
  );
}

export default function DashboardPage() {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    getDashboard()
      .then((data) => setSummary(data))
      .catch((err) => setError(err.message || 'Failed to load dashboard.'));
  }, []);

  const widgetCards = useMemo(() => {
    const incoming = Array.isArray(summary?.dashboard_widget_cards) ? summary.dashboard_widget_cards : [];
    if (incoming.length) return incoming;

    if (!summary) return [];
    return [
      { key: 'arrivals_today', type: 'metric', label: 'Arrivals Today', value: summary.arrivals_today },
      { key: 'departures_today', type: 'metric', label: 'Departures Today', value: summary.departures_today },
      { key: 'in_house_guests', type: 'metric', label: 'In-house Guests', value: summary.in_house_guests || summary.bookings_checked_in },
      { key: 'occupancy_rate', type: 'metric', label: 'Occupancy', value: summary.occupancy_rate },
      { key: 'revenue_today', type: 'metric', label: 'Revenue Today', value: summary.revenue_today },
      { key: 'cash_in_today', type: 'metric', label: 'Cash In Today', value: summary.cash_in_today },
      { key: 'cash_out_today', type: 'metric', label: 'Cash Out Today', value: summary.cash_out_today },
      { key: 'pending_approvals', type: 'metric', label: 'Pending Approvals', value: summary.pending_approvals },
      { key: 'low_stock_count', type: 'metric', label: 'Low Stock Alerts', value: summary.low_stock_count },
      {
        key: 'pending_by_workflow',
        type: 'table',
        label: 'Pending by Workflow',
        columns: ['workflow', 'pending'],
        rows: toRowsFromWorkflowMap(summary.pending_by_workflow),
      },
      {
        key: 'top_channels',
        type: 'table',
        label: 'Top Channels',
        columns: ['channel', 'booking_count', 'revenue'],
        rows: summary.top_channels || [],
      },
      {
        key: 'low_stock_items',
        type: 'table',
        label: 'Low Stock Items',
        columns: ['name', 'quantity_on_hand', 'reorder_level', 'unit'],
        rows: summary.low_stock_items || [],
      },
    ];
  }, [summary]);

  const metricCards = widgetCards.filter((card) => card.type === 'metric');
  const tableCards = widgetCards.filter((card) => card.type === 'table');
  const commandCenter = summary?.command_center || {};

  return (
    <div className="stack">
      <section className="section">
        <h1>Dashboard</h1>
        <p className="muted">Start with the work staff actually need, then review operations and accounting from the widgets below.</p>
        {!!summary?.dashboard_role && <p className="small muted">Current layout: {summary.dashboard_role.replaceAll('_', ' ')}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <StaffActionPanel title="Common Work" />

      {!!summary && (
        <section className="section">
          <div className="row wrap" style={{ justifyContent: 'space-between', alignItems: 'flex-end' }}>
            <div>
              <h2>Today&apos;s Command Center</h2>
              <p className="muted">Front desk money, stay movement, Beds24 sync, and cafe room-charge review in one place.</p>
            </div>
            {!!commandCenter.beds24_sync && (
              <span className="badge">
                Beds24 {commandCenter.beds24_sync.status}: {commandCenter.beds24_sync.event_type}
              </span>
            )}
          </div>
          <div className="card-grid command-grid" style={{ marginTop: 12 }}>
            <BookingQueue title="Arrivals" rows={commandCenter.arrivals || []} empty="No arrivals loaded for today." />
            <BookingQueue title="In-house" rows={commandCenter.in_house || []} empty="No in-house stays loaded." />
            <BookingQueue title="Departures" rows={commandCenter.departures || []} empty="No departures loaded for today." />
            <FolioQueue rows={commandCenter.open_folio_alerts || []} />
            <FolioLineReview title="Deposits & Payments" rows={commandCenter.payment_review || []} />
            <FolioLineReview title="Charges & Room Service" rows={commandCenter.room_charge_review || []} />
          </div>
        </section>
      )}

      {!!summary && (
        <section className="section">
          <h2>Snapshot</h2>
          <div className="card-grid" style={{ marginTop: 10 }}>
            {metricCards.map((card) => (
              <div key={card.key} className="card">
                <div className="muted">{card.label}</div>
                <div className="kpi">{formatValue(card.value)}</div>
                {!!card.description && <div className="small muted" style={{ marginTop: 6 }}>{card.description}</div>}
              </div>
            ))}
            {!metricCards.length && <div className="card muted">No widget cards enabled for this dashboard.</div>}
          </div>
        </section>
      )}

      {!!tableCards.length && (
        <section className="section">
          <h2>Detailed Widgets</h2>
          <div className="grid">
            {tableCards.map((card) => (
              <div key={card.key} className="card" style={{ padding: 0, overflow: 'hidden' }}>
                <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--line)' }}>
                  <strong>{card.label}</strong>
                  {!!card.description && <div className="small muted" style={{ marginTop: 4 }}>{card.description}</div>}
                </div>
                <div style={{ padding: '0 10px 10px' }}>
                  <table className="table dense-table">
                    <thead>
                      <tr>
                        {(card.columns || []).map((col) => <th key={`${card.key}-${col}`}>{String(col).replaceAll('_', ' ')}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {(card.rows || []).map((row, idx) => (
                        <tr key={`${card.key}-${idx}`}>
                          {(card.columns || []).map((col) => <td key={`${card.key}-${idx}-${col}`}>{formatValue(row?.[col])}</td>)}
                        </tr>
                      ))}
                      {!(card.rows || []).length && (
                        <tr>
                          <td colSpan={(card.columns || []).length || 1} className="muted">No data yet.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="section">
        <h2>Workspaces</h2>
        <div className="card-grid" style={{ marginTop: 10 }}>
          {WORKSPACES.map(([href, label, note]) => (
            <Link key={href} href={href} className="card card-link">
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <strong>{label}</strong>
                <span>→</span>
              </div>
              <div className="small muted">{note}</div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
