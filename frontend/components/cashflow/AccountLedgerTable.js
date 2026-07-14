function money(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

const TYPE_LABELS = {
  transaction: 'Money movement',
  transfer: 'Transfer',
  reconciliation: 'Count / check',
};

export default function AccountLedgerTable({ rows = [], interactive = false }) {
  return (
    <table className="table">
      <thead>
        <tr>
          <th>Date</th>
          <th>Type</th>
          <th>Description</th>
          <th>Reference</th>
          <th>In</th>
          <th>Out</th>
          <th>Balance</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={`${row.entry_type}-${row.entry_id}-${row.date}`} data-entry-type={row.entry_type} data-entry-id={row.entry_id} className={interactive && row.entry_type === 'money_transaction' ? 'clickable-row' : ''}>
            <td>{row.date}</td>
            <td>{TYPE_LABELS[row.entry_type] || row.entry_type}</td>
            <td>{row.description}</td>
            <td>{row.reference_no || '-'}</td>
            <td>P{money(row.debit)}</td>
            <td>P{money(row.credit)}</td>
            <td><strong>P{money(row.running_balance)}</strong></td>
          </tr>
        ))}
        {!rows.length && (
          <tr><td colSpan="7" className="muted">No account history yet.</td></tr>
        )}
      </tbody>
    </table>
  );
}
