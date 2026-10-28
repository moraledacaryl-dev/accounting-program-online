'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { businessDateISO } from '../../lib/businessDate';
import { request } from '../../lib/api';
import { useCurrentUser } from '../../lib/useCurrentUser';
import './channel-payouts.css';

const HISTORY_PAGE_SIZE = 200;

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
  const canReconcile = can('cashflow.money_in') || can('cashflow.money_out');
  const [tab, setTab] = useState('awaiting');
  const [channels, setChannels] = useState([]);
  const [channelId, setChannelId] = useState('');
  const [rows, setRows] = useState([]);
  const [bookingsLoading, setBookingsLoading] = useState(false);
  const [bookingsLoaded, setBookingsLoaded] = useState(false);
  const [bookingsError, setBookingsError] = useState('');
  const bookingsRequest = useRef(0);
  const [history, setHistory] = useState([]);
  const [historyHasMore, setHistoryHasMore] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [loadingOlderHistory, setLoadingOlderHistory] = useState(false);
  const historyGeneration = useRef(0);
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
    const generation = ++historyGeneration.current;
    setHistoryHasMore(false);
    setHistoryLoaded(false);
    const data = await request(`/channel-reconciliation/history?limit=${HISTORY_PAGE_SIZE}`);
    if (!Array.isArray(data)) throw new Error('Payout history returned an unexpected response.');
    if (generation !== historyGeneration.current) return;
    const page = data;
    setHistory(page);
    setHistoryHasMore(page.length === HISTORY_PAGE_SIZE);
    setHistoryLoaded(true);
  }

  async function loadOlderHistory() {
    if (!historyHasMore || loadingOlderHistory || !history.length) return;
    const generation = historyGeneration.current;
    const last = history[history.length - 1];
    const params = new URLSearchParams({
      limit: String(HISTORY_PAGE_SIZE),
      before_date: last.actual_payout_date || '',
      before_id: String(last.id),
    });
    setLoadingOlderHistory(true);
    setError('');
    try {
      const data = await request(`/channel-reconciliation/history?${params.toString()}`);
      if (!Array.isArray(data)) throw new Error('Payout history returned an unexpected response.');
      if (generation !== historyGeneration.current) return;
      const page = data;
      setHistory((current) => {
        const seen = new Set(current.map((row) => row.id));
        return [...current, ...page.filter((row) => !seen.has(row.id))];
      });
      setHistoryHasMore(page.length === HISTORY_PAGE_SIZE);
    } catch (err) {
      setError(err.message || 'Failed to load older payouts.');
    } finally {
      setLoadingOlderHistory(false);
    }
  }

  async function loadBookings(nextChannelId = channelId, term = search, { clear = false } = {}) {
    const requestId = ++bookingsRequest.current;
    setBookingsError('');
    if (clear) { setRows([]); setBookingsLoaded(false); }
    if (!nextChannelId) { setRows([]); setBookingsLoaded(true); setBookingsLoading(false); return; }
    setBookingsLoading(true);
    const params = new URLSearchParams({ channel_id: String(nextChannelId) });
    if (term.trim()) params.set('search', term.trim());
    try {
      const data = await request(`/channel-reconciliation/bookings?${params.toString()}`);
      if (requestId !== bookingsRequest.current) return;
      if (!Array.isArray(data)) throw new Error('Channel bookings returned an unexpected response.');
      setRows(data);
      setBookingsLoaded(true);
    } catch (err) {
      if (requestId === bookingsRequest.current) {
        setBookingsError(err.message || 'Failed to load bookings awaiting payout.');
        throw err;
      }
    } finally {
      if (requestId === bookingsRequest.current) setBookingsLoading(false);
    }
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
    loadBookings(channelId, search, { clear: true }).catch(() => {});
  }, [channelId]);

  const chosen = useMemo(() => rows.filter((row) => selected[row.booking_id]?.checked), [rows, selected]);
  const rowExpected = (row) => selected[row.booking_id]?.expected ?? String(num(row.expected_net_amount).toFixed(2));
  const totals = useMemo(() => {
    const original = chosen.reduce((sum, row) => sum + num(row.original_amount), 0);
    const expected = chosen.reduce((sum, row) => sum + num(selected[row.booking_id]?.expected ?? row.expected_net_amount), 0);
    const actual = chosen.reduce((sum, row) => sum + num(selected[row.booking_id]?.actual), 0);
    const difference = original - expected;
    const variance = expected - actual;
    return { original, expected, actual, difference, variance, rate: original > 0 ? difference / original * 100 : null };
  }, [chosen, selected]);
  const expectedTotal = useMemo(() => rows.reduce((sum, row) => sum + num(selected[row.booking_id]?.expected ?? row.expected_net_amount), 0), [rows, selected]);
  const originalTotal = useMemo(() => rows.reduce((sum, row) => sum + num(row.original_amount), 0), [rows]);
  const allocationMatches = amountReceived === '' || Math.abs(num(amountReceived) - totals.actual) < 0.005;
  const completeAmounts = chosen.length > 0 && chosen.every((row) => {
    const entry = selected[row.booking_id];
    return entry?.expected !== '' && entry?.actual !== '' && num(entry?.expected) >= 0 && num(entry?.actual) >= 0;
  });

  function toggleRow(row, checked) {
    setSelected((current) => {
      const expected = current[row.booking_id]?.expected ?? String(num(row.expected_net_amount).toFixed(2));
      return {
        ...current,
        [row.booking_id]: {
          ...current[row.booking_id],
          checked,
          expected,
          actual: current[row.booking_id]?.actual ?? expected,
        },
      };
    });
  }

  function setExpected(row, value) {
    setSelected((current) => {
      const prior = current[row.booking_id] || {};
      const priorExpected = prior.expected ?? String(num(row.expected_net_amount).toFixed(2));
      const shouldFollow = prior.actual === undefined || prior.actual === '' || prior.actual === priorExpected;
      return {
        ...current,
        [row.booking_id]: {
          ...prior,
          checked: true,
          expected: value,
          actual: shouldFollow ? value : prior.actual,
        },
      };
    });
  }

  function setActual(row, value) {
    setSelected((current) => ({
      ...current,
      [row.booking_id]: {
        ...current[row.booking_id],
        checked: true,
        expected: current[row.booking_id]?.expected ?? String(num(row.expected_net_amount).toFixed(2)),
        actual: value,
      },
    }));
  }

  function toggleAll(checked) {
    if (!checked) { setSelected({}); return; }
    const next = {};
    rows.forEach((row) => {
      const expected = selected[row.booking_id]?.expected ?? String(num(row.expected_net_amount).toFixed(2));
      next[row.booking_id] = {
        ...selected[row.booking_id],
        checked: true,
        expected,
        actual: selected[row.booking_id]?.actual ?? expected,
      };
    });
    setSelected(next);
  }

  async function reconcile() {
    if (!completeAmounts || !allocationMatches || !channelId || bookingsLoading || bookingsError) return;
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
        items: chosen.map((row) => ({
          booking_id: row.booking_id,
          expected_amount: num(selected[row.booking_id]?.expected),
          actual_amount: num(selected[row.booking_id]?.actual),
        })),
      };
      const result = await request('/channel-reconciliation/reconcile', { method: 'POST', body: JSON.stringify(payload) });
      setNotice(`${result.booking_count} booking${result.booking_count === 1 ? '' : 's'} reconciled. ${money(result.allocated_amount)} recorded as channel payout.`);
      setSelected({}); setReference(''); setAmountReceived(''); setNotes('');
      try {
        await Promise.all([loadBookings(channelId, search), loadHistory()]);
      } catch {
        setError('Payout recorded, but the lists could not be refreshed. Refresh them before recording another payout.');
      }
    } catch (err) {
      if (err.status === 409) {
        try {
          await Promise.all([loadBookings(channelId, search), loadHistory()]);
          setError('A selected booking was already recorded in another session. The list has been refreshed; review the remaining selections before trying again.');
        } catch {
          setError('A selected booking was already recorded in another session. The list could not be refreshed; refresh it before trying again.');
        }
      } else {
        setError(err.message || 'Failed to reconcile payout.');
      }
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
            <p className="muted">Use the fixed standard room rate as the baseline. Expected payout can be entered or corrected manually, and actual payout starts equal to expected until the bank deposit differs.</p>
            {!canReconcile && <p className="muted" role="status">Payouts are read-only for your role. A cashflow recording permission is required to record or change a payout.</p>}
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
              <input value={search} placeholder="Search awaiting bookings" onChange={(e) => setSearch(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); loadBookings(channelId, search).catch(() => {}); } }} />
            </label>
            {canReconcile && <label>Payout date<input type="date" value={payoutDate} onChange={(e) => setPayoutDate(e.target.value)} /></label>}
            {canReconcile && <label>Statement / reference<input value={reference} placeholder="Optional" onChange={(e) => setReference(e.target.value)} /></label>}
          </div>
          <div className="payout-kpis">
            <div className="payout-kpi"><span>Awaiting bookings</span><strong>{rows.length}</strong></div>
            <div className="payout-kpi"><span>Standard room rate</span><strong>{money(originalTotal)}</strong></div>
            <div className="payout-kpi"><span>Expected payout</span><strong>{money(expectedTotal)}</strong></div>
            <div className="payout-kpi"><span>Difference vs room rate</span><strong>{money(originalTotal - expectedTotal)}</strong></div>
          </div>
        </section>

        <section className="section">
          <div className="row wrap" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
            <div><h2>Bookings awaiting payout</h2><p className="muted small">{canReconcile ? 'Expected payout is editable for new or corrected data. Actual payout follows expected until you change the actual bank receipt.' : 'View expected payouts and recorded history. Recording requires a cashflow permission.'}</p>{rows.length >= 2000 && <p className="muted small" role="status">Showing the first 2,000 unpaid bookings. Search by guest or booking ID to find older bookings.</p>}</div>
            <button type="button" className="secondary" onClick={() => loadBookings(channelId, search).catch(() => {})}>Refresh</button>
          </div>
          {!!bookingsError && <p className="error-text" role="alert">{bookingsError}</p>}
          {rows.length > 0 ? <div className="table-wrap">
            <table className="table payout-table">
              <thead><tr><th className="select-cell">{canReconcile && <input aria-label="Select all bookings" type="checkbox" checked={rows.length > 0 && chosen.length === rows.length} onChange={(e) => toggleAll(e.target.checked)} />}</th><th>Booking</th><th>Stay</th><th className="amount">Standard room rate</th><th className="amount">Expected payout</th><th className="amount">Actual payout</th><th className="amount">Difference vs room rate</th></tr></thead>
              <tbody>
                {rows.map((row) => {
                  const entry = selected[row.booking_id] || {};
                  const expectedValue = entry.expected ?? String(num(row.expected_net_amount).toFixed(2));
                  const expected = num(expectedValue);
                  const actual = entry.actual === '' || entry.actual === undefined ? expected : num(entry.actual);
                  const difference = num(row.original_amount) - expected;
                  const rate = num(row.original_amount) > 0 ? difference / num(row.original_amount) * 100 : null;
                  const variance = expected - actual;
                  return <tr key={row.booking_id} className={entry.checked ? 'selected' : ''}>
                    <td className="select-cell">{canReconcile && <input aria-label={`Select booking ${row.booking_ref}`} type="checkbox" checked={!!entry.checked} onChange={(e) => toggleRow(row, e.target.checked)} />}</td>
                    <td><div className="booking-primary">{row.guest_name || 'Unnamed Guest'}</div><div className="booking-secondary">{row.booking_ref} · {row.room_name || 'Room not set'}</div></td>
                    <td><div>{row.check_in || '—'} → {row.check_out || '—'}</div><div className="booking-secondary">{row.booking_status}</div></td>
                    <td className="amount">{money(row.original_amount)}</td>
                    <td className="amount">{canReconcile ? <input aria-label={`Expected payout for ${row.booking_ref}`} className="payout-amount-input" type="number" min="0" step="0.01" inputMode="decimal" value={expectedValue} onChange={(e) => setExpected(row, e.target.value)} /> : money(expected)}<div className="payout-rate">{money(Math.abs(difference))} {difference >= 0 ? 'below' : 'above'} room rate</div></td>
                    <td className="amount">{canReconcile ? <input aria-label={`Actual payout for ${row.booking_ref}`} className="payout-amount-input" type="number" min="0" step="0.01" inputMode="decimal" placeholder={expected.toFixed(2)} value={entry.actual ?? expectedValue} onChange={(e) => setActual(row, e.target.value)} /> : money(actual)}{Math.abs(variance) >= 0.005 && <div className="payout-rate">{money(Math.abs(variance))} {variance > 0 ? 'below' : 'above'} expected</div>}</td>
                    <td className="amount"><div className="payout-deduction">{money(difference)}</div><div className="payout-rate">{rate === null ? '—' : `${pct(rate)} vs standard rate`}</div></td>
                  </tr>;
                })}
              </tbody>
            </table>
          </div> : <div className="payout-empty" role="status">{loading || bookingsLoading ? 'Loading channel bookings…' : !channelId ? 'No active booking channel.' : bookingsLoaded ? 'No unpaid bookings for this channel.' : 'Channel bookings could not be loaded. Refresh to try again.'}</div>}
        </section>

        {chosen.length > 0 && <section className="section payout-summary">
          <div>
            <div className="payout-summary-values">
              <div><span>Selected</span><strong>{chosen.length} booking{chosen.length === 1 ? '' : 's'}</strong></div>
              <div><span>Standard room rate</span><strong>{money(totals.original)}</strong></div>
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
            <button type="button" disabled={!canReconcile || !completeAmounts || !allocationMatches || bookingsLoading || !!bookingsError || saving} onClick={reconcile}>{saving ? 'Recording…' : `Record payout ${money(totals.actual)}`}</button>
          </div>
        </section>}
      </>}

      {tab === 'history' && <section className="section">
        <div style={{ marginBottom: 10 }}><h2>Payout history</h2><p className="muted small">History keeps the standard room-rate baseline, entered expected payout, actual receipt, and resulting differences.</p>{historyLoaded && <p className="muted small" role="status">Showing {history.length} payout record{history.length === 1 ? '' : 's'}{historyHasMore ? '; older records are available below' : ''}.</p>}</div>
        {!historyGroups.length && <div className="payout-empty">{loading ? 'Loading payout history…' : historyLoaded ? 'No reconciled booking payouts yet.' : 'Payout history could not be loaded. Refresh the page to try again.'}</div>}
        {historyGroups.map((group) => <div className="payout-history-batch" key={group.key}>
          <div className="payout-history-head"><strong>{group.channel}<br/><span>{group.reference}</span></strong><span>{group.date}</span><span>{group.rows.length} booking{group.rows.length === 1 ? '' : 's'}</span><span>Expected<br/><strong>{money(group.expected)}</strong></span><span>Received<br/><strong>{money(group.actual)}</strong></span></div>
          <div className="payout-history-body table-wrap"><table className="table"><thead><tr><th>Booking</th><th>Guest</th><th>Stay</th><th>Standard room rate</th><th>Expected payout</th><th>Actual payout</th><th>Difference vs room rate</th></tr></thead><tbody>{group.rows.map((row) => <tr key={row.id}><td>{row.booking_ref || `#${row.booking_id}`}</td><td>{row.guest_name || '—'}</td><td>{row.check_in || '—'} → {row.check_out || '—'}</td><td>{money(row.gross_amount)}</td><td>{money(row.expected_amount)}</td><td>{money(row.actual_amount)}</td><td>{money(row.deduction_amount)} <span className="muted">({pct(row.deduction_percent)})</span></td></tr>)}</tbody></table></div>
        </div>)}
        {historyHasMore && <button type="button" className="secondary" disabled={loadingOlderHistory} onClick={loadOlderHistory}>{loadingOlderHistory ? 'Loading older payouts…' : 'Load older payouts'}</button>}
      </section>}
    </div>
  );
}
