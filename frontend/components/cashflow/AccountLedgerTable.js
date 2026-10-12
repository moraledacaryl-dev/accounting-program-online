function money(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function when(row) {
  const value = row.movement_at || row.date;
  if (!value || value === 'opening') return value || '-';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime()) || !String(value).includes('T')) return value;
  return parsed.toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

export default function AccountLedgerTable({ rows = [], interactive = false, showAccount = false }) {
  return (
    <div className="ledger-table-wrap">
      <table className="table ledger-table">
        <thead><tr><th>Date & Time</th>{showAccount && <th>Account</th>}<th>Details</th><th>Reference</th><th>In</th><th>Out</th><th>Balance</th></tr></thead>
        <tbody>
          {rows.map((row) => {
            const recon = row.entry_type === 'cash_reconciliation';
            const meta = row.meta || {};
            return (
              <tr key={`${row.account_id||''}-${row.entry_type}-${row.entry_id}-${row.date}`} data-entry-type={row.entry_type} data-entry-id={row.entry_id} className={recon ? 'ledger-reconciliation-row' : (interactive && row.entry_type === 'money_transaction' ? 'clickable-row' : '')}>
                <td data-label="Date & Time">{when(row)}</td>
                {showAccount && <td data-label="Account"><strong>{row.account_name || '-'}</strong></td>}
                <td data-label="Details">{recon ? <><strong>{meta.status === 'closed' ? 'Day closed & reconciled' : 'Reconciliation / close'}</strong><small className="ledger-row-meta">{row.included_movement_count || 0} movements included · variance P{money(meta.variance)}</small></> : <><span>{row.description || '-'}</span><small className="ledger-row-meta">{meta.counterparty_name || meta.payment_method || meta.module || ''}</small></>}</td>
                <td data-label="Reference">{row.reference_no || '-'}</td>
                <td data-label="In">{recon ? '-' : `P${money(row.debit)}`}</td>
                <td data-label="Out">{recon ? '-' : `P${money(row.credit)}`}</td>
                <td data-label="Balance"><strong>P{money(row.running_balance)}</strong></td>
              </tr>
            );
          })}
          {!rows.length && <tr><td colSpan={showAccount ? 7 : 6} className="muted">No ledger activity matches these filters.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}
