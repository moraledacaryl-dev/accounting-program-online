'use client';

import { useEffect, useState } from 'react';
import {
  createSupplierEntity,
  deleteSupplierEntity,
  fetchNextCodePreview,
  fetchSuppliersEntity,
  updateSupplierEntity,
} from '../../lib/api';
import { shouldPreventEnterSubmit } from '../../lib/formBehavior';

const EMPTY_FORM = {
  code: '',
  name: '',
  supplier_type: '',
  category: '',
  contact_person: '',
  phone: '',
  email: '',
  address: '',
  tin: '',
  tax_id: '',
  payment_terms: '',
  is_active: true,
  notes: '',
};

export default function SuppliersPage() {
  const [rows, setRows] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function load(q = search) {
    const data = await fetchSuppliersEntity({ q, active_only: false });
    setRows(Array.isArray(data) ? data : []);
  }

  async function hydrateNewCode() {
    try {
      const preview = await fetchNextCodePreview('supplier');
      setForm((prev) => ({ ...prev, code: preview?.code || prev.code || '' }));
    } catch {
      // Keep manual fallback.
    }
  }

  useEffect(() => {
    Promise.all([load(), hydrateNewCode()]).catch((e) => setError(e.message || 'Failed to load suppliers.'));
  }, []);

  async function submit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      const payload = { ...form };
      if (editingId) {
        await updateSupplierEntity(editingId, payload);
        setNotice('Supplier updated.');
      } else {
        await createSupplierEntity(payload);
        setNotice('Supplier created.');
      }
      setEditingId(null);
      setForm({ ...EMPTY_FORM });
      await hydrateNewCode();
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save supplier.');
    }
  }

  function isSubmittable() {
    return !!String(form.name || '').trim();
  }

  function editRow(row) {
    setEditingId(row.id);
    setForm({
      code: row.code || '',
      name: row.name || '',
      supplier_type: row.supplier_type || '',
      category: row.category || '',
      contact_person: row.contact_person || '',
      phone: row.phone || '',
      email: row.email || '',
      address: row.address || '',
      tin: row.tin || '',
      tax_id: row.tax_id || '',
      payment_terms: row.payment_terms || '',
      is_active: !!row.is_active,
      notes: row.notes || '',
    });
  }

  async function removeRow(row) {
    if (!window.confirm(`Delete supplier ${row.code}?`)) return;
    setError('');
    try {
      await deleteSupplierEntity(row.id);
      setNotice('Supplier deleted.');
      if (editingId === row.id) {
        setEditingId(null);
        setForm({ ...EMPTY_FORM });
      }
      await load();
    } catch (err) {
      setError(err.message || 'Failed to delete supplier.');
    }
  }

  return (
    <div className="stack">
      <section className="section">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h1>Suppliers</h1>
            <p className="muted">Supplier master linked to PR/PO/Receiving and payables.</p>
          </div>
          <div className="row wrap">
            <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search code, name, contact" />
            <button type="button" className="secondary" onClick={() => load(search).catch((e) => setError(e.message || 'Failed to search suppliers.'))}>Search</button>
          </div>
        </div>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <div className="grid">
        <section className="section">
          <h2>{editingId ? `Edit Supplier #${editingId}` : 'New Supplier'}</h2>
          <form onSubmit={submit} className="stack" onKeyDown={(event) => shouldPreventEnterSubmit(event, isSubmittable)}>
            <div className="form-grid">
              <label>Code<input value={form.code} onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))} placeholder="Auto-generated if blank" /></label>
              <label>Name<input required value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} /></label>
              <label>Type<input value={form.supplier_type} onChange={(e) => setForm((f) => ({ ...f, supplier_type: e.target.value }))} placeholder="Produce, Utility, Services" /></label>
              <label>Category<input value={form.category} onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))} /></label>
              <label>Contact Person<input value={form.contact_person} onChange={(e) => setForm((f) => ({ ...f, contact_person: e.target.value }))} /></label>
              <label>Phone<input value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} /></label>
              <label>Email<input type="email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} /></label>
              <label>Payment Terms<input value={form.payment_terms} onChange={(e) => setForm((f) => ({ ...f, payment_terms: e.target.value }))} placeholder="COD, 15 Days, 30 Days" /></label>
              <label>TIN<input value={form.tin} onChange={(e) => setForm((f) => ({ ...f, tin: e.target.value }))} /></label>
              <label>Tax ID<input value={form.tax_id} onChange={(e) => setForm((f) => ({ ...f, tax_id: e.target.value }))} /></label>
              <label>Active
                <select value={String(form.is_active)} onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.value === 'true' }))}>
                  <option value="true">Active</option>
                  <option value="false">Inactive</option>
                </select>
              </label>
            </div>
            <label>Address<textarea value={form.address} onChange={(e) => setForm((f) => ({ ...f, address: e.target.value }))} /></label>
            <label>Notes<textarea value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} /></label>
            <div className="row wrap">
              <button type="submit">{editingId ? 'Update Supplier' : 'Create Supplier'}</button>
              {editingId && <button type="button" className="secondary" onClick={() => { setEditingId(null); setForm({ ...EMPTY_FORM }); hydrateNewCode(); }}>Cancel</button>}
            </div>
          </form>
        </section>

        <section className="section">
          <h2>Supplier List</h2>
          <table className="table">
            <thead><tr><th>Code</th><th>Name</th><th>Contact</th><th>Terms</th><th></th></tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.code}</td>
                  <td>{row.name}</td>
                  <td>{row.contact_person || '-'} {row.phone ? `· ${row.phone}` : ''}</td>
                  <td>{row.payment_terms || '-'}</td>
                  <td className="row wrap">
                    <button type="button" className="secondary" onClick={() => editRow(row)}>Edit</button>
                    <button type="button" className="secondary" onClick={() => removeRow(row)}>Delete</button>
                  </td>
                </tr>
              ))}
              {!rows.length && <tr><td colSpan="5" className="muted">No suppliers yet.</td></tr>}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}
