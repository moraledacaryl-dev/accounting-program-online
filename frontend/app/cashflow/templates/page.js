'use client';

import { useEffect, useState } from 'react';
import CashflowTabs from '../../../components/cashflow/CashflowTabs';
import PaymentMethodSelect from '../../../components/cashflow/PaymentMethodSelect';
import TemplateLaunchModal from '../../../components/cashflow/TemplateLaunchModal';
import ToggleField from '../../../components/cashflow/ToggleField';
import { useConfirmAction } from '../../../components/ConfirmActionProvider';
import {
  createCashflowTemplate,
  deleteCashflowTemplate,
  fetchCashflowTemplates,
  fetchFinancialAccounts,
  launchCashflowTemplate,
  updateCashflowTemplate,
} from '../../../lib/cashflowApi';
import { shouldPreventEnterSubmit } from '../../../lib/formBehavior';
import { todayISO } from '../shared';

const EMPTY_FORM = {
  name: '',
  direction: 'in',
  default_module: 'finance',
  default_category: '',
  default_subcategory: '',
  default_level3_item: '',
  default_account_id: '',
  default_payment_method: 'cash',
  default_bir_include: false,
  default_notes: '',
  is_active: true,
};

export default function CashflowTemplatesPage() {
  const confirmAction = useConfirmAction();
  const [accounts, setAccounts] = useState([]);
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [editingId, setEditingId] = useState(null);
  const [launchTarget, setLaunchTarget] = useState(null);
  const [launchSubmitting, setLaunchSubmitting] = useState(false);
  const [launchForm, setLaunchForm] = useState({
    amount: '',
    financial_account_id: '',
    transaction_date: todayISO(),
    payment_method: 'cash',
    reference_no: '',
    counterparty_name: '',
    notes: '',
    auto_post_accounting: false,
  });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function load() {
    const [accountRows, templateRows] = await Promise.all([
      fetchFinancialAccounts({ only_active: true }),
      fetchCashflowTemplates(),
    ]);
    setAccounts(Array.isArray(accountRows) ? accountRows : []);
    setRows(Array.isArray(templateRows) ? templateRows : []);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || 'Failed to load templates.'));
  }, []);

  useEffect(() => {
    if (!launchTarget || typeof document === 'undefined') return undefined;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previous;
    };
  }, [launchTarget]);

  function beginEdit(row) {
    setEditingId(row.id);
    setForm({
      name: row.name || '',
      direction: row.direction || 'in',
      default_module: row.default_module || 'finance',
      default_category: row.default_category || '',
      default_subcategory: row.default_subcategory || '',
      default_level3_item: row.default_level3_item || '',
      default_account_id: row.default_account_id ? String(row.default_account_id) : '',
      default_payment_method: row.default_payment_method || 'cash',
      default_bir_include: !!row.default_bir_include,
      default_notes: row.default_notes || '',
      is_active: !!row.is_active,
    });
  }

  function resetForm() {
    setEditingId(null);
    setForm({ ...EMPTY_FORM });
  }

  async function submit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      const payload = {
        ...form,
        default_account_id: form.default_account_id ? Number(form.default_account_id) : null,
      };
      if (editingId) {
        await updateCashflowTemplate(editingId, payload);
        setNotice(`Template #${editingId} updated.`);
      } else {
        await createCashflowTemplate(payload);
        setNotice('Template created.');
      }
      resetForm();
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save template.');
    }
  }

  async function removeTemplate(id) {
    if (!await confirmAction({ title: `Delete template #${id}?`, description: 'Existing cashflow transactions are preserved. This removes the shortcut for future entries.' })) return;
    setError('');
    setNotice('');
    try {
      await deleteCashflowTemplate(id);
      setNotice(`Template #${id} deleted.`);
      await load();
    } catch (err) {
      setError(err.message || 'Failed to delete template.');
    }
  }

  function launchTemplate(row) {
    const defaultAccountId = row.default_account_id ? String(row.default_account_id) : (accounts[0]?.id ? String(accounts[0].id) : '');
    setLaunchTarget(row);
    setLaunchForm({
      amount: '',
      financial_account_id: defaultAccountId,
      transaction_date: todayISO(),
      payment_method: row.default_payment_method || 'cash',
      reference_no: '',
      counterparty_name: '',
      notes: row.default_notes || '',
      auto_post_accounting: false,
    });
  }

  function closeLaunchModal() {
    if (launchSubmitting) return;
    setLaunchTarget(null);
  }

  async function submitLaunchTemplate(e) {
    e.preventDefault();
    if (!launchTarget) return;

    const amount = Number(launchForm.amount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setError('Amount must be greater than zero.');
      return;
    }
    const accountId = Number(launchForm.financial_account_id);
    if (!Number.isFinite(accountId) || accountId <= 0) {
      setError('Please select a valid account.');
      return;
    }

    setError('');
    setNotice('');
    setLaunchSubmitting(true);
    try {
      await launchCashflowTemplate({
        template_id: launchTarget.id,
        overrides: {
          amount,
          financial_account_id: accountId,
          transaction_date: launchForm.transaction_date || todayISO(),
          payment_method: launchForm.payment_method || '',
          reference_no: launchForm.reference_no || '',
          counterparty_name: launchForm.counterparty_name || '',
          notes: launchForm.notes || '',
          auto_post_accounting: !!launchForm.auto_post_accounting,
        },
      });
      setNotice(`Template "${launchTarget.name}" launched.`);
      setLaunchTarget(null);
    } catch (err) {
      setError(err.message || 'Failed to launch template.');
    } finally {
      setLaunchSubmitting(false);
    }
  }

  function isTemplateSubmittable() {
    return !!String(form.name || '').trim();
  }

  return (
    <div className="stack">
      <CashflowTabs />

      <section className="section">
        <h1>Cashflow Templates</h1>
        <p className="muted">Build quick entry presets for repeated money-in/money-out operations.</p>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <section className="section">
        <h2>{editingId ? `Edit Template #${editingId}` : 'Create Template'}</h2>
        <form onSubmit={submit} onKeyDown={(event) => shouldPreventEnterSubmit(event, isTemplateSubmittable)}>
          <div className="form-grid">
            <label>Name<input required value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} /></label>
            <label>Direction
              <select value={form.direction} onChange={(e) => setForm((f) => ({ ...f, direction: e.target.value }))}>
                <option value="in">money in</option>
                <option value="out">money out</option>
              </select>
            </label>
            <label>Default Module<input value={form.default_module} onChange={(e) => setForm((f) => ({ ...f, default_module: e.target.value }))} /></label>
            <label>Default Category<input value={form.default_category} onChange={(e) => setForm((f) => ({ ...f, default_category: e.target.value }))} /></label>
            <label>Default Subcategory<input value={form.default_subcategory} onChange={(e) => setForm((f) => ({ ...f, default_subcategory: e.target.value }))} /></label>
            <label>Default Level3<input value={form.default_level3_item} onChange={(e) => setForm((f) => ({ ...f, default_level3_item: e.target.value }))} /></label>
            <label>Default Account
              <select value={form.default_account_id} onChange={(e) => setForm((f) => ({ ...f, default_account_id: e.target.value }))}>
                <option value="">Select</option>
                {accounts.map((row) => <option key={row.id} value={row.id}>{row.code} · {row.name}</option>)}
              </select>
            </label>
            <PaymentMethodSelect
              label="Default Payment Method"
              value={form.default_payment_method}
              onChange={(value) => setForm((f) => ({ ...f, default_payment_method: value }))}
            />
            <ToggleField
              label="BIR Include by Default"
              checked={!!form.default_bir_include}
              onChange={(value) => setForm((f) => ({ ...f, default_bir_include: value }))}
              hint="Set to Yes if this template is usually BIR-included."
            />
            <ToggleField
              label="Template Active"
              checked={!!form.is_active}
              onChange={(value) => setForm((f) => ({ ...f, is_active: value }))}
              hint="Set to No to keep template for history only."
            />
          </div>
          <label>Default Notes<textarea value={form.default_notes} onChange={(e) => setForm((f) => ({ ...f, default_notes: e.target.value }))} /></label>
          <div className="row wrap">
            <button type="submit">{editingId ? 'Update Template' : 'Create Template'}</button>
            {editingId && <button className="secondary" type="button" onClick={resetForm}>Cancel</button>}
          </div>
        </form>
      </section>

      <section className="section">
        <h2>Template List</h2>
        <table className="table">
          <thead><tr><th>Name</th><th>Direction</th><th>Module</th><th>Default Account</th><th>Active</th><th></th></tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.name}</td>
                <td>{row.direction}</td>
                <td>{row.default_module}</td>
                <td>{row.default_account_name || '-'}</td>
                <td>{row.is_active ? 'Yes' : 'No'}</td>
                <td className="row wrap">
                  <button className="secondary" type="button" onClick={() => launchTemplate(row)}>Launch</button>
                  <button className="secondary" type="button" onClick={() => beginEdit(row)}>Edit</button>
                  <button className="secondary" type="button" onClick={() => removeTemplate(row.id)}>Delete</button>
                </td>
              </tr>
            ))}
            {!rows.length && <tr><td colSpan="6" className="muted">No templates yet.</td></tr>}
          </tbody>
        </table>
      </section>

      <TemplateLaunchModal
        template={launchTarget}
        accounts={accounts}
        form={launchForm}
        setForm={setLaunchForm}
        onClose={closeLaunchModal}
        onSubmit={submitLaunchTemplate}
        submitting={launchSubmitting}
      />
    </div>
  );
}
