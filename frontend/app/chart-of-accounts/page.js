'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  createChartAccount,
  deleteChartAccount,
  fetchChartAccounts,
  fetchNextCodePreview,
  updateChartAccount,
} from '../../lib/api';
import { shouldPreventEnterSubmit } from '../../lib/formBehavior';

const EMPTY_FORM = {
  code: '',
  name: '',
  account_type: 'asset',
  subtype: '',
  parent_id: '',
  is_active: true,
  notes: '',
};

export default function ChartOfAccountsPage() {
  const [rows, setRows] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function load() {
    const data = await fetchChartAccounts(false);
    setRows(Array.isArray(data) ? data : []);
  }

  async function hydrateNewCode() {
    try {
      const preview = await fetchNextCodePreview('chart_account');
      setForm((prev) => ({ ...prev, code: preview?.code || prev.code || '' }));
    } catch {
      // Keep manual fallback.
    }
  }

  useEffect(() => {
    Promise.all([load(), hydrateNewCode()]).catch((e) => setError(e.message || 'Failed to load chart of accounts.'));
  }, []);

  const filteredRows = useMemo(() => {
    const q = String(search || '').trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((row) =>
      String(row.code || '').toLowerCase().includes(q)
      || String(row.name || '').toLowerCase().includes(q)
      || String(row.account_type || '').toLowerCase().includes(q)
      || String(row.subtype || '').toLowerCase().includes(q)
    );
  }, [rows, search]);

  async function submit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      const payload = {
        code: form.code,
        name: form.name,
        account_type: form.account_type,
        subtype: form.subtype || null,
        parent_id: form.parent_id ? Number(form.parent_id) : null,
        is_active: !!form.is_active,
        notes: form.notes || null,
      };
      if (editingId) {
        await updateChartAccount(editingId, payload);
        setNotice('Chart account updated.');
      } else {
        await createChartAccount(payload);
        setNotice('Chart account created.');
      }
      setEditingId(null);
      setForm({ ...EMPTY_FORM });
      await hydrateNewCode();
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save chart account.');
    }
  }

  function editRow(row) {
    setEditingId(row.id);
    setForm({
      code: row.code || '',
      name: row.name || '',
      account_type: row.account_type || 'asset',
      subtype: row.subtype || '',
      parent_id: row.parent_id ? String(row.parent_id) : '',
      is_active: !!row.is_active,
      notes: row.notes || '',
    });
  }

  async function removeRow(row) {
    if (!window.confirm(`Delete account ${row.code} - ${row.name}?`)) return;
    setError('');
    try {
      await deleteChartAccount(row.id);
      setNotice('Chart account deleted.');
      if (editingId === row.id) {
        setEditingId(null);
        setForm({ ...EMPTY_FORM });
      }
      await load();
    } catch (err) {
      setError(err.message || 'Failed to delete chart account.');
    }
  }

  function isSubmittable() {
    return !!String(form.name || '').trim();
  }

  return (
    <div className="stack">
      <section className="section">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h1>Chart of Accounts</h1>
            <p className="muted">Create and maintain account codes used by journals and mapping rules.</p>
          </div>
          <input data-enter-context="search" type="search" placeholder="Search code/name/type" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <div className="grid">
        <section className="section">
          <h2>{editingId ? `Edit Account #${editingId}` : 'New Account'}</h2>
          <form onSubmit={submit} className="stack" onKeyDown={(event) => shouldPreventEnterSubmit(event, isSubmittable)}>
            <div className="form-grid">
              <label>Code<input value={form.code} onChange={(e) => setForm((prev) => ({ ...prev, code: e.target.value }))} placeholder="Auto-generated if blank" /></label>
              <label>Name<input required value={form.name} onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))} /></label>
              <label>Type
                <select value={form.account_type} onChange={(e) => setForm((prev) => ({ ...prev, account_type: e.target.value }))}>
                  <option value="asset">asset</option>
                  <option value="liability">liability</option>
                  <option value="equity">equity</option>
                  <option value="revenue">revenue</option>
                  <option value="expense">expense</option>
                </select>
              </label>
              <label>Subtype<input value={form.subtype} onChange={(e) => setForm((prev) => ({ ...prev, subtype: e.target.value }))} /></label>
              <label>Parent Account
                <select value={form.parent_id} onChange={(e) => setForm((prev) => ({ ...prev, parent_id: e.target.value }))}>
                  <option value="">No parent</option>
                  {rows.filter((row) => row.id !== editingId).map((row) => (
                    <option key={row.id} value={row.id}>{row.code} · {row.name}</option>
                  ))}
                </select>
              </label>
              <label>Active
                <select value={String(form.is_active)} onChange={(e) => setForm((prev) => ({ ...prev, is_active: e.target.value === 'true' }))}>
                  <option value="true">Active</option>
                  <option value="false">Inactive</option>
                </select>
              </label>
            </div>
            <label>Notes<textarea value={form.notes} onChange={(e) => setForm((prev) => ({ ...prev, notes: e.target.value }))} /></label>
            <div className="row wrap">
              <button type="submit">{editingId ? 'Update Account' : 'Create Account'}</button>
              {editingId && <button type="button" className="secondary" onClick={() => { setEditingId(null); setForm({ ...EMPTY_FORM }); hydrateNewCode(); }}>Cancel</button>}
            </div>
          </form>
        </section>

        <section className="section">
          <h2>Account List</h2>
          <table className="table">
            <thead><tr><th>Code</th><th>Name</th><th>Type</th><th>Parent</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {filteredRows.map((row) => (
                <tr key={row.id}>
                  <td>{row.code}</td>
                  <td>{row.name}<br /><span className="small muted">{row.subtype || '-'}</span></td>
                  <td>{row.account_type}</td>
                  <td>{row.parent_code ? `${row.parent_code} · ${row.parent_name}` : '-'}</td>
                  <td>{row.is_active ? 'Active' : 'Inactive'}</td>
                  <td className="row wrap">
                    <button type="button" className="secondary" onClick={() => editRow(row)}>Edit</button>
                    <button type="button" className="secondary" onClick={() => removeRow(row)}>Delete</button>
                  </td>
                </tr>
              ))}
              {!filteredRows.length && <tr><td colSpan="6" className="muted">No chart accounts found.</td></tr>}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}
