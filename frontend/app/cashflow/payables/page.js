'use client';

import { useEffect, useState } from 'react';
import CashflowTabs from '../../../components/cashflow/CashflowTabs';
import PayablesTable from '../../../components/cashflow/PayablesTable';
import SettlementModal from '../../../components/cashflow/SettlementModal';
import {
  createPayable,
  fetchFinancialAccounts,
  fetchPayables,
  payPayable,
  reopenPayable,
  reversePayablePayment,
  updatePayable,
  writeOffPayable,
} from '../../../lib/cashflowApi';
import { shouldPreventEnterSubmit } from '../../../lib/formBehavior';
import { useCurrentUser } from '../../../lib/useCurrentUser';
import { todayISO } from '../shared';

const EMPTY_FORM = {
  source_type: '',
  source_id: '',
  supplier_name: '',
  payable_type: 'supplier_bill',
  bill_date: todayISO(),
  due_date: '',
  gross_amount: '',
  amount_paid: '0',
  status: 'open',
  notes: '',
  bir_include: false,
};

export default function PayablesPage() {
  const { can } = useCurrentUser();
  const [accounts, setAccounts] = useState([]);
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [paymentTarget, setPaymentTarget] = useState(null);
  const [paymentForm, setPaymentForm] = useState({ amount: '', financial_account_id: '', payment_method: 'cash', reference_no: '', notes: '', auto_post_accounting: false });
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function load() {
    const [accountRows, payableRows] = await Promise.all([
      fetchFinancialAccounts({ only_active: true }),
      fetchPayables({ limit: 400 }),
    ]);
    setAccounts(Array.isArray(accountRows) ? accountRows : []);
    setRows(Array.isArray(payableRows) ? payableRows : []);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || 'Failed to load payables.'));
  }, []);

  async function submit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      const payload = {
        source_type: form.source_type || null,
        source_id: form.source_id ? Number(form.source_id) : null,
        supplier_name: form.supplier_name,
        payable_type: form.payable_type,
        bill_date: form.bill_date,
        due_date: form.due_date || null,
        gross_amount: Number(form.gross_amount || 0),
        amount_paid: Number(form.amount_paid || 0),
        status: form.status,
        notes: form.notes || null,
        bir_include: !!form.bir_include,
      };
      if (editingId) {
        await updatePayable(editingId, payload);
        setNotice('Bill updated.');
      } else {
        await createPayable(payload);
        setNotice('Bill saved.');
      }
      setForm({ ...EMPTY_FORM, bill_date: form.bill_date });
      setEditingId(null);
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save bill.');
    }
  }

  function onPay(row) {
    setError('');
    setPaymentTarget(row);
    setPaymentForm({
      amount: String(row.balance_due || ''),
      financial_account_id: accounts[0]?.id ? String(accounts[0].id) : '',
      payment_method: 'cash',
      reference_no: '',
      notes: `Payment for payable #${row.id}`,
      auto_post_accounting: false,
    });
  }

  async function submitPayment(e) {
    e.preventDefault();
    if (!paymentTarget) return;
    const amount = Number(paymentForm.amount || 0);
    const accountId = Number(paymentForm.financial_account_id || 0);
    if (!Number.isFinite(amount) || amount <= 0) {
      setError('Enter a valid payment amount.');
      return;
    }
    if (!Number.isFinite(accountId) || accountId <= 0) {
      setError('Choose the paying account.');
      return;
    }
    setError('');
    setNotice('');
    try {
      await payPayable(paymentTarget.id, {
        amount,
        payment_date: todayISO(),
        financial_account_id: accountId,
        payment_method: paymentForm.payment_method,
        reference_no: paymentForm.reference_no || null,
        notes: paymentForm.notes || null,
        auto_post_accounting: !!paymentForm.auto_post_accounting,
      });
      setNotice(`Supplier payment posted for ${paymentTarget.supplier_name || `payable #${paymentTarget.id}`}.`);
      setPaymentTarget(null);
      await load();
    } catch (err) {
      setError(err.message || 'Failed to pay payable.');
    }
  }

  function editRow(row) {
    setEditingId(row.id);
    setForm({
      source_type: row.source_type || '',
      source_id: row.source_id ? String(row.source_id) : '',
      supplier_name: row.supplier_name || '',
      payable_type: row.payable_type || 'supplier_bill',
      bill_date: row.bill_date || todayISO(),
      due_date: row.due_date || '',
      gross_amount: row.gross_amount ?? '',
      amount_paid: row.amount_paid ?? '0',
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

  function isSubmittable() {
    return !!(String(form.supplier_name || '').trim() && Number(form.gross_amount || 0) > 0);
  }

  return (
    <div className="stack">
      <CashflowTabs />

      <section className="section">
        <h1>Bills to Pay</h1>
        <p className="muted">Track supplier bills and pay them directly from cash, bank, or e-wallet accounts.</p>
        {editingId ? <p className="small muted">Editing bill #{editingId}</p> : null}
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <section className="section">
        <h2>{editingId ? 'Edit Bill' : 'Add Bill to Pay'}</h2>
        <form onSubmit={submit} onKeyDown={(event) => shouldPreventEnterSubmit(event, isSubmittable)}>
          <div className="form-grid">
            <label>Supplier<input required value={form.supplier_name} onChange={(e) => setForm((f) => ({ ...f, supplier_name: e.target.value }))} /></label>
            <label>Type
              <select value={form.payable_type} onChange={(e) => setForm((f) => ({ ...f, payable_type: e.target.value }))}>
                <option value="supplier_bill">Supplier bill</option>
                <option value="utility_bill">Utility bill</option>
                <option value="payroll_liability">Payroll / government payable</option>
                <option value="tax_liability">Tax payable</option>
                <option value="service_provider_bill">Service provider bill</option>
              </select>
            </label>
            <label>Bill Date<input type="date" value={form.bill_date} onChange={(e) => setForm((f) => ({ ...f, bill_date: e.target.value }))} /></label>
            <label>Due Date<input type="date" value={form.due_date} onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))} /></label>
            <label>Bill Amount<input required type="number" min="0.01" step="0.01" value={form.gross_amount} onChange={(e) => setForm((f) => ({ ...f, gross_amount: e.target.value }))} /></label>
            <label>Already Paid<input type="number" min="0" step="0.01" value={form.amount_paid} onChange={(e) => setForm((f) => ({ ...f, amount_paid: e.target.value }))} /></label>
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
            <button type="submit">{editingId ? 'Update Bill' : 'Save Bill'}</button>
            {editingId && (
              <button
                type="button"
                className="secondary"
                onClick={() => {
                  setEditingId(null);
                  setForm({ ...EMPTY_FORM, bill_date: todayISO() });
                }}
              >
                Cancel Edit
              </button>
            )}
          </div>
        </form>
      </section>

      <section className="section">
        <h2>Open Bills to Pay</h2>
        <PayablesTable
          rows={rows}
          onPay={onPay}
          renderActions={(row) => (
            <div className="row wrap">
              {can('cashflow.money_out') && Number(row.balance_due || 0) > 0 && (
                <button type="button" className="secondary" onClick={() => onPay(row)}>Pay</button>
              )}
              {can('cashflow.money_out') && <button type="button" className="secondary" onClick={() => editRow(row)}>Edit</button>}
              {can('cashflow.money_out') && (
                <details className="row-actions-more">
                  <summary>More</summary>
                  {Number(row.balance_due || 0) <= 0 && (
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => runAction(() => reopenPayable(row.id, { reason: 'Reopened from payables page' }), `Bill #${row.id} reopened.`)}
                    >
                      Reopen
                    </button>
                  )}
                  {Number(row.balance_due || 0) > 0 && (
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => runAction(() => writeOffPayable(row.id, { reason: 'Write-off from payables page' }), `Bill #${row.id} written off.`)}
                    >
                      Write off
                    </button>
                  )}
                  <button
                    type="button"
                    className="secondary"
                    onClick={async () => {
                      const txIdRaw = window.prompt('Payment transaction ID to reverse', '');
                      if (txIdRaw === null) return;
                      const txId = Number(txIdRaw);
                      if (!Number.isFinite(txId) || txId <= 0) {
                        setError('Invalid transaction id.');
                        return;
                      }
                      await runAction(
                        () => reversePayablePayment(row.id, txId, { reason: 'Reversed from payables page' }),
                        `Payment transaction #${txId} reversed.`,
                      );
                    }}
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
        target={paymentTarget ? {
          name: paymentTarget.supplier_name || `Payable #${paymentTarget.id}`,
          type: paymentTarget.payable_type,
          balance_due: paymentTarget.balance_due,
        } : null}
        title="Pay Supplier"
        subtitle="Enter what was paid and where the money came from."
        accounts={accounts}
        form={paymentForm}
        setForm={setPaymentForm}
        onClose={() => setPaymentTarget(null)}
        onSubmit={submitPayment}
        submitLabel="Pay Supplier"
      />
    </div>
  );
}
