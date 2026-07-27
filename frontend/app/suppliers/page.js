'use client';

import { useEffect, useState } from 'react';
import LegacyExternalModuleNotice from '../../components/LegacyExternalModuleNotice';
import RecordDrawer from '../../components/RecordDrawer';
import {
  createSupplierEntity,
  deleteSupplierEntity,
  fetchNextCodePreview,
  fetchSuppliersEntity,
  updateSupplierEntity,
} from '../../lib/api';
import { shouldPreventEnterSubmit } from '../../lib/formBehavior';
import { useConfirmAction } from '../../components/ConfirmActionProvider';

const EMPTY_FORM = {
  code: '', name: '', supplier_type: '', category: '', contact_person: '', phone: '', email: '', address: '', tin: '', tax_id: '', payment_terms: '', is_active: true, notes: '',
};

export default function SuppliersPage() {
  const confirmAction = useConfirmAction();
  const [rows, setRows] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
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

  function closeDrawer() {
    setDrawerOpen(false);
    setEditingId(null);
    setForm({ ...EMPTY_FORM });
    hydrateNewCode();
  }

  function startNew() {
    setEditingId(null);
    setForm({ ...EMPTY_FORM });
    setDrawerOpen(true);
    hydrateNewCode();
  }

  async function submit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      if (editingId) {
        await updateSupplierEntity(editingId, { ...form });
        setNotice('Supplier updated.');
      } else {
        await createSupplierEntity({ ...form });
        setNotice('Supplier created.');
      }
      setDrawerOpen(false);
      setEditingId(null);
      setForm({ ...EMPTY_FORM });
      await hydrateNewCode();
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save supplier.');
    }
  }

  function editRow(row) {
    setEditingId(row.id);
    setForm({
      code: row.code || '', name: row.name || '', supplier_type: row.supplier_type || '', category: row.category || '', contact_person: row.contact_person || '', phone: row.phone || '', email: row.email || '', address: row.address || '', tin: row.tin || '', tax_id: row.tax_id || '', payment_terms: row.payment_terms || '', is_active: !!row.is_active, notes: row.notes || '',
    });
    setDrawerOpen(true);
  }

  async function removeRow(row) {
    if (!await confirmAction({ title: `Delete supplier ${row.code}?`, description: 'Suppliers already used in procurement records should be made inactive instead.' })) return;
    setError('');
    try {
      await deleteSupplierEntity(row.id);
      setNotice('Supplier deleted.');
      if (editingId === row.id) closeDrawer();
      await load();
    } catch (err) {
      setError(err.message || 'Failed to delete supplier.');
    }
  }

  function isSubmittable() {
    return !!String(form.name || '').trim();
  }

  return (
    <div className="workflow-page">
      <LegacyExternalModuleNotice appName="Inventory & Procurement" />
      <section className="section workflow-page__header">
        <div className="workflow-page__header-copy">
          <h1>Suppliers</h1>
          <p className="muted">Review supplier records here while procurement remains owned by Inventory & Procurement.</p>
        </div>
        <div className="workflow-page__toolbar">
          <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search code, name, or contact" />
          <button type="button" className="secondary" onClick={() => load(search).catch((e) => setError(e.message || 'Failed to search suppliers.'))}>Search</button>
          <button type="button" onClick={startNew}>New supplier</button>
        </div>
      </section>

      {!!notice && <div className="success-text" role="status">{notice}</div>}
      {!!error && <div className="error-text" role="alert">{error}</div>}

      <section className="section workflow-list-card">
        <div className="workflow-list-card__header">
          <div><h2>Supplier list</h2><div className="workflow-result-count">{rows.length} suppliers</div></div>
        </div>
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>Code</th><th>Name</th><th>Contact</th><th>Terms</th><th>Status</th><th aria-label="Actions" /></tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.code}</td>
                  <td>{row.name}</td>
                  <td>{row.contact_person || '-'} {row.phone ? `· ${row.phone}` : ''}</td>
                  <td>{row.payment_terms || '-'}</td>
                  <td><span className={row.is_active ? 'status-pill status-success' : 'status-pill'}>{row.is_active ? 'Active' : 'Inactive'}</span></td>
                  <td className="row wrap"><button type="button" className="secondary" onClick={() => editRow(row)}>Edit</button><button type="button" className="secondary" onClick={() => removeRow(row)}>Delete</button></td>
                </tr>
              ))}
              {!rows.length && <tr><td colSpan="6" className="muted">No suppliers match the current search.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <RecordDrawer open={drawerOpen} title={editingId ? 'Edit supplier' : 'New supplier'} description="Supplier details stay out of the main list until you need to create or edit a record." onClose={closeDrawer}>
        <form onSubmit={submit} className="stack" onKeyDown={(event) => shouldPreventEnterSubmit(event, isSubmittable)}>
          <div className="form-grid">
            <label>Code<input value={form.code} onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))} placeholder="Auto-generated if blank" /></label>
            <label>Name<input required value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} /></label>
            <label>Type<input value={form.supplier_type} onChange={(e) => setForm((f) => ({ ...f, supplier_type: e.target.value }))} placeholder="Produce, Utility, Services" /></label>
            <label>Category<input value={form.category} onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))} /></label>
            <label>Contact person<input value={form.contact_person} onChange={(e) => setForm((f) => ({ ...f, contact_person: e.target.value }))} /></label>
            <label>Phone<input value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} /></label>
            <label>Email<input type="email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} /></label>
            <label>Payment terms<input value={form.payment_terms} onChange={(e) => setForm((f) => ({ ...f, payment_terms: e.target.value }))} placeholder="COD, 15 Days, 30 Days" /></label>
            <label>TIN<input value={form.tin} onChange={(e) => setForm((f) => ({ ...f, tin: e.target.value }))} /></label>
            <label>Tax ID<input value={form.tax_id} onChange={(e) => setForm((f) => ({ ...f, tax_id: e.target.value }))} /></label>
            <label>Status<select value={String(form.is_active)} onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.value === 'true' }))}><option value="true">Active</option><option value="false">Inactive</option></select></label>
          </div>
          <label>Address<textarea value={form.address} onChange={(e) => setForm((f) => ({ ...f, address: e.target.value }))} /></label>
          <label>Notes<textarea value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} /></label>
          <div className="record-drawer__footer"><button type="button" className="secondary" onClick={closeDrawer}>Cancel</button><button type="submit">{editingId ? 'Update supplier' : 'Create supplier'}</button></div>
        </form>
      </RecordDrawer>
    </div>
  );
}
