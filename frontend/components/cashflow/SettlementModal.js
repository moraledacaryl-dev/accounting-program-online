'use client';

const PAYMENT_METHODS = [
  ['cash', 'Cash'],
  ['gcash', 'GCash'],
  ['card', 'Card'],
  ['bank_transfer', 'Bank Transfer'],
  ['ota_payout', 'OTA Payout'],
];

function money(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

const TYPE_LABELS = {
  guest_balance: 'Guest balance',
  ota_receivable: 'OTA receivable',
  event_balance: 'Event balance',
  corporate_receivable: 'Company / group billing',
  supplier_bill: 'Supplier bill',
  utility_bill: 'Utility bill',
  payroll_liability: 'Payroll / government payable',
  tax_liability: 'Tax payable',
  service_provider_bill: 'Service provider bill',
};

export default function SettlementModal({
  target,
  title,
  subtitle,
  accounts = [],
  form,
  setForm,
  onClose,
  onSubmit,
  submitLabel = 'Save',
}) {
  if (!target) return null;

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2>{title}</h2>
            <p className="muted">{subtitle}</p>
          </div>
          <button type="button" className="secondary" onClick={onClose}>Close</button>
        </div>
        <form className="modal-form stack" onSubmit={onSubmit}>
          <section className="card">
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <div>
                <strong>{target.name}</strong>
                <div className="small muted">{TYPE_LABELS[target.type] || target.type || 'Open balance'}</div>
              </div>
              <div className="text-right">
                <div className="small muted">Remaining balance</div>
                <strong>P{money(target.balance_due)}</strong>
              </div>
            </div>
          </section>

          <div className="form-grid">
            <label>Amount
              <input
                required
                type="number"
                min="0.01"
                step="0.01"
                value={form.amount}
                onChange={(e) => setForm((prev) => ({ ...prev, amount: e.target.value }))}
              />
            </label>
            <label>Account
              <select
                required
                value={form.financial_account_id}
                onChange={(e) => setForm((prev) => ({ ...prev, financial_account_id: e.target.value }))}
              >
                <option value="">Select account</option>
                {accounts.map((row) => (
                  <option key={row.id} value={row.id}>{row.code} · {row.name}</option>
                ))}
              </select>
            </label>
            <label>Method
              <select value={form.payment_method} onChange={(e) => setForm((prev) => ({ ...prev, payment_method: e.target.value }))}>
                {PAYMENT_METHODS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label>Reference
              <input value={form.reference_no} onChange={(e) => setForm((prev) => ({ ...prev, reference_no: e.target.value }))} placeholder="OR, check, bank ref" />
            </label>
          </div>

          <label>Note
            <textarea value={form.notes} onChange={(e) => setForm((prev) => ({ ...prev, notes: e.target.value }))} />
          </label>

          <details className="quiet-details">
            <summary>Accounting options</summary>
            <label>Posting
              <select value={String(form.auto_post_accounting)} onChange={(e) => setForm((prev) => ({ ...prev, auto_post_accounting: e.target.value === 'true' }))}>
                <option value="false">Save payment first</option>
                <option value="true">Post accounting now</option>
              </select>
            </label>
          </details>

          <div className="row wrap" style={{ justifyContent: 'flex-end' }}>
            <button type="button" className="secondary" onClick={onClose}>Cancel</button>
            <button type="submit">{submitLabel}</button>
          </div>
        </form>
      </div>
    </div>
  );
}
