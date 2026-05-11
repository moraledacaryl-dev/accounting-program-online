'use client';

import { useEffect, useState } from 'react';
import {
  createRoomEntity,
  deleteRoomEntity,
  fetchNextCodePreview,
  fetchRoomsEntity,
  fetchRoomTypes,
  updateRoomEntity,
} from '../../lib/api';
import { shouldPreventEnterSubmit } from '../../lib/formBehavior';

const EMPTY_FORM = {
  room_no: '',
  name: '',
  room_type_id: '',
  floor_zone: '',
  view_name: '',
  status: 'available',
  is_active: true,
  notes: '',
};

export default function RoomsPage() {
  const [roomTypes, setRoomTypes] = useState([]);
  const [rows, setRows] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function load() {
    const [roomsData, roomTypeData] = await Promise.all([
      fetchRoomsEntity(false),
      fetchRoomTypes(true),
    ]);
    setRows(Array.isArray(roomsData) ? roomsData : []);
    setRoomTypes(Array.isArray(roomTypeData) ? roomTypeData : []);
  }

  async function hydrateNewCode() {
    try {
      const preview = await fetchNextCodePreview('room');
      setForm((prev) => ({ ...prev, room_no: preview?.code || prev.room_no || '' }));
    } catch {
      // Keep manual fallback.
    }
  }

  useEffect(() => {
    Promise.all([load(), hydrateNewCode()]).catch((e) => setError(e.message || 'Failed to load rooms.'));
  }, []);

  async function submit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      const payload = {
        ...form,
        room_type_id: form.room_type_id ? Number(form.room_type_id) : null,
      };
      if (editingId) {
        await updateRoomEntity(editingId, payload);
        setNotice('Room updated.');
      } else {
        await createRoomEntity(payload);
        setNotice('Room created.');
      }
      setEditingId(null);
      setForm({ ...EMPTY_FORM });
      await hydrateNewCode();
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save room.');
    }
  }

  function editRow(row) {
    setEditingId(row.id);
    setForm({
      room_no: row.room_no || '',
      name: row.name || '',
      room_type_id: row.room_type_id ? String(row.room_type_id) : '',
      floor_zone: row.floor_zone || '',
      view_name: row.view_name || '',
      status: row.status || 'available',
      is_active: !!row.is_active,
      notes: row.notes || '',
    });
  }

  async function removeRow(row) {
    if (!window.confirm(`Delete room ${row.room_no}?`)) return;
    setError('');
    try {
      await deleteRoomEntity(row.id);
      setNotice('Room deleted.');
      if (editingId === row.id) {
        setEditingId(null);
        setForm({ ...EMPTY_FORM });
      }
      await load();
    } catch (err) {
      setError(err.message || 'Failed to delete room.');
    }
  }

  function isSubmittable() {
    return !!(
      String(form.name || '').trim()
      && Number(form.room_type_id || 0) > 0
    );
  }

  return (
    <div className="stack">
      <section className="section">
        <h1>Rooms</h1>
        <p className="muted">Maintain individual rooms and link each room to a room type.</p>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <div className="grid">
        <section className="section">
          <h2>{editingId ? `Edit Room #${editingId}` : 'New Room'}</h2>
          <form onSubmit={submit} className="stack" onKeyDown={(event) => shouldPreventEnterSubmit(event, isSubmittable)}>
            <div className="form-grid">
              <label>Room No<input value={form.room_no} onChange={(e) => setForm((f) => ({ ...f, room_no: e.target.value }))} placeholder="Auto-generated if blank" /></label>
              <label>Name<input required value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} /></label>
              <label>Room Type
                <select required value={form.room_type_id} onChange={(e) => setForm((f) => ({ ...f, room_type_id: e.target.value }))}>
                  <option value="">Select</option>
                  {roomTypes.map((row) => <option key={row.id} value={row.id}>{row.code} · {row.name}</option>)}
                </select>
              </label>
              <label>Floor / Zone<input value={form.floor_zone} onChange={(e) => setForm((f) => ({ ...f, floor_zone: e.target.value }))} /></label>
              <label>View<input value={form.view_name} onChange={(e) => setForm((f) => ({ ...f, view_name: e.target.value }))} /></label>
              <label>Status
                <select value={form.status} onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}>
                  <option value="available">available</option>
                  <option value="occupied">occupied</option>
                  <option value="dirty">dirty</option>
                  <option value="maintenance">maintenance</option>
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
              <button type="submit">{editingId ? 'Update Room' : 'Create Room'}</button>
              {editingId && <button type="button" className="secondary" onClick={() => { setEditingId(null); setForm({ ...EMPTY_FORM }); hydrateNewCode(); }}>Cancel</button>}
            </div>
          </form>
        </section>

        <section className="section">
          <h2>Room List</h2>
          <table className="table">
            <thead><tr><th>Room</th><th>Type</th><th>Zone</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.room_no} · {row.name}</td>
                  <td>{row.room_type_name || '-'}</td>
                  <td>{row.floor_zone || '-'}</td>
                  <td>{row.status} {row.is_active ? '' : '(inactive)'}</td>
                  <td className="row wrap">
                    <button type="button" className="secondary" onClick={() => editRow(row)}>Edit</button>
                    <button type="button" className="secondary" onClick={() => removeRow(row)}>Delete</button>
                  </td>
                </tr>
              ))}
              {!rows.length && <tr><td colSpan="5" className="muted">No rooms yet.</td></tr>}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}
