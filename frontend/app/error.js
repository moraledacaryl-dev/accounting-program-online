'use client';

export default function ErrorPage({ error, reset }) {
  return (
    <section className="section">
      <h1>Something went wrong</h1>
      <p className="muted">{error?.message || 'This workspace could not be loaded.'}</p>
      <button type="button" style={{ marginTop: 12 }} onClick={() => reset()}>Try again</button>
    </section>
  );
}
