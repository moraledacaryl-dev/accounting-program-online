export default function MetricCard({ label, value, note, tone = 'neutral' }) {
  return (
    <article className={`metric-card tone-${tone}`}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      {!!note && <div className="metric-note">{note}</div>}
    </article>
  );
}
