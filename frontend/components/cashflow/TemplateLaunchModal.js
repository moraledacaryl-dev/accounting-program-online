import PaymentMethodSelect from './PaymentMethodSelect';
import ToggleField from './ToggleField';
import { shouldPreventEnterSubmit } from '../../lib/formBehavior';

export default function TemplateLaunchModal({
  template = null,
  accounts = [],
  form,
  setForm,
  onClose,
  onSubmit,
  submitting = false,
}) {
  if (!template) return null;

  function isSubmittable() {
    return !!(Number(form.financial_account_id || 0) > 0 && Number(form.amount || 0) > 0 && form.transaction_date);
  }

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="modal-card modal-card-medium" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2>Launch Template</h2>
            <p className="muted small">
              {template.name} · {template.direction === 'in' ? 'money in' : 'money out'} · {template.default_module || 'finance'}
            </p>
          </div>
          <button className="secondary" type="button" onClick={onClose}>Close</button>
        </div>

        <form onSubmit={onSubmit} className="stack modal-form" onKeyDown={(event) => shouldPreventEnterSubmit(event, isSubmittable)}>
          <div className="form-grid">
            <label>
              Amount
              <input
                required
                type="number"
                min="0.01"
                step="0.01"
                value={form.amount}
                onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
              />
            </label>
            <label>
              Account
              <select
                required
                value={form.financial_account_id}
                onChange={(e) => setForm((f) => ({ ...f, financial_account_id: e.target.value }))}
              >
                <option value="">Select account</option>
                {accounts.map((row) => (
                  <option key={row.id} value={row.id}>{row.code} · {row.name}</option>
                ))}
              </select>
            </label>
            <label>
              Date
              <input
                required
                type="date"
                value={form.transaction_date}
                onChange={(e) => setForm((f) => ({ ...f, transaction_date: e.target.value }))}
              />
            </label>
            <PaymentMethodSelect
              value={form.payment_method}
              onChange={(value) => setForm((f) => ({ ...f, payment_method: value }))}
            />
            <label>
              Counterparty
              <input
                value={form.counterparty_name}
                onChange={(e) => setForm((f) => ({ ...f, counterparty_name: e.target.value }))}
                placeholder="Supplier, guest, company, etc."
              />
            </label>
            <label>
              Reference No
              <input
                value={form.reference_no}
                onChange={(e) => setForm((f) => ({ ...f, reference_no: e.target.value }))}
                placeholder="OR / PR / check no."
              />
            </label>
            <ToggleField
              label="Auto Post Accounting"
              checked={!!form.auto_post_accounting}
              onChange={(value) => setForm((f) => ({ ...f, auto_post_accounting: value }))}
              hint="Set to Yes to create the accounting entry immediately."
            />
          </div>

          <label>
            Notes
            <textarea value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} />
          </label>

          <div className="row wrap">
            <button type="submit" disabled={submitting}>{submitting ? 'Posting...' : 'Post Transaction'}</button>
            <button className="secondary" type="button" onClick={onClose} disabled={submitting}>Cancel</button>
          </div>
        </form>
      </div>
    </div>
  );
}
