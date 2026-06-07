'use client';

import { Suspense, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import CashflowTabs from '../../../components/cashflow/CashflowTabs';
import MoneyInForm from '../../../components/cashflow/MoneyInForm';
import TemplatePicker from '../../../components/cashflow/TemplatePicker';
import PaymentMethodBadge from '../../../components/cashflow/PaymentMethodBadge';
import ConfirmActionModal from '../../../components/ConfirmActionModal';
import {
  approveMoneyTransaction,
  cancelMoneyTransaction,
  createMoneyTransaction,
  deleteMoneyTransaction,
  fetchCashflowTemplates,
  fetchFinancialAccounts,
  fetchMoneyTransactions,
  fetchReceivables,
  reverseMoneyTransaction,
  updateMoneyTransaction,
} from '../../../lib/cashflowApi';
import { fetchModuleTaxonomy, uploadAttachment } from '../../../lib/api';
import { useCurrentUser } from '../../../lib/useCurrentUser';
import { money, todayISO } from '../shared';

const PRESETS = {
  'room-payment': { module: 'rooms', category: 'Cash', subcategory: 'Cash Movements', level3_item: 'Cash In' },
  'restaurant-income': { module: 'restaurant', category: 'Cash', subcategory: 'Cash Movements', level3_item: 'Cash In' },
  'other-income': { module: 'other_income', category: 'Cash', subcategory: 'Cash Movements', level3_item: 'Cash In' },
};

const EMPTY_FORM = {
  transaction_date: todayISO(),
  direction: 'in',
  financial_account_id: '',
  module: 'finance',
  category: 'Cash',
  subcategory: 'Cash Movements',
  level3_item: 'Cash In',
  amount: '',
  payment_method: 'cash',
  reference_no: '',
  counterparty_name: '',
  notes: '',
  receivable_id: '',
  bir_include: false,
  auto_post_accounting: false,
  attachment_file: null,
};

const STATUS_LABELS = {
  draft: 'Draft',
  approved: 'Approved',
  cancelled: 'Cancelled',
  reversed: 'Reversed',
  posted: 'Posted',
};

function MoneyInContent() {
  const { can } = useCurrentUser();
  const searchParams = useSearchParams();
  const [accounts, setAccounts] = useState([]);
  const [financeTaxonomy, setFinanceTaxonomy] = useState({});
  const [receivables, setReceivables] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [templateId, setTemplateId] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [pendingAction, setPendingAction] = useState(null);

  const templateMap = useMemo(() => Object.fromEntries(templates.map((t) => [String(t.id), t])), [templates]);

  async function load() {
    const [accountsData, taxData, receivableData, txRows, templateRows] = await Promise.all([
      fetchFinancialAccounts({ only_active: true }),
      fetchModuleTaxonomy('finance'),
      fetchReceivables({ limit: 300 }),
      fetchMoneyTransactions({ direction: 'in', start_date: todayISO(), end_date: todayISO(), limit: 200 }),
      fetchCashflowTemplates({ active_only: true }),
    ]);
    setAccounts(Array.isArray(accountsData) ? accountsData : []);
    setFinanceTaxonomy(taxData || {});
    setReceivables(Array.isArray(receivableData) ? receivableData : []);
    setRows(Array.isArray(txRows) ? txRows : []);
    setTemplates((Array.isArray(templateRows) ? templateRows : []).filter((t) => t.direction === 'in'));
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || 'Failed to load money-in page.'));
  }, []);

  useEffect(() => {
    const preset = searchParams.get('preset');
    if (!preset || !PRESETS[preset]) return;
    const patch = PRESETS[preset];
    setForm((f) => ({ ...f, ...patch }));
  }, [searchParams]);

  async function submit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      const payload = {
        transaction_date: form.transaction_date,
        direction: 'in',
        financial_account_id: Number(form.financial_account_id),
        module: form.module,
        category: form.category,
        subcategory: form.subcategory,
        level3_item: form.level3_item,
        amount: Number(form.amount || 0),
        payment_method: form.payment_method || null,
        reference_no: form.reference_no || null,
        counterparty_name: form.counterparty_name || null,
        notes: form.notes || null,
        receivable_id: form.receivable_id ? Number(form.receivable_id) : null,
        bir_include: !!form.bir_include,
        auto_post_accounting: !!form.auto_post_accounting,
      };
      const created = editingId
        ? await updateMoneyTransaction(editingId, payload)
        : await createMoneyTransaction(payload);
      if (!editingId && form.attachment_file && created?.id) {
        await uploadAttachment({
          file: form.attachment_file,
          entityType: 'money_transaction',
          entityId: created.id,
          note: form.notes || `Money-in attachment ${created.id}`,
        });
      }
      setNotice(editingId ? 'Money in record updated.' : 'Money in record saved.');
      setForm({ ...EMPTY_FORM, transaction_date: form.transaction_date });
      setEditingId(null);
      setTemplateId('');
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save money in record.');
    }
  }

  function startEdit(row) {
    setEditingId(row.id);
    setForm({
      ...EMPTY_FORM,
      transaction_date: row.transaction_date || todayISO(),
      financial_account_id: row.financial_account_id ? String(row.financial_account_id) : '',
      module: row.module || 'finance',
      category: row.category || 'Cash',
      subcategory: row.subcategory || 'Cash Movements',
      level3_item: row.level3_item || 'Cash In',
      amount: row.amount ?? '',
      payment_method: row.payment_method || 'cash',
      reference_no: row.reference_no || '',
      counterparty_name: row.counterparty_name || '',
      notes: row.notes || '',
      receivable_id: row.receivable_id ? String(row.receivable_id) : '',
      bir_include: !!row.bir_include,
      attachment_file: null,
    });
  }

  async function confirmPendingAction(reason) {
    const action = pendingAction;
    if (!action) return;
    setError('');
    setNotice('');
    try {
      await action.work(reason);
      setNotice(action.successMessage);
      await load();
    } catch (err) {
      setError(err.message || 'Action failed.');
      throw err;
    }
  }

  return (
    <div className="stack">
      <CashflowTabs />

      <section className="section">
        <h1>Money In</h1>
        <p className="muted">Record money received, link it to an open balance when needed, and attach proof if available.</p>
        {editingId ? <p className="small muted">Editing money in record #{editingId}</p> : null}
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <section className="section">
        <div className="form-grid">
          <TemplatePicker templates={templates} value={templateId} onChange={(value) => {
            setTemplateId(value);
            const tpl = templateMap[value];
            if (!tpl) return;
            setForm((f) => ({
              ...f,
              module: tpl.default_module || f.module,
              category: tpl.default_category || f.category,
              subcategory: tpl.default_subcategory || f.subcategory,
              level3_item: tpl.default_level3_item || f.level3_item,
              financial_account_id: tpl.default_account_id ? String(tpl.default_account_id) : f.financial_account_id,
              payment_method: tpl.default_payment_method || f.payment_method,
              bir_include: !!tpl.default_bir_include,
              notes: tpl.default_notes || f.notes,
            }));
          }} />
        </div>
      </section>

      <MoneyInForm
        accounts={accounts}
        financeTaxonomy={financeTaxonomy}
        form={form}
        setForm={setForm}
        receivables={receivables}
        onSubmit={submit}
        submitLabel={editingId ? 'Update Money In' : 'Save Money In'}
      />

      {editingId ? (
        <section className="section">
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
        </section>
      ) : null}

      <section className="section">
        <h2>Today's Money In</h2>
        <table className="table">
          <thead><tr><th>Date</th><th>Account</th><th>Area</th><th>Reason</th><th>Amount</th><th>Method</th><th>Status</th><th>Reference</th><th></th></tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.transaction_date}</td>
                <td>{row.financial_account_code} · {row.financial_account_name}</td>
                <td>{row.module}</td>
                <td>{row.category || '-'} / {row.subcategory || '-'}</td>
                <td>P{money(row.amount)}</td>
                <td><PaymentMethodBadge method={row.payment_method} /></td>
                <td>{STATUS_LABELS[row.status] || row.status || '-'}</td>
                <td>{row.reference_no || '-'}</td>
                <td className="row wrap">
                  {(can('cashflow.money_in') || can('cashflow.money_out')) && (
                    <>
                      <button type="button" className="secondary" onClick={() => startEdit(row)}>Edit</button>
                      <details className="row-actions-more">
                        <summary>More</summary>
                        <button type="button" className="secondary" onClick={() => setPendingAction({ title: `Approve money-in record #${row.id}?`, description: 'Confirm this received amount and destination account are correct.', confirmLabel: 'Approve record', tone: 'normal', work: () => approveMoneyTransaction(row.id, {}), successMessage: `Record #${row.id} approved.` })}>Approve</button>
                        <button type="button" className="danger" onClick={() => setPendingAction({ title: `Cancel money-in record #${row.id}?`, description: 'This remains visible in the audit trail. Record why it should be cancelled.', confirmLabel: 'Cancel record', reasonRequired: true, work: (reason) => cancelMoneyTransaction(row.id, { reason }), successMessage: `Record #${row.id} cancelled.` })}>Cancel</button>
                        <button type="button" className="danger" onClick={() => setPendingAction({ title: `Reverse money-in record #${row.id}?`, description: 'This changes the account balance and remains visible in the audit trail.', confirmLabel: 'Reverse record', reasonRequired: true, work: (reason) => reverseMoneyTransaction(row.id, { reason }), successMessage: `Record #${row.id} reversed.` })}>Reverse</button>
                        <button type="button" className="danger" onClick={() => setPendingAction({ title: `Delete draft money-in record #${row.id}?`, description: 'Only unposted drafts can be deleted. Posted records must be reversed.', confirmLabel: 'Delete draft', work: () => deleteMoneyTransaction(row.id), successMessage: `Record #${row.id} deleted.` })}>Delete</button>
                      </details>
                    </>
                  )}
                </td>
              </tr>
            ))}
            {!rows.length && <tr><td colSpan="9" className="muted">No money-in records for today.</td></tr>}
          </tbody>
        </table>
      </section>
      <ConfirmActionModal
        open={!!pendingAction}
        title={pendingAction?.title}
        description={pendingAction?.description}
        confirmLabel={pendingAction?.confirmLabel}
        tone={pendingAction?.tone || 'danger'}
        reasonRequired={!!pendingAction?.reasonRequired}
        onClose={() => setPendingAction(null)}
        onConfirm={confirmPendingAction}
      />
    </div>
  );
}

export default function MoneyInPage() {
  return (
    <Suspense fallback={<div className="stack"><CashflowTabs /></div>}>
      <MoneyInContent />
    </Suspense>
  );
}
