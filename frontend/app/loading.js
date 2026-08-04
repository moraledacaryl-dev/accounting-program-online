export default function Loading() {
  return (
    <main className="route-state-shell" aria-busy="true" aria-live="polite">
      <section className="route-state-card route-loading-card" aria-label="Loading page">
        <div className="route-loading-line title" />
        <div className="route-loading-line" />
        <div className="route-loading-line short" />
        <div className="route-loading-block" />
      </section>
    </main>
  );
}
