function money(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function JournalImpactPreview({ direction = 'in', amount = 0, paymentMethod = 'cash' }) {
  const value = Number(amount || 0);
  const method = String(paymentMethod || 'cash').toLowerCase();

  const cashAccount = method.includes('bank') ? 'Bank' : (method.includes('ewallet') || method.includes('gcash') ? 'E-Wallet' : 'Cash');
  const debit = direction === 'in' ? cashAccount : 'Operating Expense';
  const credit = direction === 'in' ? 'Revenue' : cashAccount;

  return (
    <section className="section">
      <details className="quiet-details">
        <summary>Accounting preview</summary>
        <div className="small muted" style={{ marginTop: 8 }}>For manager/accounting review. Final accounts still follow the saved posting rules.</div>
        <table className="table dense-table" style={{ marginTop: 8 }}>
          <thead><tr><th>Side</th><th>Account</th><th>Amount</th></tr></thead>
          <tbody>
            <tr><td>Debit</td><td>{debit}</td><td>P{money(value)}</td></tr>
            <tr><td>Credit</td><td>{credit}</td><td>P{money(value)}</td></tr>
          </tbody>
        </table>
      </details>
    </section>
  );
}
