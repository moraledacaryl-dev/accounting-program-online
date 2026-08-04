import Link from 'next/link';

export default function NotFound() {
  return (
    <main className="route-state-shell">
      <section className="route-state-card">
        <div className="route-state-icon" aria-hidden="true">404</div>
        <h1>Page not found</h1>
        <p>The requested accounting workspace does not exist, may have moved, or is no longer available to this account.</p>
        <div className="route-state-actions">
          <Link className="primary" href="/dashboard">Go to dashboard</Link>
          <Link className="secondary" href="/review-inbox">Open review inbox</Link>
        </div>
      </section>
    </main>
  );
}
