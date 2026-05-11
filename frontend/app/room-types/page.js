'use client';

import { useEffect, useState } from 'react';
import { createRoomType, deleteRoomType, fetchNextCodePreview, fetchRoomTypes, updateRoomType } from '../../lib/api';
import { shouldPreventEnterSubmit } from '../../lib/formBehavior';

const EMPTY_FORM = {
  code: '',
  name: '',
  description: '',
  base_capacity: 2,
  max_capacity: 2,
  is_active: true,
  notes: '',
};

export default function RoomTypesPage() {
  const [rows, setRows] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function load() {
    const data = await fetchRoomTypes(false);
    setRows(Array.isArray(data) ? data : []);
  }

  async function hydrateNewCode() {
    try {
      const preview = await fetchNextCodePreview('room_type');
      setForm((prev) => ({ ...prev, code: preview?.code || prev.code || '' }));
    } catch {
      // Keep manual fallback when preview is unavailable.
    }
  }

  useEffect(() => {
    Promise.all([load(), hydrateNewCode()]).catch((e) => setError(e.message || 'Failed to load room types.'));
  }, []);

  async function submit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      const payload = {
        ...form,
        base_capacity: Number(form.base_capacity || 1),
        max_capacity: Number(form.max_capacity || 1),
      };
      if (editingId) {
        await updateRoomType(editingId, payload);
        setNotice('Room type updated.');
      } else {
        await createRoomType(payload);
        setNotice('Room type created.');
      }
      setEditingId(null);
      setForm({ ...EMPTY_FORM });
      await hydrateNewCode();
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save room type.');
    }
  }

  function editRow(row) {
    setEditingId(row.id);
    setForm({
      code: row.code || '',
      name: row.name || '',
      description: row.description || '',
      base_capacity: row.base_capacity ?? 2,
      max_capacity: row.max_capacity ?? 2,
      is_active: !!row.is_active,
      notes: row.notes || '',
    });
  }

  async function removeRow(row) {
    if (!window.confirm(`Delete room type ${row.code}?`)) return;
    setError('');
    try {
      await deleteRoomType(row.id);
      setNotice('Room type deleted.');
      if (editingId === row.id) {
        setEditingId(null);
        setForm({ ...EMPTY_FORM });
      }
      await load();
    } catch (err) {
      setError(err.message || 'Failed to delete room type.');
    }
  }

  function isSubmittable() {
    return !!String(form.name || '').trim();
  }

  return (
    <div className="stack">
      <section className="section">
        <h1>Room Types</h1>
        <p className="muted">Define room type identities used by rooms, rates, and bookings.</p>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <div className="grid">
        <section className="section">
          <h2>{editingId ? `Edit Room Type #${editingId}` : 'New Room Type'}</h2>
          <form onSubmit={submit} className="stack" onKeyDown={(event) => shouldPreventEnterSubmit(event, isSubmittable)}>
            <div className="form-grid">
              <label>Code
                <input value={form.code} onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))} placeholder="Auto-generated if blank" />
              </label>
              <label>Name<input required value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} /></label>
              <label>Active
                <select value={String(form.is_active)} onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.value === 'true' }))}>
                  <option value="true">Active</option>
                  <option value="false">Inactive</option>
                </select>
              </label>
              <label>Base Capacity<input type="number" min="1" step="1" value={form.base_capacity} onChange={(e) => setForm((f) => ({ ...f, base_capacity: e.target.value }))} /></label>
              <label>Max Capacity<input type="number" min="1" step="1" value={form.max_capacity} onChange={(e) => setForm((f) => ({ ...f, max_capacity: e.target.value }))} /></label>
              <label>Description<input value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} /></label>
            </div>
            <label>Notes<textarea value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} /></label>
            <div className="row wrap">
              <button type="submit">{editingId ? 'Update Room Type' : 'Create Room Type'}</button>
              {editingId && (
                <button
                  type="button"
                  className="secondary"
                  onClick={() => {
                    setEditingId(null);
                    setForm({ ...EMPTY_FORM });
                    hydrateNewCode();
                  }}
                >
                  Cancel
                </button>
              )}
            </div>
          </form>
        </section>

        <section className="section">
          <h2>Room Type List</h2>
          <table className="table">
            <thead><tr><th>Code</th><th>Name</th><th>Capacity</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.code}</td>
                  <td>{row.name}</td>
                  <td>{row.base_capacity} / {row.max_capacity}</td>
                  <td>{row.is_active ? 'Active' : 'Inactive'}</td>
                  <td className="row wrap">
                    <button type="button" className="secondary" onClick={() => editRow(row)}>Edit</button>
                    <button type="button" className="secondary" onClick={() => removeRow(row)}>Delete</button>
                  </td>
                </tr>
              ))}
              {!rows.length && <tr><td colSpan="5" className="muted">No room types yet.</td></tr>}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}
