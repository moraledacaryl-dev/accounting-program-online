function money(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

const TYPE_LABELS = {
  supplier_bill: 'Supplier',
  utility_bill: 'Utility',
  payroll_liability: 'Payroll / gov',
  tax_liability: 'Tax',
  service_provider_bill: 'Service provider',
};

const STATUS_LABELS = {
  open: 'Open',
  partial: 'Part paid',
  settled: 'Paid',
  written_off: 'Written off',
};

export default function PayablesTable({ rows = [], onPay, renderActions = null }) {
  const hasCustomActions = typeof renderActions === 'function';
  return (
    <table className="table">
      <thead>
        <tr>
          <th>Bill Date</th>
          <th>Type</th>
          <th>Supplier</th>
          <th>Total</th>
          <th>Paid</th>
          <th>Balance</th>
          <th>Due</th>
          <th>Status</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <td>{row.bill_date}</td>
            <td>{TYPE_LABELS[row.payable_type] || row.payable_type || '-'}</td>
            <td>{row.supplier_name}</td>
            <td>P{money(row.gross_amount)}</td>
            <td>P{money(row.amount_paid)}</td>
            <td>P{money(row.balance_due)}</td>
            <td>{row.due_date || '-'}</td>
            <td>{STATUS_LABELS[row.status] || row.status || '-'}</td>
            <td>
              {hasCustomActions
                ? renderActions(row)
                : (
                  Number(row.balance_due || 0) > 0
                    ? <button type="button" className="secondary" onClick={() => onPay?.(row)}>Pay</button>
                    : '-'
                )}
            </td>
          </tr>
        ))}
        {!rows.length && <tr><td colSpan="9" className="muted">No payables.</td></tr>}
      </tbody>
    </table>
  );
}
