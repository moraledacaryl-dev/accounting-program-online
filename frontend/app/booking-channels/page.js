'use client';

import { useEffect, useState } from 'react';
import {
  createBookingChannel,
  deleteBookingChannel,
  fetchNextCodePreview,
  fetchBookingChannels,
  updateBookingChannel,
} from '../../lib/api';
import { shouldPreventEnterSubmit } from '../../lib/formBehavior';

const EMPTY_FORM = {
  code: '',
  name: '',
  channel_class: '',
  settlement_mode: '',
  default_commission_rate: 0,
  is_prepaid: false,
  is_active: true,
  notes: '',
};

export default function BookingChannelsPage() {
  const [rows, setRows] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function load() {
    const data = await fetchBookingChannels(false);
    setRows(Array.isArray(data) ? data : []);
  }

  async function hydrateNewCode() {
    try {
      const preview = await fetchNextCodePreview('booking_channel');
      setForm((prev) => ({ ...prev, code: preview?.code || prev.code || '' }));
    } catch {
      // Keep manual fallback.
    }
  }

  useEffect(() => {
    Promise.all([load(), hydrateNewCode()]).catch((e) => setError(e.message || 'Failed to load booking channels.'));
  }, []);

  async function submit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      const payload = {
        ...form,
        default_commission_rate: Number(form.default_commission_rate || 0),
      };
      if (editingId) {
        await updateBookingChannel(editingId, payload);
        setNotice('Booking channel updated.');
      } else {
        await createBookingChannel(payload);
        setNotice('Booking channel created.');
      }
      setEditingId(null);
      setForm({ ...EMPTY_FORM });
      await hydrateNewCode();
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save booking channel.');
    }
  }

  function editRow(row) {
    setEditingId(row.id);
    setForm({
      code: row.code || '',
      name: row.name || '',
      channel_class: row.channel_class || '',
      settlement_mode: row.settlement_mode || '',
      default_commission_rate: row.default_commission_rate ?? 0,
      is_prepaid: !!row.is_prepaid,
      is_active: !!row.is_active,
      notes: row.notes || '',
    });
  }

  async function removeRow(row) {
    if (!window.confirm(`Delete booking channel ${row.code}?`)) return;
    setError('');
    try {
      await deleteBookingChannel(row.id);
      setNotice('Booking channel deleted.');
      if (editingId === row.id) {
        setEditingId(null);
        setForm({ ...EMPTY_FORM });
      }
      await load();
    } catch (err) {
      setError(err.message || 'Failed to delete booking channel.');
    }
  }

  function isSubmittable() {
    return !!String(form.name || '').trim();
  }

  return (
    <div className="stack">
      <section className="section">
        <h1>Booking Channels</h1>
        <p className="muted">Manage direct and OTA channels linked to bookings and payout tracking.</p>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <div className="grid">
        <section className="section">
          <h2>{editingId ? `Edit Channel #${editingId}` : 'New Channel'}</h2>
          <form onSubmit={submit} className="stack" onKeyDown={(event) => shouldPreventEnterSubmit(event, isSubmittable)}>
            <div className="form-grid">
              <label>Code<input value={form.code} onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))} placeholder="Auto-generated if blank" /></label>
              <label>Name<input required value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} /></label>
              <label>Class<input value={form.channel_class} onChange={(e) => setForm((f) => ({ ...f, channel_class: e.target.value }))} placeholder="OTA, Direct, Corporate" /></label>
              <label>Settlement Mode<input value={form.settlement_mode} onChange={(e) => setForm((f) => ({ ...f, settlement_mode: e.target.value }))} placeholder="net payout, direct collect" /></label>
              <label>Default Commission %<input type="number" min="0" step="0.01" value={form.default_commission_rate} onChange={(e) => setForm((f) => ({ ...f, default_commission_rate: e.target.value }))} /></label>
              <label>Prepaid Channel
                <select value={String(form.is_prepaid)} onChange={(e) => setForm((f) => ({ ...f, is_prepaid: e.target.value === 'true' }))}>
                  <option value="false">No</option>
                  <option value="true">Yes (room charges prepaid)</option>
                </select>
              </label>
              <label>Active
                <select value={String(form.is_active)} onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.value === 'true' }))}>
                  <option value="true">Active</option>
                  <option value="false">Inactive</option>
                </select>
              </label>
            </div>
            <label>Notes<textarea value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} /></label>
            <div className="row wrap">
              <button type="submit">{editingId ? 'Update Channel' : 'Create Channel'}</button>
              {editingId && <button type="button" className="secondary" onClick={() => { setEditingId(null); setForm({ ...EMPTY_FORM }); hydrateNewCode(); }}>Cancel</button>}
            </div>
          </form>
        </section>

        <section className="section">
          <h2>Channel List</h2>
          <table className="table">
            <thead><tr><th>Code</th><th>Name</th><th>Class</th><th>Prepaid</th><th>Commission</th><th></th></tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.code}</td>
                  <td>{row.name}</td>
                  <td>{row.channel_class || '-'}</td>
                  <td>{row.is_prepaid ? 'Yes' : 'No'}</td>
                  <td>{Number(row.default_commission_rate || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%</td>
                  <td className="row wrap">
                    <button type="button" className="secondary" onClick={() => editRow(row)}>Edit</button>
                    <button type="button" className="secondary" onClick={() => removeRow(row)}>Delete</button>
                  </td>
                </tr>
              ))}
              {!rows.length && <tr><td colSpan="6" className="muted">No booking channels yet.</td></tr>}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}
