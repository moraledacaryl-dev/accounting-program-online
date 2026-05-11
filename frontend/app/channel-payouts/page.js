'use client';

import { useEffect, useState } from 'react';
import { createPayout, fetchPayoutChannelOptions, fetchPayouts, settlePayout, updatePayout } from '../../lib/api';
import { shouldPreventEnterSubmit } from '../../lib/formBehavior';
import { useCurrentUser } from '../../lib/useCurrentUser';

const PAYMENT_METHODS = ['ota_payout', 'bank_transfer', 'cash', 'gcash'];

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function money(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

const EMPTY_FORM = {
  channel_choice: '',
  booking_ref: '',
  gross_amount: '',
  commission_amount: '',
  net_amount: '',
  payment_method: 'ota_payout',
  auto_post_accounting: false,
  expected_payout_date: '',
  actual_payout_date: '',
  status: 'pending',
  notes: '',
};

export default function PayoutsPage() {
  const { can } = useCurrentUser();
  const [rows, setRows] = useState([]);
  const [channelOptions, setChannelOptions] = useState([]);
  const [legacyChannels, setLegacyChannels] = useState([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });

  function parseChannelChoice(value) {
    const selected = String(value || '').trim();
    if (!selected) return { channel_id: null, channel: null };
    if (selected.startsWith('id:')) {
      const parsedId = Number(selected.slice(3));
      return Number.isFinite(parsedId) && parsedId > 0
        ? { channel_id: parsedId, channel: null }
        : { channel_id: null, channel: null };
    }
    if (selected.startsWith('legacy:')) {
      const legacyValue = selected.slice('legacy:'.length).trim();
      return { channel_id: null, channel: legacyValue || null };
    }
    return { channel_id: null, channel: null };
  }

  async function load() {
    const [data, options] = await Promise.all([
      fetchPayouts(),
      fetchPayoutChannelOptions(),
    ]);
    const payoutRows = Array.isArray(data) ? data : [];
    const setupChannels = Array.isArray(options?.channels) ? options.channels : [];
    const legacyFromApi = Array.isArray(options?.legacy_channels) ? options.legacy_channels : [];
    setRows(payoutRows);
    setChannelOptions(setupChannels);

    const legacySet = new Set(legacyFromApi.map((value) => String(value || '').trim()).filter(Boolean));
    for (const row of payoutRows) {
      const label = String(row?.channel || '').trim();
      if (!label) continue;
      if (row?.channel_id) continue;
      if (setupChannels.some((channel) => String(channel?.name || '').trim().toLowerCase() === label.toLowerCase())) continue;
      if (setupChannels.some((channel) => String(channel?.code || '').trim().toLowerCase() === label.toLowerCase())) continue;
      legacySet.add(label);
    }
    setLegacyChannels(Array.from(legacySet).sort((a, b) => a.localeCompare(b)));

    setForm((prev) => {
      if (prev.channel_choice) return prev;
      if (!setupChannels.length) return prev;
      return { ...prev, channel_choice: `id:${setupChannels[0].id}` };
    });
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || 'Failed to load payouts.'));
  }, []);

  function resetForm() {
    setEditingId(null);
    setForm({
      ...EMPTY_FORM,
      channel_choice: channelOptions.length ? `id:${channelOptions[0].id}` : '',
    });
  }

  async function submit(e) {
    e.preventDefault();
    setError('');
    try {
      const payload = {
        ...form,
        ...parseChannelChoice(form.channel_choice),
        gross_amount: Number(form.gross_amount || 0),
        commission_amount: Number(form.commission_amount || 0),
        net_amount: Number(form.net_amount || 0),
        auto_post_accounting: !!form.auto_post_accounting,
      };
      delete payload.channel_choice;
      if (!payload.channel_id && !payload.channel) {
        setError('Select a booking channel.');
        return;
      }

      if (editingId) {
        await updatePayout(editingId, payload);
        setNotice(payload.auto_post_accounting ? 'Payout updated with accounting adjustments.' : 'Payout updated.');
      } else {
        await createPayout(payload);
        setNotice(payload.auto_post_accounting ? 'Payout saved and linked to accounting.' : 'Payout saved.');
      }

      resetForm();
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save payout.');
    }
  }

  function isSubmittable() {
    const gross = Number(form.gross_amount || 0);
    const net = Number(form.net_amount || 0);
    return !!form.channel_choice && gross >= 0 && net >= 0;
  }

  function editRow(row) {
    const choice = row.channel_id
      ? `id:${row.channel_id}`
      : (row.channel ? `legacy:${row.channel}` : (channelOptions.length ? `id:${channelOptions[0].id}` : ''));
    setEditingId(row.id);
    setForm({
      channel_choice: choice,
      booking_ref: row.booking_ref || '',
      gross_amount: row.gross_amount ?? '',
      commission_amount: row.commission_amount ?? '',
      net_amount: row.net_amount ?? '',
      payment_method: 'ota_payout',
      auto_post_accounting: false,
      expected_payout_date: row.expected_payout_date || '',
      actual_payout_date: row.actual_payout_date || '',
      status: row.status || 'pending',
      notes: row.notes || '',
    });
  }

  async function settle(row) {
    setError('');
    try {
      await settlePayout(row.id, {
        actual_payout_date: todayISO(),
        payment_method: 'bank_transfer',
        auto_post_accounting: false,
      });
      setNotice(`Payout ${row.id} marked as settled.`);
      await load();
    } catch (err) {
      setError(err.message || 'Failed to settle payout.');
    }
  }

  return (
    <div>
      <section className="section">
        <h1>Channel Payouts</h1>
        <p className="muted">Track OTA gross, commission, and settlements with optional accounting links to keep postings intentional.</p>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <div className="grid">
        <section className="section">
          <h2>{editingId ? `Edit Payout #${editingId}` : 'Add Payout'}</h2>
          <form onSubmit={submit} onKeyDown={(event) => shouldPreventEnterSubmit(event, isSubmittable)}>
            <div className="form-grid">
              <label>Channel
                <select value={form.channel_choice} onChange={e => setForm(f => ({ ...f, channel_choice: e.target.value }))}>
                  <option value="">Select channel</option>
                  {channelOptions.map((row) => (
                    <option key={`channel-${row.id}`} value={`id:${row.id}`}>
                      {row.name}{row.code ? ` (${row.code})` : ''}
                    </option>
                  ))}
                  {legacyChannels.map((label) => (
                    <option key={`legacy-${label}`} value={`legacy:${label}`}>Legacy: {label}</option>
                  ))}
                </select>
              </label>
              <label>Booking Ref<input value={form.booking_ref} onChange={e => setForm(f => ({ ...f, booking_ref: e.target.value }))} /></label>
              <label>Gross<input type="number" step="0.01" inputMode="decimal" min="0" value={form.gross_amount} onChange={e => setForm(f => ({ ...f, gross_amount: e.target.value }))} /></label>
              <label>Commission<input type="number" step="0.01" inputMode="decimal" min="0" value={form.commission_amount} onChange={e => setForm(f => ({ ...f, commission_amount: e.target.value }))} /></label>
              <label>Net<input type="number" step="0.01" inputMode="decimal" min="0" value={form.net_amount} onChange={e => setForm(f => ({ ...f, net_amount: e.target.value }))} /></label>
              <label>Payment Method
                <select value={form.payment_method} onChange={e => setForm(f => ({ ...f, payment_method: e.target.value }))}>
                  {PAYMENT_METHODS.map(row => <option key={row} value={row}>{row}</option>)}
                </select>
              </label>
              <label>Auto Post Accounting
                <select value={String(form.auto_post_accounting)} onChange={e => setForm(f => ({ ...f, auto_post_accounting: e.target.value === 'true' }))}>
                  <option value="false">false</option>
                  <option value="true">true</option>
                </select>
              </label>
              <label>Expected Payout<input type="date" value={form.expected_payout_date} onChange={e => setForm(f => ({ ...f, expected_payout_date: e.target.value }))} /></label>
              <label>Actual Payout<input type="date" value={form.actual_payout_date} onChange={e => setForm(f => ({ ...f, actual_payout_date: e.target.value }))} /></label>
              <label>Status
                <select value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value }))}>
                  <option value="pending">pending</option>
                  <option value="scheduled">scheduled</option>
                  <option value="paid">paid</option>
                  <option value="cancelled">cancelled</option>
                </select>
              </label>
            </div>
            <label>Notes<textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} /></label>
            <div className="row wrap">
              {(can('cashflow.money_in') || can('cashflow.money_out') || can('reports.view')) && (
                <button type="submit" disabled={!isSubmittable()}>{editingId ? 'Update Payout' : 'Save Payout'}</button>
              )}
              {editingId && <button type="button" className="secondary" onClick={resetForm}>Cancel Edit</button>}
            </div>
          </form>
        </section>

        <section className="section">
          <h2>Payout List</h2>
          <table className="table">
            <thead><tr><th>Channel</th><th>Booking Ref</th><th>Gross</th><th>Commission</th><th>Net</th><th>Status</th><th>Accounting</th><th></th></tr></thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.id}>
                  <td>{r.channel_display_name || r.channel || '-'}</td>
                  <td>{r.booking_ref || '-'}</td>
                  <td>{money(r.gross_amount)}</td>
                  <td>{money(r.commission_amount)}</td>
                  <td>{money(r.net_amount)}</td>
                  <td>{r.status}</td>
                  <td className="small">
                    {(r.accounting_links || []).map((link) => (
                      <div key={link.id}>{link.link_type}: REC-{link.record_id} ({money(link.record_amount)})</div>
                    ))}
                    {!(r.accounting_links || []).length && <span className="muted">none</span>}
                  </td>
                  <td className="row wrap">
                    {(can('cashflow.money_in') || can('cashflow.money_out') || can('reports.view')) && (
                      <button className="secondary" type="button" onClick={() => editRow(r)}>Edit</button>
                    )}
                    {(can('cashflow.money_in') || can('cashflow.money_out') || can('reports.view')) && r.status !== 'paid' && (
                      <button className="secondary" type="button" onClick={() => settle(r)}>Settle</button>
                    )}
                  </td>
                </tr>
              ))}
              {!rows.length && <tr><td colSpan="8" className="muted">No payouts yet.</td></tr>}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}
