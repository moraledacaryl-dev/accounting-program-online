export default function CashVarianceBadge({ variance = 0 }) {
  const value = Number(variance || 0);
  const absValue = Math.abs(value);
  if (absValue < 0.01) {
    return <span className="badge">Balanced</span>;
  }
  const label = value > 0 ? `Over +${value.toFixed(2)}` : `Short ${value.toFixed(2)}`;
  return <span className="badge" style={{ background: '#fdecec', color: '#9a1f1f', borderColor: '#f5cccc' }}>{label}</span>;
}
