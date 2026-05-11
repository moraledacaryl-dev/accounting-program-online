export default function AccountTypeIcon({ accountType }) {
  const key = String(accountType || '').toLowerCase();
  if (key === 'bank') return <span className="badge">BANK</span>;
  if (key === 'cash_drawer') return <span className="badge">DRAWER</span>;
  if (key === 'petty_cash') return <span className="badge">PETTY</span>;
  if (key === 'safe') return <span className="badge">SAFE</span>;
  if (key === 'ewallet') return <span className="badge">EWALLET</span>;
  return <span className="badge">ACCOUNT</span>;
}
