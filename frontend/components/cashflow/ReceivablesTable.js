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

function sourceDetails(row) {
  if (row.source_type === 'pos_room_charge') {
    return `POS room charge${row.source_id ? ` #${row.source_id}` : ''}${row.external_id ? ` · ${row.external_id}` : ''}`;
  }
  if (row.source_type === 'pos_room_charge_reversal') {
    return `POS reversal${row.source_id ? ` #${row.source_id}` : ''}${row.external_id ? ` · ${row.external_id}` : ''}`;
  }
  return [row.source_type, row.source_id ? `#${row.source_id}` : '', row.external_id].filter(Boolean).join(' · ');
}

function reversalDetails(row) {
  const total = Number(row.adjustments_total || row.adjustment_amount || 0);
  if (!total) return '';
  const reversed = Math.abs(total);
  const remaining = Number(row.balance_due || 0);
  return `${remaining > 0 ? 'Partially reversed' : 'Reversed'} P${money(reversed)}${row.latest_adjustment_source_type ? ` by ${row.latest_adjustment_source_type}` : ''}`;
}

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
            <td>
              <strong>{row.counterparty_name}</strong>
              {sourceDetails(row) ? <div className="small muted">{sourceDetails(row)}</div> : null}
              {reversalDetails(row) ? <div className="small muted">{reversalDetails(row)}</div> : null}
            </td>
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
