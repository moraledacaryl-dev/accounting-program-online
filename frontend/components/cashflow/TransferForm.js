import AccountSelector from './AccountSelector';
import ToggleField from './ToggleField';
import { shouldPreventEnterSubmit } from '../../lib/formBehavior';

export default function TransferForm({ accounts = [], form, setForm, onSubmit }) {
  return (
    <form
      onSubmit={onSubmit}
      className="stack"
      onKeyDown={(event) => shouldPreventEnterSubmit(
        event,
        () => !!(
          form.transfer_date
          && Number(form.from_account_id || 0) > 0
          && Number(form.to_account_id || 0) > 0
          && Number(form.amount || 0) > 0
          && Number(form.from_account_id || 0) !== Number(form.to_account_id || 0)
        ),
      )}
    >
      <div className="form-grid">
        <label>
          Date
          <input type="date" value={form.transfer_date} onChange={(e) => setForm((f) => ({ ...f, transfer_date: e.target.value }))} />
        </label>
        <AccountSelector
          label="From"
          required
          accounts={accounts}
          value={form.from_account_id}
          onChange={(value) => setForm((f) => ({ ...f, from_account_id: value }))}
        />
        <AccountSelector
          label="To"
          required
          accounts={accounts}
          value={form.to_account_id}
          onChange={(value) => setForm((f) => ({ ...f, to_account_id: value }))}
        />
        <label>
          Amount
          <input required type="number" min="0.01" step="0.01" value={form.amount} onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))} />
        </label>
        <label>
          Reference
          <input value={form.reference_no} onChange={(e) => setForm((f) => ({ ...f, reference_no: e.target.value }))} />
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
      <button type="submit">Save Transfer</button>
    </form>
  );
}
