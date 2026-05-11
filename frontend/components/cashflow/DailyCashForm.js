import AccountSelector from './AccountSelector';
import CashVarianceBadge from './CashVarianceBadge';
import { shouldPreventEnterSubmit } from '../../lib/formBehavior';

function money(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function DailyCashForm({ accounts = [], form, setForm, preview = null, onSubmit }) {
  return (
    <form
      onSubmit={onSubmit}
      className="stack"
      onKeyDown={(event) => shouldPreventEnterSubmit(
        event,
        () => !!(
          Number(form.financial_account_id || 0) > 0
          && !!form.reconciliation_date
          && Number.isFinite(Number(form.actual_counted))
        ),
      )}
    >
      <div className="form-grid">
        <AccountSelector
          label="Account"
          required
          accounts={accounts}
          value={form.financial_account_id}
          onChange={(value) => setForm((f) => ({ ...f, financial_account_id: value }))}
        />
        <label>
          Date
          <input required type="date" value={form.reconciliation_date} onChange={(e) => setForm((f) => ({ ...f, reconciliation_date: e.target.value }))} />
        </label>
        <label>
          Shift
          <input value={form.shift_name} onChange={(e) => setForm((f) => ({ ...f, shift_name: e.target.value }))} placeholder="Day / Night" />
        </label>
        <label>
          Counted Amount
          <input required type="number" step="0.01" value={form.actual_counted} onChange={(e) => setForm((f) => ({ ...f, actual_counted: e.target.value }))} />
        </label>
        <label>
          Status
          <select value={form.status} onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}>
            <option value="open">Open</option>
            <option value="counted">Counted</option>
            <option value="reviewed">Reviewed</option>
            <option value="closed">Closed</option>
            <option value="discrepancy_flagged">Difference needs review</option>
          </select>
        </label>
      </div>
      {preview && (
        <div className="card">
          <div className="row wrap">
            <span className="small muted">Opening: P{money(preview.opening_balance)}</span>
            <span className="small muted">Expected In: P{money(preview.expected_in)}</span>
            <span className="small muted">Expected Out: P{money(preview.expected_out)}</span>
            <span className="small muted">Expected: P{money(preview.expected_closing)}</span>
            <CashVarianceBadge variance={preview.variance} />
          </div>
        </div>
      )}
      <label>
        Notes
        <textarea value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} />
      </label>
      <button type="submit">Save Count</button>
    </form>
  );
}
