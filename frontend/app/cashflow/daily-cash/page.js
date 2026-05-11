'use client';

import { Suspense, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import CashflowTabs from '../../../components/cashflow/CashflowTabs';
import DailyCashForm from '../../../components/cashflow/DailyCashForm';
import ReconciliationTable from '../../../components/cashflow/ReconciliationTable';
import {
  approveReconciliation,
  closeReconciliation,
  createReconciliation,
  fetchFinancialAccounts,
  fetchReconciliations,
  reverseReconciliation,
  updateReconciliation,
} from '../../../lib/cashflowApi';
import { useCurrentUser } from '../../../lib/useCurrentUser';
import { todayISO } from '../shared';

const EMPTY_FORM = {
  financial_account_id: '',
  reconciliation_date: todayISO(),
  shift_name: 'day',
  actual_counted: '',
  status: 'counted',
  notes: '',
};

function DailyCashContent() {
  const { can } = useCurrentUser();
  const searchParams = useSearchParams();
  const [accounts, setAccounts] = useState([]);
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function load() {
    const [accountRows, reconRows] = await Promise.all([
      fetchFinancialAccounts({ only_active: true }),
      fetchReconciliations({ limit: 400 }),
    ]);
    setAccounts(Array.isArray(accountRows) ? accountRows : []);
    setRows(Array.isArray(reconRows) ? reconRows : []);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || 'Failed to load daily cash data.'));
  }, []);

  useEffect(() => {
    const accountId = searchParams.get('account_id');
    if (!accountId) return;
    setForm((f) => ({ ...f, financial_account_id: accountId }));
  }, [searchParams]);

  const preview = useMemo(() => {
    if (!form.financial_account_id || !form.reconciliation_date) return null;
    const found = rows.find((row) => (
      String(row.financial_account_id) === String(form.financial_account_id)
      && row.reconciliation_date === form.reconciliation_date
      && String(row.shift_name || 'day') === String(form.shift_name || 'day')
    ));
    if (found) {
      return {
        opening_balance: found.opening_balance,
        expected_in: found.expected_in,
        expected_out: found.expected_out,
        expected_closing: found.expected_closing,
        variance: Number(form.actual_counted || 0) - Number(found.expected_closing || 0),
      };
    }
    return null;
  }, [rows, form.financial_account_id, form.reconciliation_date, form.shift_name, form.actual_counted]);

  async function submit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      const payload = {
        financial_account_id: Number(form.financial_account_id),
        reconciliation_date: form.reconciliation_date,
        shift_name: form.shift_name || null,
        actual_counted: Number(form.actual_counted || 0),
        status: form.status,
        notes: form.notes || null,
        lines: [],
      };
      if (editingId) {
        await updateReconciliation(editingId, payload);
        setNotice(`Cash count #${editingId} updated.`);
      } else {
        await createReconciliation(payload);
        setNotice('Cash count saved.');
      }
      setForm((f) => ({ ...f, actual_counted: '', notes: '' }));
      setEditingId(null);
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save cash count.');
    }
  }

  function startEdit(row) {
    setEditingId(row.id);
    setForm({
      financial_account_id: row.financial_account_id ? String(row.financial_account_id) : '',
      reconciliation_date: row.reconciliation_date || todayISO(),
      shift_name: row.shift_name || 'day',
      actual_counted: String(row.actual_counted ?? ''),
      status: row.status || 'counted',
      notes: row.notes || '',
    });
  }

  async function runAction(action, successMessage) {
    setError('');
    setNotice('');
    try {
      await action();
      setNotice(successMessage);
      await load();
    } catch (err) {
      setError(err.message || 'Action failed.');
    }
  }

  return (
    <div className="stack">
      <CashflowTabs />

      <section className="section">
        <h1>Cash Count</h1>
        <p className="muted">Count drawers, petty cash, safes, or occasional bank balances. Banks can be checked periodically, not forced every day.</p>
        {editingId ? <p className="small muted">Editing cash count #{editingId}</p> : null}
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <section className="section">
        <DailyCashForm accounts={accounts} form={form} setForm={setForm} preview={preview} onSubmit={submit} />
        {editingId && (
          <button
            type="button"
            className="secondary"
            onClick={() => {
              setEditingId(null);
              setForm({ ...EMPTY_FORM, reconciliation_date: todayISO() });
            }}
          >
            Cancel Edit
          </button>
        )}
      </section>

      <section className="section">
        <h2>Count History</h2>
        <ReconciliationTable
          rows={rows}
          renderActions={(row) => (
            can('cashflow.reconcile') ? (
              <>
                <button type="button" className="secondary" onClick={() => startEdit(row)}>Edit</button>
                <details className="row-actions-more">
                  <summary>More</summary>
                  <button type="button" className="secondary" onClick={() => runAction(() => approveReconciliation(row.id, {}), `Cash count #${row.id} reviewed.`)}>Review</button>
                  <button type="button" className="secondary" onClick={() => runAction(() => closeReconciliation(row.id, { reason: 'Closed from daily cash page' }), `Cash count #${row.id} closed.`)}>Close</button>
                  <button type="button" className="secondary" onClick={() => runAction(() => reverseReconciliation(row.id, { reason: 'Reversed from daily cash page' }), `Cash count #${row.id} reversed.`)}>Reverse</button>
                </details>
              </>
            ) : null
          )}
        />
      </section>
    </div>
  );
}

export default function DailyCashPage() {
  return (
    <Suspense fallback={<div className="stack"><CashflowTabs /></div>}>
      <DailyCashContent />
    </Suspense>
  );
}
