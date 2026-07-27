'use client';

import { useEffect, useRef } from 'react';
import NavIcon from './app-shell/NavIcon';

export default function RecordDrawer({ open, title, description, onClose, children }) {
  const closeRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const timer = window.setTimeout(() => closeRef.current?.focus(), 0);
    function handleKey(event) {
      if (event.key === 'Escape') onClose?.();
    }
    document.addEventListener('keydown', handleKey);
    return () => {
      window.clearTimeout(timer);
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', handleKey);
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="record-drawer-layer" role="presentation">
      <button type="button" className="record-drawer-scrim" aria-label="Close panel" onClick={onClose} />
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
