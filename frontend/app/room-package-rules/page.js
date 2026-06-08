'use client';

import { useEffect, useState } from 'react';
import {
  createRoomPackageRule,
  deleteRoomPackageRule,
  fetchRatePlansEntity,
  fetchRoomPackageRules,
  fetchRoomTypes,
  updateRoomPackageRule,
} from '../../lib/api';
import { shouldPreventEnterSubmit } from '../../lib/formBehavior';
import { useConfirmAction } from '../../components/ConfirmActionProvider';

const EMPTY_FORM = {
  name: '',
  room_type_id: '',
  rate_plan_id: '',
  included_breakfast: 0,
  included_pax: 2,
  extra_pax_rate: 0,
  is_active: true,
  notes: '',
};

export default function RoomPackageRulesPage() {
  const confirmAction = useConfirmAction();
  const [roomTypes, setRoomTypes] = useState([]);
  const [ratePlans, setRatePlans] = useState([]);
  const [rows, setRows] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function load() {
    const [rulesData, roomTypeData, ratePlanData] = await Promise.all([
      fetchRoomPackageRules(false),
      fetchRoomTypes(true),
      fetchRatePlansEntity(true),
    ]);
    setRows(Array.isArray(rulesData) ? rulesData : []);
    setRoomTypes(Array.isArray(roomTypeData) ? roomTypeData : []);
    setRatePlans(Array.isArray(ratePlanData) ? ratePlanData : []);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || 'Failed to load package rules.'));
  }, []);

  async function submit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      const payload = {
        ...form,
        room_type_id: form.room_type_id ? Number(form.room_type_id) : null,
        rate_plan_id: form.rate_plan_id ? Number(form.rate_plan_id) : null,
        included_breakfast: Number(form.included_breakfast || 0),
        included_pax: Number(form.included_pax || 1),
        extra_pax_rate: Number(form.extra_pax_rate || 0),
      };
      if (editingId) {
        await updateRoomPackageRule(editingId, payload);
        setNotice('Package rule updated.');
      } else {
        await createRoomPackageRule(payload);
        setNotice('Package rule created.');
      }
      setEditingId(null);
      setForm({ ...EMPTY_FORM });
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save package rule.');
    }
  }

  function editRow(row) {
    setEditingId(row.id);
    setForm({
      name: row.name || '',
      room_type_id: row.room_type_id ? String(row.room_type_id) : '',
      rate_plan_id: row.rate_plan_id ? String(row.rate_plan_id) : '',
      included_breakfast: row.included_breakfast ?? 0,
      included_pax: row.included_pax ?? 2,
      extra_pax_rate: row.extra_pax_rate ?? 0,
      is_active: !!row.is_active,
      notes: row.notes || '',
    });
  }

  async function removeRow(row) {
    if (!await confirmAction({ title: `Delete package rule ${row.name}?`, description: 'This removes the default inclusions from future booking guidance.' })) return;
    setError('');
    try {
      await deleteRoomPackageRule(row.id);
      setNotice('Package rule deleted.');
      if (editingId === row.id) {
        setEditingId(null);
        setForm({ ...EMPTY_FORM });
      }
      await load();
    } catch (err) {
      setError(err.message || 'Failed to delete package rule.');
    }
  }

  function isSubmittable() {
    return !!String(form.name || '').trim();
  }

  return (
    <div className="stack">
      <section className="section">
        <h1>Room Package Rules</h1>
        <p className="muted">Set default inclusions per room type/rate plan for booking guidance.</p>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <div className="grid">
        <section className="section">
          <h2>{editingId ? `Edit Rule #${editingId}` : 'New Package Rule'}</h2>
          <form onSubmit={submit} className="stack" onKeyDown={(event) => shouldPreventEnterSubmit(event, isSubmittable)}>
            <div className="form-grid">
              <label>Name<input required value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} /></label>
              <label>Room Type
                <select value={form.room_type_id} onChange={(e) => setForm((f) => ({ ...f, room_type_id: e.target.value }))}>
                  <option value="">All</option>
                  {roomTypes.map((row) => <option key={row.id} value={row.id}>{row.code} · {row.name}</option>)}
                </select>
              </label>
              <label>Rate Plan
                <select value={form.rate_plan_id} onChange={(e) => setForm((f) => ({ ...f, rate_plan_id: e.target.value }))}>
                  <option value="">All</option>
                  {ratePlans.map((row) => <option key={row.id} value={row.id}>{row.code} · {row.name}</option>)}
                </select>
              </label>
              <label>Included Breakfast<input type="number" min="0" step="1" value={form.included_breakfast} onChange={(e) => setForm((f) => ({ ...f, included_breakfast: e.target.value }))} /></label>
              <label>Included Pax<input type="number" min="1" step="1" value={form.included_pax} onChange={(e) => setForm((f) => ({ ...f, included_pax: e.target.value }))} /></label>
              <label>Extra Pax Rate<input type="number" min="0" step="0.01" value={form.extra_pax_rate} onChange={(e) => setForm((f) => ({ ...f, extra_pax_rate: e.target.value }))} /></label>
              <label>Active
                <select value={String(form.is_active)} onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.value === 'true' }))}>
                  <option value="true">Active</option>
                  <option value="false">Inactive</option>
                </select>
              </label>
            </div>
            <label>Notes<textarea value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} /></label>
            <div className="row wrap">
              <button type="submit">{editingId ? 'Update Package Rule' : 'Create Package Rule'}</button>
              {editingId && <button type="button" className="secondary" onClick={() => { setEditingId(null); setForm({ ...EMPTY_FORM }); }}>Cancel</button>}
            </div>
          </form>
        </section>

        <section className="section">
          <h2>Package Rule List</h2>
          <table className="table">
            <thead><tr><th>Name</th><th>Room Type</th><th>Rate Plan</th><th>Inclusions</th><th></th></tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.name}</td>
                  <td>{row.room_type_name || 'All'}</td>
                  <td>{row.rate_plan_name || 'All'}</td>
                  <td>Breakfast {row.included_breakfast}, Pax {row.included_pax}</td>
                  <td className="row wrap">
                    <button type="button" className="secondary" onClick={() => editRow(row)}>Edit</button>
                    <button type="button" className="secondary" onClick={() => removeRow(row)}>Delete</button>
                  </td>
                </tr>
              ))}
              {!rows.length && <tr><td colSpan="5" className="muted">No package rules yet.</td></tr>}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}
