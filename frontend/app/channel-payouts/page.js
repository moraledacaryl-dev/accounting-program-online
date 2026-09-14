'use client';

import { useEffect, useMemo, useState } from 'react';
import { businessDateISO } from '../../lib/businessDate';
import { request } from '../../lib/api';
import { useCurrentUser } from '../../lib/useCurrentUser';
import './channel-payouts.css';

function money(value) {
  return Number(value || 0).toLocaleString('en-PH', { style: 'currency', currency: 'PHP', minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function pct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return `${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
}

function num(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function groupHistory(rows) {
  const groups = new Map();
  for (const row of rows) {
    const key = `${row.channel_id}|${row.actual_payout_date || ''}|${row.payout_reference || `payout-${row.id}`}`;
    if (!groups.has(key)) groups.set(key, { key, channel: row.channel_name || 'Channel', date: row.actual_payout_date || '—', reference: row.payout_reference || `PAYOUT-${row.id}`, rows: [] });
    groups.get(key).rows.push(row);
  }
  return Array.from(groups.values()).map((group) => ({
    ...group,
    original: group.rows.reduce((sum, row) => sum + num(row.gross_amount), 0),
    expected: group.rows.reduce((sum, row) => sum + num(row.expected_amount), 0),
    actual: group.rows.reduce((sum, row) => sum + num(row.actual_amount), 0),
    difference: group.rows.reduce((sum, row) => sum + num(row.deduction_amount), 0),
  }));
}

export default function PayoutsPage() {
  const { can } = useCurrentUser();
  const canReconcile = can('cashflow.money_in') || can('cashflow.money_out') || can('reports.view');
  const [tab, setTab] = useState('awaiting');
  const [channels, setChannels] = useState([]);
  const [channelId, setChannelId] = useState('');
  const [rows, setRows] = useState([]);
  const [history, setHistory] = useState([]);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState({});
  const [payoutDate, setPayoutDate] = useState(businessDateISO());
  const [reference, setReference] = useState('');
  const [amountReceived, setAmountReceived] = useState('');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function loadOptions() {
    const data = await request('/channel-reconciliation/channels');
    const available = Array.isArray(data) ? data : [];
    setChannels(available);
    setChannelId((current) => current || (available[0]?.id ? String(available[0].id) : ''));
  }

  async function loadHistory() {
    const data = await request('/channel-reconciliation/history');
    setHistory(Array.isArray(data) ? data : []);
  }

  async function loadBookings(nextChannelId = channelId, term = search) {
    if (!nextChannelId) { setRows([]); return; }
    const params = new URLSearchParams({ channel_id: String(nextChannelId) });
    if (term.trim()) params.set('search', term.trim());
    const data = await request(`/channel-reconciliation/bookings?${params.toString()}`);
    setRows(Array.isArray(data) ? data : []);
  }

  useEffect(() => {
    setLoading(true);
    Promise.all([loadOptions(), loadHistory()])
      .catch((err) => setError(err.message || 'Failed to load channel payouts.'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!channelId) return;
    setSelected({});
    loadBookings(channelId, search).catch((err) => setError(err.message || 'Failed to load bookings awaiting payout.'));
  }, [channelId]);

  const chosen = useMemo(() => rows.filter((row) => selected[row.booking_id]?.checked), [rows, selected]);
  const totals = useMemo(() => {
    const original = chosen.reduce((sum, row) => sum + num(row.original_amount), 0);
    const expected = chosen.reduce((sum, row) => sum + num(row.expected_net_amount), 0);
    const actual = chosen.reduce((sum, row) => sum + num(selected[row.booking_id]?.actual), 0);
    const difference = original - actual;
    const variance = expected - actual;
    return { original, expected, actual, difference, variance, rate: original > 0 ? difference / original * 100 : null };
  }, [chosen, selected]);
  const expectedTotal = useMemo(() => rows.reduce((sum, row) => sum + num(row.expected_net_amount), 0), [rows]);
  const originalTotal = useMemo(() => rows.reduce((sum, row) => sum + num(row.original_amount), 0), [rows]);
  const allocationMatches = amountReceived === '' || Math.abs(num(amountReceived) - totals.actual) < 0.005;
  const completeAmounts = chosen.length > 0 && chosen.every((row) => selected[row.booking_id]?.actual !== '' && num(selected[row.booking_id]?.actual) >= 0 && num(selected[row.booking_id]?.actual) <= Math.max(num(row.original_amount), num(row.expected_net_amount)));

  function toggleRow(row, checked) {
    setSelected((current) => ({
      ...current,
      [row.booking_id]: {
        checked,
        actual: current[row.booking_id]?.actual ?? String(num(row.expected_net_amount).toFixed(2)),
      },
    }));
  }

  function setActual(row, value) {
    setSelected((current) => ({ ...current, [row.booking_id]: { checked: true, actual: value } }));
  }

  function toggleAll(checked) {
    if (!checked) { setSelected({}); return; }
    const next = {};
    rows.forEach((row) => {
      next[row.booking_id] = {
        checked: true,
        actual: selected[row.booking_id]?.actual ?? String(num(row.expected_net_amount).toFixed(2)),
      };
    });
    setSelected(next);
  }

  async function reconcile() {
    if (!completeAmounts || !allocationMatches || !channelId) return;
    setSaving(true); setError(''); setNotice('');
    try {
      const payload = {
        channel_id: Number(channelId),
        actual_payout_date: payoutDate,
        payout_reference: reference.trim() || null,
        amount_received: amountReceived === '' ? null : num(amountReceived),
        payment_method: 'bank_transfer',
        auto_post_accounting: true,
        notes: notes.trim() || null,
        items: chosen.map((row) => ({ booking_id: row.booking_id, actual_amount: num(selected[row.booking_id]?.actual) })),
      };
      const result = await request('/channel-reconciliation/reconcile', { method: 'POST', body: JSON.stringify(payload) });
      setNotice(`${result.booking_count} booking${result.booking_count === 1 ? '' : 's'} reconciled. ${money(result.allocated_amount)} recorded as channel payout.`);
      setSelected({}); setReference(''); setAmountReceived(''); setNotes('');
      await Promise.all([loadBookings(channelId, search), loadHistory()]);
    } catch (err) {
      setError(err.message || 'Failed to reconcile payout.');
    } finally {
      setSaving(false);
    }
  }

  const historyGroups = useMemo(() => groupHistory(history), [history]);

  return (
    <div className="payout-page">
      <section className="section">
        <div className="payout-hero">
          <div className="payout-hero-copy">
            <h1>Channel Payouts</h1>
            <p className="muted">Compare the normal room rate with the OTA booking value, then confirm what the channel actually deposited. Expected and actual payout start the same and only differ when the deposit really differs.</p>
          </div>
          <div className="payout-tabs" role="tablist" aria-label="Channel payout views">
            <button type="button" className={`payout-tab ${tab === 'awaiting' ? 'active' : ''}`} onClick={() => setTab('awaiting')}>Awaiting payout</button>
            <button type="button" className={`payout-tab ${tab === 'history' ? 'active' : ''}`} onClick={() => setTab('history')}>Payout history</button>
          </div>
        </div>
        {!!notice && <p className="success-text" style={{ marginTop: 12 }}>{notice}</p>}
        {!!error && <p className="error-text" style={{ marginTop: 12 }}>{error}</p>}
      </section>

      {tab === 'awaiting' && <>
        <section className="section">
          <div className="payout-filter-grid">
            <label>Booking channel
              <select value={channelId} onChange={(e) => setChannelId(e.target.value)} disabled={loading}>
                {!channels.length && <option value="">No active channels</option>}
                {channels.map((row) => <option key={row.id} value={row.id}>{row.name}{row.code ? ` · ${row.code}` : ''}</option>)}
              </select>
            </label>
            <label>Guest or booking ID
              <input value={search} placeholder="Search awaiting bookings" onChange={(e) => setSearch(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); loadBookings(channelId, search).catch((err) => setError(err.message)); } }} />
            </label>
            <label>Payout date<input type="date" value={payoutDate} onChange={(e) => setPayoutDate(e.target.value)} /></label>
            <label>Statement / reference<input value={reference} placeholder="Optional" onChange={(e) => setReference(e.target.value)} /></label>
          </div>
          <div className="payout-kpis">
            <div className="payout-kpi"><span>Awaiting bookings</span><strong>{rows.length}</strong></div>
            <div className="payout-kpi"><span>Normal room rate</span><strong>{money(originalTotal)}</strong></div>
            <div className="payout-kpi"><span>Expected payout</span><strong>{money(expectedTotal)}</strong></div>
            <div className="payout-kpi"><span>Difference vs room rate</span><strong>{money(originalTotal - expectedTotal)}</strong></div>
          </div>
        </section>

        <section className="section">
          <div className="row wrap" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
            <div><h2>Bookings awaiting payout</h2><p className="muted small">Actual payout is prefilled from the expected OTA booking value. Change it only when the bank deposit differs.</p></div>
            <button type="button" className="secondary" onClick={() => loadBookings(channelId, search).catch((err) => setError(err.message))}>Refresh</button>
          </div>
          <div className="table-wrap">
            <table className="table payout-table">
              <thead><tr><th className="select-cell"><input aria-label="Select all bookings" type="checkbox" checked={rows.length > 0 && chosen.length === rows.length} onChange={(e) => toggleAll(e.target.checked)} /></th><th>Booking</th><th>Stay</th><th className="amount">Normal room rate</th><th className="amount">Expected payout</th><th className="amount">Actual payout</th><th className="amount">Difference vs room rate</th></tr></thead>
              <tbody>
                {rows.map((row) => {
                  const entry = selected[row.booking_id] || {};
                  const actual = entry.actual === '' || entry.actual === undefined ? null : num(entry.actual);
                  const difference = actual === null ? num(row.original_amount) - num(row.expected_net_amount) : num(row.original_amount) - actual;
                  const rate = num(row.original_amount) > 0 ? difference / num(row.original_amount) * 100 : null;
                  const variance = actual === null ? null : num(row.expected_net_amount) - actual;
                  return <tr key={row.booking_id} className={entry.checked ? 'selected' : ''}>
                    <td className="select-cell"><input aria-label={`Select booking ${row.booking_ref}`} type="checkbox" checked={!!entry.checked} onChange={(e) => toggleRow(row, e.target.checked)} /></td>
                    <td><div className="booking-primary">{row.guest_name || 'Unnamed Guest'}</div><div className="booking-secondary">{row.booking_ref} · {row.room_name || 'Room not set'}</div></td>
                    <td><div>{row.check_in || '—'} → {row.check_out || '—'}</div><div className="booking-secondary">{row.booking_status}</div></td>
                    <td className="amount">{money(row.original_amount)}</td>
                    <td className="amount"><div>{money(row.expected_net_amount)}</div><div className="payout-rate">{money(row.expected_difference_amount)} below room rate</div></td>
                    <td className="amount"><input className="payout-amount-input" type="number" min="0" max={Math.max(num(row.original_amount), num(row.expected_net_amount))} step="0.01" inputMode="decimal" placeholder={num(row.expected_net_amount).toFixed(2)} value={entry.actual ?? ''} onChange={(e) => setActual(row, e.target.value)} />{variance !== null && Math.abs(variance) >= 0.005 && <div className="payout-rate">{money(Math.abs(variance))} {variance > 0 ? 'below' : 'above'} expected</div>}</td>
                    <td className="amount"><div className="payout-deduction">{money(difference)}</div><div className="payout-rate">{rate === null ? '—' : `${pct(rate)} below normal rate`}</div></td>
                  </tr>;
                })}
                {!rows.length && <tr><td colSpan="7" className="payout-empty">{loading ? 'Loading channel bookings…' : 'No unpaid bookings for this channel.'}</td></tr>}
              </tbody>
            </table>
          </div>
        </section>

        {chosen.length > 0 && <section className="section payout-summary">
          <div>
            <div className="payout-summary-values">
              <div><span>Selected</span><strong>{chosen.length} booking{chosen.length === 1 ? '' : 's'}</strong></div>
              <div><span>Normal room rate</span><strong>{money(totals.original)}</strong></div>
              <div><span>Expected payout</span><strong>{money(totals.expected)}</strong></div>
              <div><span>Actual payout</span><strong>{money(totals.actual)}</strong></div>
              <div><span>Difference vs room rate</span><strong>{money(totals.difference)} · {pct(totals.rate)}</strong></div>
            </div>
            <div className="form-grid" style={{ marginTop: 10 }}>
              <label>Bank payout received (optional cross-check)<input type="number" min="0" step="0.01" inputMode="decimal" value={amountReceived} placeholder={money(totals.actual).replace('₱','').trim()} onChange={(e) => setAmountReceived(e.target.value)} /></label>
              <label>Batch notes<input value={notes} placeholder="Optional note for this payout" onChange={(e) => setNotes(e.target.value)} /></label>
            </div>
            {Math.abs(totals.variance) >= 0.005 && <div className="payout-match">Actual payout differs from expected by {money(Math.abs(totals.variance))}.</div>}
            {amountReceived !== '' && <div className={`payout-match ${allocationMatches ? 'payout-good' : 'error-text'}`}>{allocationMatches ? '✓ Allocations match the bank payout.' : `${money(Math.abs(num(amountReceived) - totals.actual))} remains ${num(amountReceived) > totals.actual ? 'unallocated' : 'over-allocated'}.`}</div>}
          </div>
          <div className="payout-actions">
            <button type="button" className="secondary" onClick={() => setSelected({})}>Clear selection</button>
            <button type="button" disabled={!canReconcile || !completeAmounts || !allocationMatches || saving} onClick={reconcile}>{saving ? 'Recording…' : `Record payout ${money(totals.actual)}`}</button>
          </div>
        </section>}
      </>}

      {tab === 'history' && <section className="section">
        <div style={{ marginBottom: 10 }}><h2>Payout history</h2><p className="muted small">History keeps the normal room-rate baseline, expected OTA amount, actual receipt, and resulting difference.</p></div>
        {!historyGroups.length && <div className="payout-empty">No reconciled booking payouts yet.</div>}
        {historyGroups.map((group) => <div className="payout-history-batch" key={group.key}>
          <div className="payout-history-head"><strong>{group.channel}<br/><span>{group.reference}</span></strong><span>{group.date}</span><span>{group.rows.length} booking{group.rows.length === 1 ? '' : 's'}</span><span>Expected<br/><strong>{money(group.expected)}</strong></span><span>Received<br/><strong>{money(group.actual)}</strong></span></div>
          <div className="payout-history-body table-wrap"><table className="table"><thead><tr><th>Booking</th><th>Guest</th><th>Stay</th><th>Normal room rate</th><th>Expected payout</th><th>Actual payout</th><th>Difference</th></tr></thead><tbody>{group.rows.map((row) => <tr key={row.id}><td>{row.booking_ref || `#${row.booking_id}`}</td><td>{row.guest_name || '—'}</td><td>{row.check_in || '—'} → {row.check_out || '—'}</td><td>{money(row.gross_amount)}</td><td>{money(row.expected_amount)}</td><td>{money(row.actual_amount)}</td><td>{money(row.deduction_amount)} <span className="muted">({pct(row.deduction_percent)})</span></td></tr>)}</tbody></table></div>
        </div>)}
      </section>}
    </div>
  );
}