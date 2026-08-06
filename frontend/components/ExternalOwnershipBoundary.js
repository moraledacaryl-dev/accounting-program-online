'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';
import { ownershipForPath } from '../lib/applicationOwnership';

const MUTATION_PATTERN = /^(add|approve|cancel|convert|create|delete|edit|import|issue|post|receive|reject|remove|save|submit|sync|update)\b/i;

function controlLabel(element) {
  return String(element?.getAttribute?.('aria-label') || element?.textContent || '').trim();
}

export default function ExternalOwnershipBoundary({ children }) {
  const pathname = usePathname();
  const ownership = ownershipForPath(pathname);
  const [blockedMessage, setBlockedMessage] = useState('');

  if (!ownership) return children;

  function blockMutation(event) {
    event.preventDefault();
    event.stopPropagation();
    setBlockedMessage(`Create and update this record in ${ownership.appName}. Accounting is read-only for this workflow.`);
  }

  function handleClickCapture(event) {
    const button = event.target?.closest?.('button');
    if (!button || button.disabled) return;
    if (button.dataset.ownershipSafe === 'true') return;
    if (MUTATION_PATTERN.test(controlLabel(button))) blockMutation(event);
  }

  return (
    <div className="external-ownership-boundary" onSubmitCapture={blockMutation} onClickCapture={handleClickCapture}>
      <section className="section legacy-notice ownership-notice" aria-label="Authoritative application notice">
        <div>
          <span className="badge">Read-only transition view</span>
          <h2>{ownership.appName} owns this operational workflow</h2>
          <p className="muted">Accounting retains historical records, financial references, and migration verification. Create, edit, approve, receive, or delete operational records in the authoritative application.</p>
          {!!blockedMessage && <p className="error-text" role="alert">{blockedMessage}</p>}
        </div>
        {ownership.appUrl ? <Link className="button-link" href={ownership.appUrl}>Open {ownership.appName}</Link> : <span className="badge">Application URL not configured</span>}
      </section>
      {children}
    </div>
  );
}
