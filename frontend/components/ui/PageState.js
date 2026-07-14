export function LoadingState({ title = 'Loading', message = 'Preparing this workspace…' }) {
  return <section className="page-state"><div className="state-spinner" /><h2>{title}</h2><p>{message}</p></section>;
}

export function EmptyState({ title = 'Nothing here yet', message, action }) {
  return <section className="page-state"><div className="state-icon">—</div><h2>{title}</h2>{message && <p>{message}</p>}{action}</section>;
}

export function ErrorState({ title = 'Something went wrong', message, action }) {
  return <section className="page-state state-error"><div className="state-icon">!</div><h2>{title}</h2>{message && <p>{message}</p>}{action}</section>;
}

export function PermissionState() {
  return <section className="page-state"><div className="state-icon">⌁</div><h2>Access restricted</h2><p>Your role does not include this workspace. Ask the Owner to update your access settings if needed.</p></section>;
}
