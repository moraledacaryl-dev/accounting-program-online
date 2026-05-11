function currency(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function CashflowSummaryCards({ cards = {} }) {
  const rows = [
    ['Total Cash On Hand', cards.total_cash_on_hand, true],
    ['Total Bank Balance', cards.total_bank_balance, true],
    ['To Receive', cards.receivables_due, true],
    ['To Pay', cards.payables_due, true],
    ["Today's Money In", cards.todays_money_in, true],
    ["Today's Money Out", cards.todays_money_out, true],
    ['Accounts to Check', cards.unreconciled_accounts, false],
    ['Count Differences', cards.variance_alerts, false],
  ];

  return (
    <div className="card-grid">
      {rows.map(([label, value, money]) => (
        <div key={label} className="card">
          <div className="muted">{label}</div>
          <div className="kpi">{money ? `P${currency(value)}` : Number(value || 0)}</div>
        </div>
      ))}
    </div>
  );
}
