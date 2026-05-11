export default function ToggleField({ label, checked, onChange, hint = '' }) {
  return (
    <div className="toggle-field">
      <div>
        <div className="toggle-label">{label}</div>
        {!!hint && <div className="toggle-hint">{hint}</div>}
      </div>
      <button
        type="button"
        className={checked ? 'toggle-btn on' : 'toggle-btn'}
        aria-pressed={checked}
        onClick={() => onChange(!checked)}
      >
        {checked ? 'Yes' : 'No'}
      </button>
    </div>
  );
}
