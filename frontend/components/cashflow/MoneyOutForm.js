import AccountSelector from './AccountSelector';
import CategorySubcategoryPicker from './CategorySubcategoryPicker';
import PaymentMethodSelect from './PaymentMethodSelect';
import SourceModuleSelect from './SourceModuleSelect';
import JournalImpactPreview from './JournalImpactPreview';
import ToggleField from './ToggleField';
import { shouldPreventEnterSubmit } from '../../lib/formBehavior';

export default function MoneyOutForm({
  accounts = [],
  financeTaxonomy = {},
  form,
  setForm,
  payables = [],
  onSubmit,
  submitLabel = 'Save Money Out',
}) {
  return (
    <div className="grid">
      <section className="section">
        <form
          onSubmit={onSubmit}
          className="stack"
          onKeyDown={(event) => shouldPreventEnterSubmit(
            event,
            () => !!(form.transaction_date && Number(form.financial_account_id || 0) > 0 && Number(form.amount || 0) > 0),
          )}
        >
          <div className="form-grid">
            <label>
              Date
              <input required type="date" value={form.transaction_date} onChange={(e) => setForm((f) => ({ ...f, transaction_date: e.target.value }))} />
            </label>
            <AccountSelector
              required
              accounts={accounts}
              value={form.financial_account_id}
              onChange={(value) => setForm((f) => ({ ...f, financial_account_id: value }))}
            />
            <SourceModuleSelect value={form.module} onChange={(value) => setForm((f) => ({ ...f, module: value }))} label="Area" />
            <CategorySubcategoryPicker
              taxonomy={financeTaxonomy}
              category={form.category}
              subcategory={form.subcategory}
              level3Item={form.level3_item}
              onCategoryChange={(value) => setForm((f) => ({ ...f, category: value, subcategory: '', level3_item: '' }))}
              onSubcategoryChange={(value) => setForm((f) => ({ ...f, subcategory: value, level3_item: '' }))}
              onLevel3ItemChange={(value) => setForm((f) => ({ ...f, level3_item: value }))}
            />
            <label>
              Amount
              <input required type="number" min="0.01" step="0.01" value={form.amount} onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))} />
            </label>
            <PaymentMethodSelect value={form.payment_method} onChange={(value) => setForm((f) => ({ ...f, payment_method: value }))} />
            <label>
              Payee / Supplier
              <input value={form.counterparty_name} onChange={(e) => setForm((f) => ({ ...f, counterparty_name: e.target.value }))} />
            </label>
            <label>
              Reference No
              <input value={form.reference_no} onChange={(e) => setForm((f) => ({ ...f, reference_no: e.target.value }))} />
            </label>
            <label>
              Linked Payable
              <select value={form.payable_id} onChange={(e) => setForm((f) => ({ ...f, payable_id: e.target.value }))}>
                <option value="">Select</option>
                {payables.filter((r) => Number(r.balance_due || 0) > 0).map((row) => (
                  <option key={row.id} value={row.id}>#{row.id} · {row.supplier_name} · Bal {row.balance_due}</option>
                ))}
              </select>
            </label>
            <ToggleField
              label="Include in BIR"
              checked={!!form.bir_include}
              onChange={(value) => setForm((f) => ({ ...f, bir_include: value }))}
              hint="Set to Yes only for entries intended for BIR output."
            />
            <label>
              Attachment
              <input type="file" onChange={(e) => setForm((f) => ({ ...f, attachment_file: e.target.files?.[0] || null }))} />
            </label>
          </div>
          <details className="quiet-details">
            <summary>Accounting options</summary>
            <ToggleField
              label="Post accounting now"
              checked={!!form.auto_post_accounting}
              onChange={(value) => setForm((f) => ({ ...f, auto_post_accounting: value }))}
              hint="Usually No until manager/accounting review."
            />
          </details>
          <label>
            Notes
            <textarea value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} />
          </label>
          <button type="submit">{submitLabel}</button>
        </form>
      </section>

      <JournalImpactPreview direction="out" amount={form.amount} paymentMethod={form.payment_method} />
    </div>
  );
}
