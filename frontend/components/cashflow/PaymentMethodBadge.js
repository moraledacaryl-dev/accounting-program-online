export default function PaymentMethodBadge({ method = '' }) {
  const value = String(method || '').trim() || 'n/a';
  return <span className="badge">{value}</span>;
}
