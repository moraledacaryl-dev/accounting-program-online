import CashVarianceBadge from './CashVarianceBadge';

function money(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

const STATUS_LABELS = {
  open: 'Open',
  counted: 'Counted',
  reviewed: 'Reviewed',
  closed: 'Closed',
  discrepancy_flagged: 'Needs review',
  reversed: 'Reversed',
};

export default function ReconciliationTable({ rows = [], renderActions = null }) {
  const hasActions = typeof renderActions === 'function';
  return (
    <table className="table">
      <thead>
        <tr>
          <th>Date</th>
          <th>Account</th>
          <th>Shift</th>
          <th>Expected</th>
          <th>Counted</th>
          <th>Difference</th>
          <th>Status</th>
          {hasActions && <th></th>}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <td>{row.reconciliation_date}</td>
            <td>{row.financial_account_code} · {row.financial_account_name}</td>
            <td>{row.shift_name || 'day'}</td>
            <td>P{money(row.expected_closing)}</td>
            <td>P{money(row.actual_counted)}</td>
            <td><CashVarianceBadge variance={row.variance} /></td>
            <td>{STATUS_LABELS[row.status] || row.status || '-'}</td>
            {hasActions && <td className="row wrap">{renderActions(row)}</td>}
          </tr>
        ))}
        {!rows.length && <tr><td colSpan={hasActions ? 8 : 7} className="muted">No counts or checks yet.</td></tr>}
      </tbody>
    </table>
  );
}
