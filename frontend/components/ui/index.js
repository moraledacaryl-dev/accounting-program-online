'use client';

import { useEffect } from 'react';

function cx(...values) {
  return values.filter(Boolean).join(' ');
}

export function PageStack({ className, children }) {
  return <div className={cx('ui-page-stack', className)}>{children}</div>;
}

export function PageHeader({ eyebrow, title, description, actions, className }) {
  return (
    <header className={cx('ui-page-header', className)}>
      <div className="ui-page-header__copy">
        {eyebrow ? <div className="ui-eyebrow">{eyebrow}</div> : null}
        <h1 className="ui-page-title">{title}</h1>
        {description ? <p className="ui-page-description">{description}</p> : null}
      </div>
      {actions ? <div className="ui-page-actions">{actions}</div> : null}
    </header>
  );
}

export function MetricGrid({ className, children }) {
  return <div className={cx('ui-metric-grid', className)}>{children}</div>;
}

export function MetricCard({ label, value, delta, className }) {
  return (
    <article className={cx('ui-metric-card', className)}>
      <div className="ui-metric-card__label">{label}</div>
      <div className="ui-metric-card__value">{value}</div>
      {delta ? <div className="ui-metric-card__delta">{delta}</div> : null}
    </article>
  );
}

export function SectionCard({ title, description, actions, variant, className, children }) {
  return (
    <section className={cx('ui-section-card', variant && `ui-section-card--${variant}`, className)}>
      {title || description || actions ? (
        <header className="ui-section-card__header">
          <div>
            {title ? <h2 className="ui-section-card__title">{title}</h2> : null}
            {description ? <p className="ui-section-card__description">{description}</p> : null}
          </div>
          {actions ? <div className="ui-card-actions">{actions}</div> : null}
        </header>
      ) : null}
      <div className="ui-section-card__body">{children}</div>
    </section>
  );
}

export function StatusBadge({ tone = 'neutral', className, children }) {
  return <span className={cx('ui-badge', tone !== 'neutral' && `ui-badge--${tone}`, className)}>{children}</span>;
}

export function Button({ variant = 'secondary', size = 'medium', className, type = 'button', ...props }) {
  return (
    <button
      type={type}
      className={cx(
        'ui-button',
        variant !== 'secondary' && `ui-button--${variant}`,
        size === 'small' && 'ui-button--small',
        className,
      )}
      {...props}
    />
  );
}

export function Tabs({ value, onChange, items, ariaLabel = 'Sections', className }) {
  return (
    <div className={cx('ui-tabs', className)} role="tablist" aria-label={ariaLabel}>
      {items.map((item) => (
        <button
          key={item.value}
          type="button"
          role="tab"
          aria-selected={value === item.value}
          className={cx('ui-tab', value === item.value && 'ui-tab--active')}
          onClick={() => onChange?.(item.value)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

export function FilterBar({ className, children }) {
  return <div className={cx('ui-filter-bar', className)}>{children}</div>;
}

export function Input({ className, ...props }) {
  return <input className={cx('ui-input', className)} {...props} />;
}

export function Select({ className, children, ...props }) {
  return <select className={cx('ui-select', className)} {...props}>{children}</select>;
}

export function Textarea({ className, ...props }) {
  return <textarea className={cx('ui-textarea', className)} {...props} />;
}

export function DataTable({ children, className, tableClassName }) {
  return (
    <div className={cx('ui-table-wrap', className)}>
      <table className={cx('ui-table', tableClassName)}>{children}</table>
    </div>
  );
}

export function Notice({ tone = 'warning', className, children }) {
  return (
    <div className={cx('ui-notice', tone !== 'warning' && `ui-notice--${tone}`, className)} role="status">
      {children}
    </div>
  );
}

export function EmptyState({ title, description, actions, className }) {
  return (
    <div className={cx('ui-empty-state', className)}>
      {title ? <div className="ui-empty-state__title">{title}</div> : null}
      {description ? <div>{description}</div> : null}
      {actions ? <div className="ui-inline-actions">{actions}</div> : null}
    </div>
  );
}

export function Drawer({ open, title, description, onClose, footer, children }) {
  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose?.();
    };
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <>
      <button className="ui-drawer-scrim" aria-label="Close drawer" onClick={onClose} />
      <aside className="ui-drawer" role="dialog" aria-modal="true" aria-label={title || 'Details'}>
        <header className="ui-drawer__header">
          <div className="ui-card-actions" style={{ justifyContent: 'space-between' }}>
            <div>
              {title ? <h2 className="ui-section-card__title">{title}</h2> : null}
              {description ? <p className="ui-section-card__description">{description}</p> : null}
            </div>
            <Button size="small" variant="ghost" onClick={onClose} aria-label="Close drawer">Close</Button>
          </div>
        </header>
        <div className="ui-drawer__body">{children}</div>
        {footer ? <footer className="ui-drawer__footer">{footer}</footer> : null}
      </aside>
    </>
  );
}

export function ActionMenu({ label = 'More', children, className }) {
  return (
    <details className={className}>
      <summary className="ui-button ui-button--small">{label}</summary>
      <div className="ui-section-card" style={{ position: 'absolute', zIndex: 20, padding: 8, minWidth: 180 }}>
        {children}
      </div>
    </details>
  );
}
