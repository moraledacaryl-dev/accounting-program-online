function money(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

const TYPE_LABELS = {
  guest_balance: 'Guest',
  ota_receivable: 'OTA',
  event_balance: 'Event',
  corporate_receivable: 'Company / group',
};

const STATUS_LABELS = {
  open: 'Open',
  partial: 'Part paid',
  settled: 'Paid',
  written_off: 'Written off',
};

export default function ReceivablesTable({ rows = [], onCollect, renderActions = null }) {
  const hasCustomActions = typeof renderActions === 'function';
  return (
    <table className="table">
      <thead>
        <tr>
          <th>Date</th>
          <th>Type</th>
          <th>Customer / Source</th>
          <th>Total</th>
          <th>Collected</th>
          <th>Balance</th>
          <th>Due</th>
          <th>Status</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <td>{row.transaction_date}</td>
            <td>{TYPE_LABELS[row.receivable_type] || row.receivable_type || '-'}</td>
            <td>{row.counterparty_name}</td>
            <td>P{money(row.gross_amount)}</td>
            <td>P{money(row.amount_collected)}</td>
            <td>P{money(row.balance_due)}</td>
            <td>{row.due_date || '-'}</td>
            <td>{STATUS_LABELS[row.status] || row.status || '-'}</td>
            <td>
              {hasCustomActions
                ? renderActions(row)
                : (
                  Number(row.balance_due || 0) > 0
                    ? <button type="button" className="secondary" onClick={() => onCollect?.(row)}>Receive</button>
                    : '-'
                )}
            </td>
          </tr>
        ))}
        {!rows.length && <tr><td colSpan="9" className="muted">No receivables.</td></tr>}
      </tbody>
    </table>
  );
}
