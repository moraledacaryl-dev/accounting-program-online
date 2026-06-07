'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  createAccountMapping,
  deleteAccountMapping,
  fetchAccountMappings,
  fetchChartAccounts,
  updateAccountMapping,
} from '../../lib/api';
import { shouldPreventEnterSubmit } from '../../lib/formBehavior';
import { useConfirmAction } from '../../components/ConfirmActionProvider';

const EMPTY_FORM = {
  module_slug: '',
  category: '',
  bucket: '',
  item: '',
  direction: '',
  payment_method: '',
  debit_account_code: '',
  credit_account_code: '',
  priority: '100',
  is_active: true,
  notes: '',
};

export default function AccountMappingPage() {
  const confirmAction = useConfirmAction();
  const [rows, setRows] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [moduleFilter, setModuleFilter] = useState('');
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function load() {
    const [mappingData, accountData] = await Promise.all([
      fetchAccountMappings({ module_slug: moduleFilter || undefined }),
      fetchChartAccounts(true),
    ]);
    setRows(Array.isArray(mappingData) ? mappingData : []);
    setAccounts(Array.isArray(accountData) ? accountData : []);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || 'Failed to load account mappings.'));
  }, [moduleFilter]);

  const moduleOptions = useMemo(() => {
    return [...new Set(rows.map((row) => row.module_slug).filter(Boolean))].sort();
  }, [rows]);

  async function submit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      const payload = {
        module_slug: form.module_slug || null,
        category: form.category || null,
        bucket: form.bucket || null,
        item: form.item || null,
        direction: form.direction || null,
        payment_method: form.payment_method || null,
        debit_account_code: form.debit_account_code || null,
        credit_account_code: form.credit_account_code || null,
        priority: Number(form.priority || 100),
        is_active: !!form.is_active,
        notes: form.notes || null,
      };
      if (!payload.module_slug) {
        setError('Module slug is required.');
        return;
      }
      if (editingId) {
        await updateAccountMapping(editingId, payload);
        setNotice('Account mapping updated.');
      } else {
        await createAccountMapping(payload);
        setNotice('Account mapping created.');
      }
      setEditingId(null);
      setForm({ ...EMPTY_FORM });
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save account mapping.');
    }
  }

  function editRow(row) {
    setEditingId(row.id);
    setForm({
      module_slug: row.module_slug || '',
      category: row.category || '',
      bucket: row.bucket || '',
      item: row.item || '',
      direction: row.direction || '',
      payment_method: row.payment_method || '',
      debit_account_code: row.debit_account_code || '',
      credit_account_code: row.credit_account_code || '',
      priority: String(row.priority ?? '100'),
      is_active: !!row.is_active,
      notes: row.notes || '',
    });
  }

  async function removeRow(row) {
    if (!await confirmAction({ title: `Delete account mapping #${row.id}?`, description: 'Future automated accounting entries will no longer use this rule.' })) return;
    setError('');
    try {
      await deleteAccountMapping(row.id);
      setNotice('Account mapping deleted.');
      if (editingId === row.id) {
        setEditingId(null);
        setForm({ ...EMPTY_FORM });
      }
      await load();
    } catch (err) {
      setError(err.message || 'Failed to delete account mapping.');
    }
  }

  function isSubmittable() {
    return !!String(form.module_slug || '').trim();
  }

  return (
    <div className="stack">
      <section className="section">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h1>Account Mapping</h1>
            <p className="muted">Map module/category/bucket/item and direction to debit/credit account codes.</p>
          </div>
          <label style={{ minWidth: 220 }}>
            Module Filter
            <select value={moduleFilter} onChange={(e) => setModuleFilter(e.target.value)}>
              <option value="">All</option>
              {moduleOptions.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
        </div>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <div className="grid">
        <section className="section">
          <h2>{editingId ? `Edit Mapping #${editingId}` : 'New Mapping'}</h2>
          <form onSubmit={submit} className="stack" onKeyDown={(event) => shouldPreventEnterSubmit(event, isSubmittable)}>
            <div className="form-grid">
              <label>Module Slug<input required value={form.module_slug} onChange={(e) => setForm((prev) => ({ ...prev, module_slug: e.target.value }))} placeholder="rooms, restaurant, inventory" /></label>
              <label>Category<input value={form.category} onChange={(e) => setForm((prev) => ({ ...prev, category: e.target.value }))} /></label>
              <label>Subcategory<input value={form.bucket} onChange={(e) => setForm((prev) => ({ ...prev, bucket: e.target.value }))} /></label>
              <label>Level 3 Item<input value={form.item} onChange={(e) => setForm((prev) => ({ ...prev, item: e.target.value }))} /></label>
              <label>Direction<input value={form.direction} onChange={(e) => setForm((prev) => ({ ...prev, direction: e.target.value }))} placeholder="in, out, income, expense" /></label>
              <label>Payment Method<input value={form.payment_method} onChange={(e) => setForm((prev) => ({ ...prev, payment_method: e.target.value }))} placeholder="cash, bank, gcash" /></label>
              <label>Debit Account
                <select value={form.debit_account_code} onChange={(e) => setForm((prev) => ({ ...prev, debit_account_code: e.target.value }))}>
                  <option value="">None</option>
                  {accounts.map((row) => <option key={row.id} value={row.code}>{row.code} · {row.name}</option>)}
                </select>
              </label>
              <label>Credit Account
                <select value={form.credit_account_code} onChange={(e) => setForm((prev) => ({ ...prev, credit_account_code: e.target.value }))}>
                  <option value="">None</option>
                  {accounts.map((row) => <option key={row.id} value={row.code}>{row.code} · {row.name}</option>)}
                </select>
              </label>
              <label>Priority<input type="number" min="1" step="1" value={form.priority} onChange={(e) => setForm((prev) => ({ ...prev, priority: e.target.value }))} /></label>
              <label>Active
                <select value={String(form.is_active)} onChange={(e) => setForm((prev) => ({ ...prev, is_active: e.target.value === 'true' }))}>
                  <option value="true">Active</option>
                  <option value="false">Inactive</option>
                </select>
              </label>
            </div>
            <label>Notes<textarea value={form.notes} onChange={(e) => setForm((prev) => ({ ...prev, notes: e.target.value }))} /></label>
            <div className="row wrap">
              <button type="submit">{editingId ? 'Update Mapping' : 'Create Mapping'}</button>
              {editingId && <button type="button" className="secondary" onClick={() => { setEditingId(null); setForm({ ...EMPTY_FORM }); }}>Cancel</button>}
            </div>
          </form>
        </section>

        <section className="section">
          <h2>Mapping List</h2>
          <table className="table">
            <thead><tr><th>Scope</th><th>Direction/Method</th><th>Accounts</th><th>Priority</th><th></th></tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>
                    <strong>{row.module_slug}</strong>
                    <br />
                    <span className="small muted">{row.category || '*'} / {row.bucket || '*'} / {row.item || '*'}</span>
                  </td>
                  <td>{row.direction || '*'} / {row.payment_method || '*'}</td>
                  <td>
                    Dr {row.debit_account_code || '-'}
                    <br />
                    <span className="small muted">Cr {row.credit_account_code || '-'}</span>
                  </td>
                  <td>{row.priority}</td>
                  <td className="row wrap">
                    <button type="button" className="secondary" onClick={() => editRow(row)}>Edit</button>
                    <button type="button" className="secondary" onClick={() => removeRow(row)}>Delete</button>
                  </td>
                </tr>
              ))}
              {!rows.length && <tr><td colSpan="5" className="muted">No account mappings found.</td></tr>}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}
