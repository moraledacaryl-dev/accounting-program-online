'use client';

import { useEffect, useRef } from 'react';
import NavIcon from './app-shell/NavIcon';

export default function RecordDrawer({ open, title, description, onClose, children }) {
  const closeRef = useRef(null);
  const layerRef = useRef(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return undefined;
    const previousOverflow = document.body.style.overflow;
    const opener = document.activeElement;
    const inertElements = [];
    let node = layerRef.current;
    while (node && node.parentElement && node.parentElement !== document.body) {
      for (const sibling of node.parentElement.children) {
        if (sibling !== node) { inertElements.push([sibling, sibling.inert]); sibling.inert = true; }
      }
      node = node.parentElement;
    }
    document.body.style.overflow = 'hidden';
    const timer = window.setTimeout(() => closeRef.current?.focus(), 0);
    function handleKey(event) {
      if (event.key === 'Escape') { event.preventDefault(); onCloseRef.current?.(); }
      if (event.key !== 'Tab') return;
      const items = [...layerRef.current.querySelectorAll('.record-drawer a[href], .record-drawer button:not(:disabled), .record-drawer input:not(:disabled), .record-drawer select:not(:disabled), .record-drawer textarea:not(:disabled), .record-drawer [tabindex="0"]')].filter(e => e.getClientRects().length);
      const index = items.indexOf(document.activeElement);
      if (event.shiftKey && index <= 0) { event.preventDefault(); items.at(-1)?.focus(); }
      else if (!event.shiftKey && (index === -1 || index === items.length - 1)) { event.preventDefault(); items[0]?.focus(); }
    }
    document.addEventListener('keydown', handleKey);
    return () => {
      window.clearTimeout(timer);
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', handleKey);
      inertElements.forEach(([element, previous]) => { element.inert = previous; });
      if (opener?.isConnected) opener.focus();
    };
  }, [open]);

  if (!open) return null;

  return (
    <div ref={layerRef} className="record-drawer-layer" role="presentation">
      <button type="button" className="record-drawer-scrim" aria-label="Close panel" tabIndex={-1} onClick={onClose} />
      <aside className="record-drawer" role="dialog" aria-modal="true" aria-labelledby="record-drawer-title">
        <header className="record-drawer__header">
          <div>
            <h2 id="record-drawer-title">{title}</h2>
            {description && <p>{description}</p>}
          </div>
          <button ref={closeRef} type="button" className="record-drawer__close" aria-label="Close panel" onClick={onClose}>
            <NavIcon name="close" size={18} />
          </button>
        </header>
        <div className="record-drawer__body">{children}</div>
      </aside>
    </div>
  );
}
