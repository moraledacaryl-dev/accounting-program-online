import Link from 'next/link';

export function PageHeader({ eyebrow, title, description, actions, className = '' }) {
  return (
    <header className={`ho-page-header ${className}`.trim()}>
      <div className="ho-page-header__copy">
        {eyebrow ? <div className="ho-eyebrow">{eyebrow}</div> : null}
        <h1 className="ho-page-title">{title}</h1>
        {description ? <p className="ho-page-description">{description}</p> : null}
      </div>
      {actions ? <div className="ho-page-actions">{actions}</div> : null}
    </header>
  );
}

export function Button({
  children,
  variant = 'secondary',
  size = 'medium',
  className = '',
  href,
  ...props
}) {
  const classes = [
    'ho-button',
    variant !== 'secondary' ? `ho-button--${variant}` : '',
    size === 'small' ? 'ho-button--small' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  if (href) {
    return (
      <Link className={classes} href={href} {...props}>
        {children}
      </Link>
    );
  }

  return (
    <button className={classes} type={props.type || 'button'} {...props}>
      {children}
    </button>
  );
}

export function Card({ title, description, actions, children, tone = 'raised', className = '' }) {
  const surfaceClass = tone === 'subtle' ? 'ho-surface--subtle' : tone === 'flat' ? 'ho-surface' : 'ho-surface--raised';

  return (
    <section className={`${surfaceClass} card ${className}`.trim()}>
      {title || description || actions ? (
        <div className="ho-card-header">
          <div>
            {title ? <h2 className="ho-card-title">{title}</h2> : null}
            {description ? <p className="ho-card-description">{description}</p> : null}
          </div>
          {actions ? <div className="ho-page-actions">{actions}</div> : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}

export function MetricCard({ label, value, note, tone = 'neutral', className = '' }) {
  const noteClass = tone === 'positive' || tone === 'warning' || tone === 'danger'
    ? ` ho-metric-note--${tone}`
    : '';

  return (
    <article className={`ho-metric-card ${className}`.trim()}>
      <div className="ho-metric-label">{label}</div>
      <div className="ho-metric-value">{value}</div>
      {note ? <div className={`ho-metric-note${noteClass}`}>{note}</div> : null}
    </article>
  );
}

export function MetricGrid({ children, className = '' }) {
  return <div className={`ho-metric-grid ${className}`.trim()}>{children}</div>;
}

export function StatusBadge({ children, tone = 'neutral', className = '' }) {
  return <span className={`ho-badge ho-badge--${tone} ${className}`.trim()}>{children}</span>;
}

export function Tabs({ children, label = 'Sections', className = '' }) {
  return (
    <div className={`ho-tabs ${className}`.trim()} role="tablist" aria-label={label}>
      {children}
    </div>
  );
}

export function Tab({ children, active = false, className = '', ...props }) {
  return (
    <button
      className={`ho-tab ${active ? 'is-active' : ''} ${className}`.trim()}
      type="button"
      role="tab"
      aria-selected={active}
      {...props}
    >
      {children}
    </button>
  );
}

export function Notice({ children, tone = 'warning', className = '' }) {
  const toneClass = tone === 'warning' ? '' : ` ho-notice--${tone}`;
  return <div className={`ho-notice${toneClass} ${className}`.trim()}>{children}</div>;
}

export function EmptyState({ title, description, action, className = '' }) {
  return (
    <div className={`ho-empty-state ${className}`.trim()}>
      <div>
        {title ? <div className="ho-empty-state__title">{title}</div> : null}
        {description ? <p>{description}</p> : null}
        {action ? <div className="ho-page-actions" style={{ justifyContent: 'center', marginTop: '1rem' }}>{action}</div> : null}
      </div>
    </div>
  );
}

export function Field({ label, help, error, required = false, children, className = '' }) {
  return (
    <label className={`ho-field ${className}`.trim()}>
      <span className="ho-field-label">
        {label}
        {required ? ' *' : ''}
      </span>
      {children}
      {error ? <span className="ho-field-error">{error}</span> : null}
      {!error && help ? <span className="ho-field-help">{help}</span> : null}
    </label>
  );
}

export function TableWrap({ children, className = '' }) {
  return <div className={`ho-table-wrap ${className}`.trim()}>{children}</div>;
}
