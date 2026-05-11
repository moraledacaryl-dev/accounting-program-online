'use client';

import { useMemo, useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import CashflowTabs from '../../../components/cashflow/CashflowTabs';
import AccountCard from '../../../components/cashflow/AccountCard';
import ToggleField from '../../../components/cashflow/ToggleField';
import {
  bootstrapFinancialAccounts,
  createFinancialAccount,
  fetchFinancialAccounts,
  fetchNextCodePreview,
  updateFinancialAccount,
} from '../../../lib/cashflowApi';
import { shouldPreventEnterSubmit } from '../../../lib/formBehavior';

const EMPTY_FORM = {
  name: '',
  code: '',
  account_type: 'cash_drawer',
  subtype: '',
  currency: 'PHP',
  is_active: true,
  requires_daily_reconciliation: true,
  opening_balance: '',
  department: '',
  notes: '',
};

const FILTERS = [
  ['all', 'All Accounts'],
  ['cash_drawer', 'Drawers'],
  ['bank', 'Banks'],
  ['petty_cash', 'Petty Cash'],
  ['safe', 'Safes'],
  ['ewallet', 'E-Wallet'],
];

export default function CashflowAccountsPage() {
  const router = useRouter();
  const [rows, setRows] = useState([]);
  const [filterType, setFilterType] = useState('all');
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function load() {
    setRows(await fetchFinancialAccounts());
  }

  async function hydrateNewCode() {
    try {
      const preview = await fetchNextCodePreview('financial_account');
      setForm((prev) => ({ ...prev, code: preview?.code || prev.code || '' }));
    } catch {
      // Keep manual fallback.
    }
  }

  useEffect(() => {
    Promise.all([load(), hydrateNewCode()]).catch((e) => setError(e.message || 'Failed to load financial accounts.'));
  }, []);

  const filtered = useMemo(() => {
    if (filterType === 'all') return rows;
    return rows.filter((row) => row.account_type === filterType);
  }, [rows, filterType]);

  function beginEdit(row) {
    setEditingId(row.id);
    setForm({
      name: row.name || '',
      code: row.code || '',
      account_type: row.account_type || 'cash_drawer',
      subtype: row.subtype || '',
      currency: row.currency || 'PHP',
      is_active: !!row.is_active,
      requires_daily_reconciliation: !!row.requires_daily_reconciliation,
      opening_balance: row.opening_balance ?? '',
      department: row.department || '',
      notes: row.notes || '',
    });
  }

  function resetForm() {
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
        ...form,
        opening_balance: Number(form.opening_balance || 0),
      };
      if (editingId) {
        await updateFinancialAccount(editingId, payload);
        setNotice(`Account #${editingId} updated.`);
      } else {
        await createFinancialAccount(payload);
        setNotice('Financial account created.');
      }
      resetForm();
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save account.');
    }
  }

  function isSubmittable() {
    return !!String(form.name || '').trim();
  }

  return (
    <div className="stack">
      <CashflowTabs />

      <section className="section">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h1>Cashflow Accounts</h1>
            <p className="muted">Manage drawers, petty cash, safes, banks, and e-wallet accounts with simple count/check controls.</p>
          </div>
          <button className="secondary" onClick={async () => {
            try {
              await bootstrapFinancialAccounts();
              await load();
              setNotice('Default accounts ensured.');
            } catch (err) {
              setError(err.message || 'Failed to bootstrap defaults.');
            }
          }}>
            Create Default Accounts
          </button>
        </div>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <section className="section">
        <h2>{editingId ? `Edit Account #${editingId}` : 'Add Account'}</h2>
        <form onSubmit={submit} className="stack" onKeyDown={(event) => shouldPreventEnterSubmit(event, isSubmittable)}>
          <div className="form-grid">
            <label>Name<input required value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} /></label>
            <label>Code<input value={form.code} onChange={(e) => setForm((f) => ({ ...f, code: e.target.value.toUpperCase() }))} placeholder="Auto-generated if blank" /></label>
            <label>
              Account Type
              <select value={form.account_type} onChange={(e) => setForm((f) => ({ ...f, account_type: e.target.value }))}>
                <option value="cash_drawer">Cash drawer</option>
                <option value="petty_cash">Petty cash</option>
                <option value="safe">Safe</option>
                <option value="bank">Bank</option>
                <option value="ewallet">E-wallet</option>
              </select>
            </label>
            <label>Subtype<input value={form.subtype} onChange={(e) => setForm((f) => ({ ...f, subtype: e.target.value }))} /></label>
            <label>Department<input value={form.department} onChange={(e) => setForm((f) => ({ ...f, department: e.target.value }))} /></label>
            <label>Currency<input value={form.currency} onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value.toUpperCase() }))} /></label>
            <label>Opening Balance<input type="number" step="0.01" value={form.opening_balance} onChange={(e) => setForm((f) => ({ ...f, opening_balance: e.target.value }))} /></label>
            <ToggleField
              label="Active"
              checked={!!form.is_active}
              onChange={(value) => setForm((f) => ({ ...f, is_active: value }))}
              hint="Set to No to deactivate this account from daily use."
            />
            <ToggleField
              label="Count Daily"
              checked={!!form.requires_daily_reconciliation}
              onChange={(value) => setForm((f) => ({ ...f, requires_daily_reconciliation: value }))}
              hint="Set to Yes for accounts that must be counted daily."
            />
          </div>
          <label>Notes<textarea value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} /></label>
          <div className="row wrap">
            <button type="submit">{editingId ? 'Update Account' : 'Add Account'}</button>
            {editingId && <button className="secondary" type="button" onClick={resetForm}>Cancel</button>}
          </div>
        </form>
      </section>

      <section className="section">
        <div className="tabs" style={{ marginTop: 0 }}>
          {FILTERS.map(([key, label]) => (
            <button key={key} type="button" className={filterType === key ? 'tab active' : 'tab'} onClick={() => setFilterType(key)}>
              {label}
            </button>
          ))}
        </div>
      </section>

      <div className="card-grid">
        {filtered.map((row) => (
          <AccountCard
            key={row.id}
            account={row}
            onEdit={beginEdit}
            onReconcile={(account) => router.push(`/cashflow/daily-cash?account_id=${account.id}`)}
          />
        ))}
        {!filtered.length && <section className="section"><p className="muted">No accounts in this filter.</p></section>}
      </div>
    </div>
  );
}
