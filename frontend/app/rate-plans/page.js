'use client';

import { useEffect, useState } from 'react';
import {
  createRatePlanEntity,
  deleteRatePlanEntity,
  fetchNextCodePreview,
  fetchRatePlansEntity,
  fetchRoomTypes,
  updateRatePlanEntity,
} from '../../lib/api';
import { shouldPreventEnterSubmit } from '../../lib/formBehavior';

const EMPTY_FORM = {
  code: '',
  name: '',
  room_type_id: '',
  base_rate: 0,
  breakfast_included: 0,
  pax_included: 2,
  is_active: true,
  notes: '',
};

export default function RatePlansPage() {
  const [roomTypes, setRoomTypes] = useState([]);
  const [rows, setRows] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function load() {
    const [data, typeData] = await Promise.all([fetchRatePlansEntity(false), fetchRoomTypes(true)]);
    setRows(Array.isArray(data) ? data : []);
    setRoomTypes(Array.isArray(typeData) ? typeData : []);
  }

  async function hydrateNewCode() {
    try {
      const preview = await fetchNextCodePreview('rate_plan');
      setForm((prev) => ({ ...prev, code: preview?.code || prev.code || '' }));
    } catch {
      // Keep manual fallback.
    }
  }

  useEffect(() => {
    Promise.all([load(), hydrateNewCode()]).catch((e) => setError(e.message || 'Failed to load rate plans.'));
  }, []);

  async function submit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      const payload = {
        ...form,
        room_type_id: form.room_type_id ? Number(form.room_type_id) : null,
        base_rate: Number(form.base_rate || 0),
        breakfast_included: Number(form.breakfast_included || 0),
        pax_included: Number(form.pax_included || 1),
      };
      if (editingId) {
        await updateRatePlanEntity(editingId, payload);
        setNotice('Rate plan updated.');
      } else {
        await createRatePlanEntity(payload);
        setNotice('Rate plan created.');
      }
      setEditingId(null);
      setForm({ ...EMPTY_FORM });
      await hydrateNewCode();
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save rate plan.');
    }
  }

  function editRow(row) {
    setEditingId(row.id);
    setForm({
      code: row.code || '',
      name: row.name || '',
      room_type_id: row.room_type_id ? String(row.room_type_id) : '',
      base_rate: row.base_rate ?? 0,
      breakfast_included: row.breakfast_included ?? 0,
      pax_included: row.pax_included ?? 2,
      is_active: !!row.is_active,
      notes: row.notes || '',
    });
  }

  async function removeRow(row) {
    if (!window.confirm(`Delete rate plan ${row.code}?`)) return;
    setError('');
    try {
      await deleteRatePlanEntity(row.id);
      setNotice('Rate plan deleted.');
      if (editingId === row.id) {
        setEditingId(null);
        setForm({ ...EMPTY_FORM });
      }
      await load();
    } catch (err) {
      setError(err.message || 'Failed to delete rate plan.');
    }
  }

  function isSubmittable() {
    return !!String(form.name || '').trim();
  }

  return (
    <div className="stack">
      <section className="section">
        <h1>Rate Plans</h1>
        <p className="muted">Maintain room pricing and included breakfast/pax defaults.</p>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <div className="grid">
        <section className="section">
          <h2>{editingId ? `Edit Rate Plan #${editingId}` : 'New Rate Plan'}</h2>
          <form onSubmit={submit} className="stack" onKeyDown={(event) => shouldPreventEnterSubmit(event, isSubmittable)}>
            <div className="form-grid">
              <label>Code<input value={form.code} onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))} placeholder="Auto-generated if blank" /></label>
              <label>Name<input required value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} /></label>
              <label>Room Type
                <select value={form.room_type_id} onChange={(e) => setForm((f) => ({ ...f, room_type_id: e.target.value }))}>
                  <option value="">All room types</option>
                  {roomTypes.map((row) => <option key={row.id} value={row.id}>{row.code} · {row.name}</option>)}
                </select>
              </label>
              <label>Base Rate<input type="number" min="0" step="0.01" value={form.base_rate} onChange={(e) => setForm((f) => ({ ...f, base_rate: e.target.value }))} /></label>
              <label>Breakfast Included<input type="number" min="0" step="1" value={form.breakfast_included} onChange={(e) => setForm((f) => ({ ...f, breakfast_included: e.target.value }))} /></label>
              <label>Pax Included<input type="number" min="1" step="1" value={form.pax_included} onChange={(e) => setForm((f) => ({ ...f, pax_included: e.target.value }))} /></label>
              <label>Active
                <select value={String(form.is_active)} onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.value === 'true' }))}>
                  <option value="true">Active</option>
                  <option value="false">Inactive</option>
                </select>
              </label>
            </div>
            <label>Notes<textarea value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} /></label>
            <div className="row wrap">
              <button type="submit">{editingId ? 'Update Rate Plan' : 'Create Rate Plan'}</button>
              {editingId && <button type="button" className="secondary" onClick={() => { setEditingId(null); setForm({ ...EMPTY_FORM }); hydrateNewCode(); }}>Cancel</button>}
            </div>
          </form>
        </section>

        <section className="section">
          <h2>Rate Plan List</h2>
          <table className="table">
            <thead><tr><th>Code</th><th>Name</th><th>Type</th><th>Rate</th><th></th></tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.code}</td>
                  <td>{row.name}</td>
                  <td>{row.room_type_name || 'All'}</td>
                  <td>{Number(row.base_rate || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                  <td className="row wrap">
                    <button type="button" className="secondary" onClick={() => editRow(row)}>Edit</button>
                    <button type="button" className="secondary" onClick={() => removeRow(row)}>Delete</button>
                  </td>
                </tr>
              ))}
              {!rows.length && <tr><td colSpan="5" className="muted">No rate plans yet.</td></tr>}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}
