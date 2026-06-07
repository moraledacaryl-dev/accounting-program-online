'use client';

import { useEffect, useState } from 'react';
import CashflowTabs from '../../../components/cashflow/CashflowTabs';
import InputActionModal from '../../../components/InputActionModal';
import ReceivablesTable from '../../../components/cashflow/ReceivablesTable';
import SettlementModal from '../../../components/cashflow/SettlementModal';
import {
  collectReceivable,
  createReceivable,
  fetchFinancialAccounts,
  fetchReceivables,
  reopenReceivable,
  reverseReceivableCollection,
  updateReceivable,
  writeOffReceivable,
} from '../../../lib/cashflowApi';
import { shouldPreventEnterSubmit } from '../../../lib/formBehavior';
import { useCurrentUser } from '../../../lib/useCurrentUser';
import { todayISO } from '../shared';

const EMPTY_FORM = {
  source_type: '',
  source_id: '',
  counterparty_name: '',
  receivable_type: 'guest_balance',
  transaction_date: todayISO(),
  due_date: '',
  gross_amount: '',
  amount_collected: '0',
  status: 'open',
  notes: '',
  bir_include: false,
};

export default function ReceivablesPage() {
  const { can } = useCurrentUser();
  const [accounts, setAccounts] = useState([]);
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [collectionTarget, setCollectionTarget] = useState(null);
  const [reverseTarget, setReverseTarget] = useState(null);
  const [collectionForm, setCollectionForm] = useState({ amount: '', financial_account_id: '', payment_method: 'cash', reference_no: '', notes: '', auto_post_accounting: false });
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function load() {
    const [accountRows, receivableRows] = await Promise.all([
      fetchFinancialAccounts({ only_active: true }),
      fetchReceivables({ limit: 400 }),
    ]);
    setAccounts(Array.isArray(accountRows) ? accountRows : []);
    setRows(Array.isArray(receivableRows) ? receivableRows : []);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || 'Failed to load receivables.'));
  }, []);

  async function submit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      const payload = {
        source_type: form.source_type || null,
        source_id: form.source_id ? Number(form.source_id) : null,
        counterparty_name: form.counterparty_name,
        receivable_type: form.receivable_type,
        transaction_date: form.transaction_date,
        due_date: form.due_date || null,
        gross_amount: Number(form.gross_amount || 0),
        amount_collected: Number(form.amount_collected || 0),
        status: form.status,
        notes: form.notes || null,
        bir_include: !!form.bir_include,
      };
      if (editingId) {
        await updateReceivable(editingId, payload);
        setNotice('Balance updated.');
      } else {
        await createReceivable(payload);
        setNotice('Balance saved.');
      }
      setForm({ ...EMPTY_FORM, transaction_date: form.transaction_date });
      setEditingId(null);
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save balance.');
    }
  }

  function onCollect(row) {
    setError('');
    setCollectionTarget(row);
    setCollectionForm({
      amount: String(row.balance_due || ''),
      financial_account_id: accounts[0]?.id ? String(accounts[0].id) : '',
      payment_method: 'cash',
      reference_no: '',
      notes: `Collection for receivable #${row.id}`,
      auto_post_accounting: false,
    });
  }

  async function submitCollection(e) {
    e.preventDefault();
    if (!collectionTarget) return;
    const amount = Number(collectionForm.amount || 0);
    const accountId = Number(collectionForm.financial_account_id || 0);
    if (!Number.isFinite(amount) || amount <= 0) {
      setError('Enter a valid collection amount.');
      return;
    }
    if (!Number.isFinite(accountId) || accountId <= 0) {
      setError('Choose the receiving account.');
      return;
    }
    setError('');
    setNotice('');
    try {
      await collectReceivable(collectionTarget.id, {
        amount,
        collection_date: todayISO(),
        financial_account_id: accountId,
        payment_method: collectionForm.payment_method,
        reference_no: collectionForm.reference_no || null,
        notes: collectionForm.notes || null,
        auto_post_accounting: !!collectionForm.auto_post_accounting,
      });
      setNotice(`Payment received for ${collectionTarget.counterparty_name || `receivable #${collectionTarget.id}`}.`);
      setCollectionTarget(null);
      await load();
    } catch (err) {
      setError(err.message || 'Failed to collect receivable.');
    }
  }

  function editRow(row) {
    setEditingId(row.id);
    setForm({
      source_type: row.source_type || '',
      source_id: row.source_id ? String(row.source_id) : '',
      counterparty_name: row.counterparty_name || '',
      receivable_type: row.receivable_type || 'guest_balance',
      transaction_date: row.transaction_date || todayISO(),
      due_date: row.due_date || '',
      gross_amount: row.gross_amount ?? '',
      amount_collected: row.amount_collected ?? '0',
      status: row.status || 'open',
      notes: row.notes || '',
      bir_include: !!row.bir_include,
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

  async function reversePayment(transactionIdRaw) {
    const transactionId = Number(transactionIdRaw);
    if (!Number.isFinite(transactionId) || transactionId <= 0) {
      throw new Error('Enter a valid payment transaction ID.');
    }
    setError('');
    setNotice('');
    try {
      await reverseReceivableCollection(reverseTarget.id, transactionId, { reason: 'Reversed from receivables page' });
      setNotice(`Payment transaction #${transactionId} reversed.`);
      await load();
    } catch (err) {
      setError(err.message || 'Failed to reverse payment.');
      throw err;
    }
  }

  function isSubmittable() {
    return !!(String(form.counterparty_name || '').trim() && Number(form.gross_amount || 0) > 0);
  }

  return (
    <div className="stack">
      <CashflowTabs />

      <section className="section">
        <h1>Payments to Receive</h1>
        <p className="muted">Receive payments for guest, OTA, event, and company balances without needing journal knowledge.</p>
        {editingId ? <p className="small muted">Editing balance #{editingId}</p> : null}
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <section className="section">
        <h2>{editingId ? 'Edit Balance' : 'Add Balance to Collect'}</h2>
        <form onSubmit={submit} onKeyDown={(event) => shouldPreventEnterSubmit(event, isSubmittable)}>
          <div className="form-grid">
            <label>Customer / Source<input required value={form.counterparty_name} onChange={(e) => setForm((f) => ({ ...f, counterparty_name: e.target.value }))} /></label>
            <label>Type
              <select value={form.receivable_type} onChange={(e) => setForm((f) => ({ ...f, receivable_type: e.target.value }))}>
                <option value="guest_balance">Guest balance</option>
                <option value="ota_receivable">OTA receivable</option>
                <option value="event_balance">Event balance</option>
                <option value="corporate_receivable">Company / group billing</option>
              </select>
            </label>
            <label>Date<input type="date" value={form.transaction_date} onChange={(e) => setForm((f) => ({ ...f, transaction_date: e.target.value }))} /></label>
            <label>Due Date<input type="date" value={form.due_date} onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))} /></label>
            <label>Total Amount<input required type="number" min="0.01" step="0.01" value={form.gross_amount} onChange={(e) => setForm((f) => ({ ...f, gross_amount: e.target.value }))} /></label>
            <label>Already Collected<input type="number" min="0" step="0.01" value={form.amount_collected} onChange={(e) => setForm((f) => ({ ...f, amount_collected: e.target.value }))} /></label>
            <label>Status
              <select value={form.status} onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}>
                <option value="open">Open</option>
                <option value="partial">Partially paid</option>
                <option value="settled">Paid</option>
              </select>
            </label>
            <label>Include in BIR
              <select value={String(form.bir_include)} onChange={(e) => setForm((f) => ({ ...f, bir_include: e.target.value === 'true' }))}>
                <option value="false">No</option>
                <option value="true">Yes</option>
              </select>
            </label>
          </div>
          <label>Notes<textarea value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} /></label>
          <div className="row wrap">
            <button type="submit">{editingId ? 'Update Balance' : 'Save Balance'}</button>
            {editingId && (
              <button
                type="button"
                className="secondary"
                onClick={() => {
                  setEditingId(null);
                  setForm({ ...EMPTY_FORM, transaction_date: todayISO() });
                }}
              >
                Cancel Edit
              </button>
            )}
          </div>
        </form>
      </section>

      <section className="section">
        <h2>Open Payments to Receive</h2>
        <ReceivablesTable
          rows={rows}
          onCollect={onCollect}
          renderActions={(row) => (
            <div className="row wrap">
              {can('cashflow.money_in') && Number(row.balance_due || 0) > 0 && (
                <button type="button" className="secondary" onClick={() => onCollect(row)}>Collect</button>
              )}
              {can('cashflow.money_in') && <button type="button" className="secondary" onClick={() => editRow(row)}>Edit</button>}
              {can('cashflow.money_in') && (
                <details className="row-actions-more">
                  <summary>More</summary>
                  {Number(row.balance_due || 0) <= 0 && (
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => runAction(() => reopenReceivable(row.id, { reason: 'Reopened from receivables page' }), `Balance #${row.id} reopened.`)}
                    >
                      Reopen
                    </button>
                  )}
                  {Number(row.balance_due || 0) > 0 && (
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => runAction(() => writeOffReceivable(row.id, { reason: 'Write-off from receivables page' }), `Balance #${row.id} written off.`)}
                    >
                      Write off
                    </button>
                  )}
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => setReverseTarget(row)}
                  >
                    Reverse payment
                  </button>
                </details>
              )}
            </div>
          )}
        />
      </section>

      <SettlementModal
        target={collectionTarget ? {
          name: collectionTarget.counterparty_name || `Receivable #${collectionTarget.id}`,
          type: collectionTarget.receivable_type,
          balance_due: collectionTarget.balance_due,
        } : null}
        title="Receive Payment"
        subtitle="Enter what was received and where the money went."
        accounts={accounts}
        form={collectionForm}
        setForm={setCollectionForm}
        onClose={() => setCollectionTarget(null)}
        onSubmit={submitCollection}
        submitLabel="Receive Payment"
      />
      <InputActionModal
        open={!!reverseTarget}
        title={`Reverse payment for balance #${reverseTarget?.id}?`}
        description="Enter the payment transaction ID. This reverses that collection and recalculates the balance due."
        fieldLabel="Payment transaction ID"
        inputType="number"
        required
        confirmLabel="Reverse Payment"
        onClose={() => setReverseTarget(null)}
        onConfirm={reversePayment}
      />
    </div>
  );
}
