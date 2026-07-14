export default function PageHeader({ eyebrow, title, description, actions, children }) {
  return (
    <section className="page-header">
      <div className="page-header-copy">
        {!!eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {!!description && <p className="muted">{description}</p>}
        {children}
      </div>
      {!!actions && <div className="page-header-actions">{actions}</div>}
    </section>
  );
}
