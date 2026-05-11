import Link from 'next/link';
import AccountTypeIcon from './AccountTypeIcon';
import CashVarianceBadge from './CashVarianceBadge';

function money(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function AccountCard({ account, onEdit, onReconcile }) {
  return (
    <div className="card">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <strong>{account.name}</strong>
        <AccountTypeIcon accountType={account.account_type} />
      </div>
      <div className="small muted">{account.code}</div>
      <div className="kpi" style={{ marginTop: 6, marginBottom: 8 }}>P{money(account.current_balance)}</div>
      <div className="row wrap" style={{ marginBottom: 8 }}>
        <span className="small muted">In: P{money(account.today_in)}</span>
        <span className="small muted">Out: P{money(account.today_out)}</span>
      </div>
      <div className="row wrap" style={{ marginBottom: 10 }}>
        <span className="small muted">Check: {account.reconciliation_status || 'missing'}</span>
        {account.reconciliation_variance !== null && typeof account.reconciliation_variance !== 'undefined' && (
          <CashVarianceBadge variance={account.reconciliation_variance} />
        )}
      </div>
      <div className="row wrap">
        <button type="button" className="secondary" onClick={() => onEdit?.(account)}>Edit</button>
        <button type="button" className="secondary" onClick={() => onReconcile?.(account)}>Count</button>
        <Link className="button-link secondary-link" href={`/cashflow/${account.id}`}>History</Link>
      </div>
    </div>
  );
}
