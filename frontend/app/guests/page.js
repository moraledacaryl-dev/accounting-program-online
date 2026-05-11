'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import {
  createGuest,
  fetchGuests,
  mergeGuests,
  searchGuests,
  updateGuest,
} from '../../lib/api';
import { shouldPreventEnterSubmit } from '../../lib/formBehavior';

const EMPTY_FORM = {
  first_name: '',
  last_name: '',
  full_name: '',
  phone: '',
  email: '',
  address: '',
  city: '',
  nationality: '',
  birthday: '',
  company: '',
  vip_flag: false,
  status_tags: '',
  notes: '',
  tags_text: '',
  preferences_text: '',
  is_active: true,
};

function parseTags(text) {
  return String(text || '')
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean);
}

function parsePreferences(text) {
  const lines = String(text || '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
  const out = [];
  for (const line of lines) {
    const [key, ...rest] = line.split(':');
    const k = String(key || '').trim();
    if (!k) continue;
    out.push({ preference_key: k, preference_value: rest.join(':').trim() || null });
  }
  return out;
}

function preferenceText(preferences = []) {
  return (preferences || [])
    .map((pref) => `${pref.preference_key || ''}: ${pref.preference_value || ''}`.trim())
    .join('\n');
}

function mergeLabel(row) {
  const stay = Number(row.stay_count || 0);
  const booking = Number(row.booking_count || 0);
  const vip = row.vip_flag ? 'VIP' : 'Standard';
  return `${vip} · ${booking} bookings · ${stay} stays`;
}

function php(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function GuestsPage() {
  const [rows, setRows] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [query, setQuery] = useState('');
  const [vipOnly, setVipOnly] = useState(false);
  const [activeOnly, setActiveOnly] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const [mergeForm, setMergeForm] = useState({
    source_guest_id: '',
    target_guest_id: '',
    reason: '',
  });
  const [mergeSourceOptions, setMergeSourceOptions] = useState([]);
  const [mergeTargetOptions, setMergeTargetOptions] = useState([]);

  async function load() {
    const data = await fetchGuests({
      q: query || undefined,
      vip_only: vipOnly,
      active_only: activeOnly,
      limit: 500,
    });
    setRows(Array.isArray(data) ? data : []);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || 'Failed to load guests.'));
  }, [query, vipOnly, activeOnly]);

  function formPayload() {
    return {
      first_name: form.first_name || null,
      last_name: form.last_name || null,
      full_name: form.full_name || null,
      phone: form.phone || null,
      email: form.email || null,
      address: form.address || null,
      city: form.city || null,
      nationality: form.nationality || null,
      birthday: form.birthday || null,
      company: form.company || null,
      vip_flag: !!form.vip_flag,
      status_tags: form.status_tags || null,
      notes: form.notes || null,
      tags: parseTags(form.tags_text),
      preferences: parsePreferences(form.preferences_text),
      is_active: !!form.is_active,
    };
  }

  async function submit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      const payload = formPayload();
      if (editingId) {
        await updateGuest(editingId, payload);
        setNotice('Guest updated.');
      } else {
        await createGuest(payload);
        setNotice('Guest created.');
      }
      setEditingId(null);
      setForm({ ...EMPTY_FORM });
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save guest.');
    }
  }

  function editRow(row) {
    setEditingId(row.id);
    setForm({
      first_name: row.first_name || '',
      last_name: row.last_name || '',
      full_name: row.full_name || '',
      phone: row.phone || '',
      email: row.email || '',
      address: row.address || '',
      city: row.city || '',
      nationality: row.nationality || '',
      birthday: row.birthday || '',
      company: row.company || '',
      vip_flag: !!row.vip_flag,
      status_tags: row.status_tags || '',
      notes: row.notes || '',
      tags_text: (row.tags || []).join(', '),
      preferences_text: preferenceText(row.preferences || []),
      is_active: !!row.is_active,
    });
  }

  async function deactivateRow(row) {
    if (!window.confirm(`Set guest ${row.full_name} as inactive?`)) return;
    setError('');
    try {
      await updateGuest(row.id, { is_active: false });
      setNotice('Guest set to inactive.');
      if (editingId === row.id) {
        setEditingId(null);
        setForm({ ...EMPTY_FORM });
      }
      await load();
    } catch (err) {
      setError(err.message || 'Failed to deactivate guest.');
    }
  }

  async function lookupMergeSource(text) {
    const q = String(text || '').trim();
    if (!q || q.length < 2) {
      setMergeSourceOptions([]);
      return;
    }
    try {
      const data = await searchGuests(q, 15);
      setMergeSourceOptions(Array.isArray(data) ? data : []);
    } catch {
      setMergeSourceOptions([]);
    }
  }

  async function lookupMergeTarget(text) {
    const q = String(text || '').trim();
    if (!q || q.length < 2) {
      setMergeTargetOptions([]);
      return;
    }
    try {
      const data = await searchGuests(q, 15);
      setMergeTargetOptions(Array.isArray(data) ? data : []);
    } catch {
      setMergeTargetOptions([]);
    }
  }

  async function submitMerge(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      if (!mergeForm.source_guest_id || !mergeForm.target_guest_id) {
        setError('Select both source and target guests for merge.');
        return;
      }
      await mergeGuests({
        source_guest_id: Number(mergeForm.source_guest_id),
        target_guest_id: Number(mergeForm.target_guest_id),
        reason: mergeForm.reason || null,
      });
      setNotice('Guest merge completed. Source guest is now inactive.');
      setMergeForm({ source_guest_id: '', target_guest_id: '', reason: '' });
      setMergeSourceOptions([]);
      setMergeTargetOptions([]);
      await load();
    } catch (err) {
      setError(err.message || 'Failed to merge guests.');
    }
  }

  function isGuestSubmittable() {
    return !!(
      String(form.full_name || '').trim()
      || (String(form.first_name || '').trim() && String(form.last_name || '').trim())
    );
  }

  function isMergeSubmittable() {
    return !!(
      Number(mergeForm.source_guest_id || 0) > 0
      && Number(mergeForm.target_guest_id || 0) > 0
      && Number(mergeForm.source_guest_id || 0) !== Number(mergeForm.target_guest_id || 0)
    );
  }

  return (
    <div className="stack">
      <section className="section">
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-end' }}>
          <div>
            <h1>Guests</h1>
            <p className="muted">Guest CRM with VIP/returning visibility, profile history, and merge support.</p>
          </div>
          <div className="row wrap">
            <input
              data-enter-context="search"
              type="search"
              placeholder="Search name, phone, email"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <label style={{ minWidth: 120 }}>
              VIP Only
              <select value={String(vipOnly)} onChange={(e) => setVipOnly(e.target.value === 'true')}>
                <option value="false">No</option>
                <option value="true">Yes</option>
              </select>
            </label>
            <label style={{ minWidth: 120 }}>
              Active
              <select value={String(activeOnly)} onChange={(e) => setActiveOnly(e.target.value === 'true')}>
                <option value="true">Active</option>
                <option value="false">All</option>
              </select>
            </label>
          </div>
        </div>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <div className="grid">
        <section className="section">
          <h2>{editingId ? `Edit Guest #${editingId}` : 'New Guest'}</h2>
          <form onSubmit={submit} className="stack" onKeyDown={(event) => shouldPreventEnterSubmit(event, isGuestSubmittable)}>
            <div className="form-grid">
              <label>First Name<input value={form.first_name} onChange={(e) => setForm((f) => ({ ...f, first_name: e.target.value }))} /></label>
              <label>Last Name<input value={form.last_name} onChange={(e) => setForm((f) => ({ ...f, last_name: e.target.value }))} /></label>
              <label>Full Name Override<input value={form.full_name} onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))} placeholder="Optional" /></label>
              <label>Phone<input value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} /></label>
              <label>Email<input type="email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} /></label>
              <label>Company<input value={form.company} onChange={(e) => setForm((f) => ({ ...f, company: e.target.value }))} /></label>
              <label>City<input value={form.city} onChange={(e) => setForm((f) => ({ ...f, city: e.target.value }))} /></label>
              <label>Nationality<input value={form.nationality} onChange={(e) => setForm((f) => ({ ...f, nationality: e.target.value }))} /></label>
              <label>Birthday<input type="date" value={form.birthday} onChange={(e) => setForm((f) => ({ ...f, birthday: e.target.value }))} /></label>
              <label>VIP
                <select value={String(form.vip_flag)} onChange={(e) => setForm((f) => ({ ...f, vip_flag: e.target.value === 'true' }))}>
                  <option value="false">No</option>
                  <option value="true">Yes</option>
                </select>
              </label>
              <label>Status Tags<input value={form.status_tags} onChange={(e) => setForm((f) => ({ ...f, status_tags: e.target.value }))} placeholder="returning, corporate" /></label>
              <label>Active
                <select value={String(form.is_active)} onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.value === 'true' }))}>
                  <option value="true">Active</option>
                  <option value="false">Inactive</option>
                </select>
              </label>
            </div>
            <label>Address<textarea value={form.address} onChange={(e) => setForm((f) => ({ ...f, address: e.target.value }))} /></label>
            <label>Tags (comma separated)<input value={form.tags_text} onChange={(e) => setForm((f) => ({ ...f, tags_text: e.target.value }))} placeholder="vip, wedding, corporate" /></label>
            <label>Preferences (one per line: key:value)
              <textarea value={form.preferences_text} onChange={(e) => setForm((f) => ({ ...f, preferences_text: e.target.value }))} placeholder={"bed: king\nview: sea\ndiet: vegan"} />
            </label>
            <label>Notes<textarea value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} /></label>
            <div className="row wrap">
              <button type="submit">{editingId ? 'Update Guest' : 'Create Guest'}</button>
              {editingId && (
                <button type="button" className="secondary" onClick={() => { setEditingId(null); setForm({ ...EMPTY_FORM }); }}>
                  Cancel
                </button>
              )}
            </div>
          </form>
        </section>

        <section className="section">
          <h2>Merge Guests</h2>
          <p className="muted small">Merge duplicate guest records into a single target profile.</p>
          <form onSubmit={submitMerge} className="stack" style={{ marginTop: 10 }} onKeyDown={(event) => shouldPreventEnterSubmit(event, isMergeSubmittable)}>
            <label>Search Source Guest
              <input
                data-enter-context="search"
                placeholder="Type name/phone/email"
                onChange={(e) => lookupMergeSource(e.target.value)}
              />
            </label>
            <label>Source Guest
              <select value={mergeForm.source_guest_id} onChange={(e) => setMergeForm((f) => ({ ...f, source_guest_id: e.target.value }))}>
                <option value="">Select source</option>
                {mergeSourceOptions.map((row) => (
                  <option key={row.id} value={row.id}>{row.full_name} ({row.phone || '-'})</option>
                ))}
              </select>
            </label>

            <label>Search Target Guest
              <input
                data-enter-context="search"
                placeholder="Type name/phone/email"
                onChange={(e) => lookupMergeTarget(e.target.value)}
              />
            </label>
            <label>Target Guest
              <select value={mergeForm.target_guest_id} onChange={(e) => setMergeForm((f) => ({ ...f, target_guest_id: e.target.value }))}>
                <option value="">Select target</option>
                {mergeTargetOptions.map((row) => (
                  <option key={row.id} value={row.id}>{row.full_name} ({row.phone || '-'})</option>
                ))}
              </select>
            </label>
            <label>Reason<textarea value={mergeForm.reason} onChange={(e) => setMergeForm((f) => ({ ...f, reason: e.target.value }))} /></label>
            <button type="submit">Merge Guests</button>
          </form>

          <div style={{ marginTop: 14 }}>
            <h3>Quick Summary</h3>
            <div className="small muted">Total guests: {rows.length}</div>
            <div className="small muted">VIP guests: {rows.filter((row) => row.vip_flag).length}</div>
            <div className="small muted">Returning guests: {rows.filter((row) => Number(row.booking_count || 0) > 0).length}</div>
          </div>
        </section>
      </div>

      <section className="section">
        <h2>Guest List</h2>
        <table className="table">
          <thead>
            <tr>
              <th>Guest</th>
              <th>Contact</th>
              <th>Profile</th>
              <th>Outstanding</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>
                  <div><strong>{row.full_name}</strong> {row.vip_flag ? <span className="badge">VIP</span> : null}</div>
                  <div className="small muted">{mergeLabel(row)}</div>
                </td>
                <td>{row.phone || '-'}<br />{row.email || '-'}</td>
                <td>
                  <div className="small">Last stay: {row.last_stay_date || '-'}</div>
                  <div className="small muted">Tags: {(row.tags || []).join(', ') || '-'}</div>
                </td>
                <td>{php(row.outstanding_balance || 0)}</td>
                <td className="row wrap">
                  <Link className="button-link secondary-link" href={`/guests/${row.id}`}>Profile</Link>
                  <button type="button" className="secondary" onClick={() => editRow(row)}>Edit</button>
                  {!!row.is_active && <button type="button" className="secondary" onClick={() => deactivateRow(row)}>Deactivate</button>}
                </td>
              </tr>
            ))}
            {!rows.length && <tr><td colSpan="5" className="muted">No guests found.</td></tr>}
          </tbody>
        </table>
      </section>

      <section className="section">
        <h2>Duplicate Hint</h2>
        <p className="small muted">If you see repeated phone or email values, use the merge panel above. This keeps booking and folio history intact on one profile.</p>
      </section>
    </div>
  );
}
