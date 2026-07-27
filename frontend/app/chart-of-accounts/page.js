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
import { useConfirmAction } from '../../components/ConfirmActionProvider';
import RecordDrawer from '../../components/RecordDrawer';

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
  const confirmAction = useConfirmAction();
  const [rows, setRows] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
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

  function closeDrawer() {
    setDrawerOpen(false);
    setEditingId(null);
    setForm({ ...EMPTY_FORM });
    hydrateNewCode();
  }

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
      setDrawerOpen(false);
      setEditingId(null);
      setForm({ ...EMPTY_FORM });
      await hydrateNewCode();
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save chart account.');
    }
  }

  function startNew() {
    setEditingId(null);
    setForm({ ...EMPTY_FORM });
    setDrawerOpen(true);
    hydrateNewCode();
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
    setDrawerOpen(true);
  }

  async function removeRow(row) {
    if (!await confirmAction({ title: `Delete account ${row.code} - ${row.name}?`, description: 'Accounts referenced by journals or mapping rules should be deactivated instead of removed.' })) return;
    setError('');
    try {
      await deleteChartAccount(row.id);
      setNotice('Chart account deleted.');
      if (editingId === row.id) closeDrawer();
      await load();
    } catch (err) {
      setError(err.message || 'Failed to delete chart account.');
    }
  }

  function isSubmittable() {
    return !!String(form.name || '').trim();
  }

  return (
    <div className="workflow-page">
      <section className="section workflow-page__header">
        <div className="workflow-page__header-copy">
          <h1>Chart of Accounts</h1>
          <p className="muted">Maintain the account structure used by journals, mapping rules, reports, and period close.</p>
        </div>
        <div className="workflow-page__toolbar">
          <input data-enter-context="search" type="search" placeholder="Search code, name, or type" value={search} onChange={(e) => setSearch(e.target.value)} />
          <button type="button" onClick={startNew}>New account</button>
        </div>
      </section>

      {!!notice && <div className="success-text" role="status">{notice}</div>}
      {!!error && <div className="error-text" role="alert">{error}</div>}

      <section className="section workflow-list-card">
        <div className="workflow-list-card__header">
          <div>
            <h2>Accounts</h2>
            <div className="workflow-result-count">{filteredRows.length} of {rows.length} accounts</div>
          </div>
        </div>
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>Code</th><th>Name</th><th>Type</th><th>Parent</th><th>Status</th><th aria-label="Actions" /></tr></thead>
            <tbody>
              {filteredRows.map((row) => (
                <tr key={row.id}>
                  <td>{row.code}</td>
                  <td>{row.name}<br /><span className="small muted">{row.subtype || '-'}</span></td>
                  <td>{row.account_type}</td>
                  <td>{row.parent_code ? `${row.parent_code} · ${row.parent_name}` : '-'}</td>
                  <td><span className={row.is_active ? 'status-pill status-success' : 'status-pill'}>{row.is_active ? 'Active' : 'Inactive'}</span></td>
                  <td className="row wrap">
                    <button type="button" className="secondary" onClick={() => editRow(row)}>Edit</button>
                    <button type="button" className="secondary" onClick={() => removeRow(row)}>Delete</button>
                  </td>
                </tr>
              ))}
              {!filteredRows.length && <tr><td colSpan="6" className="muted">No chart accounts match the current search.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <RecordDrawer
        open={drawerOpen}
        title={editingId ? 'Edit account' : 'New account'}
        description={editingId ? 'Update this account without losing your place in the list.' : 'Create an account, then return directly to the account list.'}
        onClose={closeDrawer}
      >
        <form onSubmit={submit} className="stack" onKeyDown={(event) => shouldPreventEnterSubmit(event, isSubmittable)}>
          <div className="form-grid">
            <label>Code<input value={form.code} onChange={(e) => setForm((prev) => ({ ...prev, code: e.target.value }))} placeholder="Auto-generated if blank" /></label>
            <label>Name<input required value={form.name} onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))} /></label>
            <label>Type
              <select value={form.account_type} onChange={(e) => setForm((prev) => ({ ...prev, account_type: e.target.value }))}>
                <option value="asset">Asset</option>
                <option value="liability">Liability</option>
                <option value="equity">Equity</option>
                <option value="revenue">Revenue</option>
                <option value="expense">Expense</option>
              </select>
            </label>
            <label>Subtype<input value={form.subtype} onChange={(e) => setForm((prev) => ({ ...prev, subtype: e.target.value }))} /></label>
            <label>Parent account
              <select value={form.parent_id} onChange={(e) => setForm((prev) => ({ ...prev, parent_id: e.target.value }))}>
                <option value="">No parent</option>
                {rows.filter((row) => row.id !== editingId).map((row) => (
                  <option key={row.id} value={row.id}>{row.code} · {row.name}</option>
                ))}
              </select>
            </label>
            <label>Status
              <select value={String(form.is_active)} onChange={(e) => setForm((prev) => ({ ...prev, is_active: e.target.value === 'true' }))}>
                <option value="true">Active</option>
                <option value="false">Inactive</option>
              </select>
            </label>
          </div>
          <label>Notes<textarea value={form.notes} onChange={(e) => setForm((prev) => ({ ...prev, notes: e.target.value }))} /></label>
          <div className="record-drawer__footer">
            <button type="button" className="secondary" onClick={closeDrawer}>Cancel</button>
            <button type="submit">{editingId ? 'Update account' : 'Create account'}</button>
          </div>
        </form>
      </RecordDrawer>
    </div>
  );
}
