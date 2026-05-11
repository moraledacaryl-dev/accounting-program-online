'use client';

import Link from 'next/link';
import SetupGroupsManager from './SetupGroupsManager';

export default function SetupWorkspacePage({ title, description, groups = [], links = [] }) {
  return (
    <div className="stack">
      <section className="section">
        <h1>{title}</h1>
        {description && <p className="muted">{description}</p>}
      </section>

      <SetupGroupsManager groups={groups} />

      {!!links.length && (
        <section className="section">
          <h2>Related Pages</h2>
          <div className="card-grid" style={{ marginTop: 10 }}>
            {links.map(([href, label, note]) => (
              <Link key={href} href={href} className="card card-link">
                <div className="row" style={{ justifyContent: 'space-between' }}>
                  <strong>{label}</strong>
                  <span>→</span>
                </div>
                <div className="small muted">{note}</div>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
