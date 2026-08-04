'use client';

import Link from 'next/link';

export default function ErrorPage({ error, reset }) {
  return (
    <main className="route-state-shell">
      <section className="route-state-card" data-tone="danger" role="alert">
        <div className="route-state-icon" aria-hidden="true">!</div>
        <h1>This page could not be loaded</h1>
        <p>{error?.message || 'An unexpected application error interrupted this workspace.'}</p>
        <div className="route-state-actions">
          <button type="button" className="primary" onClick={() => reset()}>Try again</button>
          <Link className="secondary" href="/dashboard">Return to dashboard</Link>
        </div>
      </section>
    </main>
  );
}
