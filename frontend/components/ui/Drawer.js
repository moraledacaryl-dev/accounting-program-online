'use client';

import { useEffect, useId, useRef } from 'react';

export default function Drawer({ open, onClose, title, description, children, footer, size = 'medium' }) {
  const titleId = useId();
  const descriptionId = useId();
  const closeRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const timer = window.setTimeout(() => closeRef.current?.focus(), 0);
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose?.();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="ho-drawer-layer" role="presentation">
      <button className="ho-drawer-scrim" type="button" aria-label="Close panel" onClick={onClose} />
      <section className={`ho-drawer ho-drawer--${size}`} role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={description ? descriptionId : undefined}>
        <header className="ho-drawer__header">
          <div>
            <div className="ho-eyebrow">Quick entry</div>
            <h2 id={titleId}>{title}</h2>
            {description ? <p id={descriptionId}>{description}</p> : null}
          </div>
          <button ref={closeRef} type="button" className="ho-drawer__close" onClick={onClose} aria-label="Close panel">×</button>
        </header>
        <div className="ho-drawer__body">{children}</div>
        {footer ? <footer className="ho-drawer__footer">{footer}</footer> : null}
      </section>
    </div>
  );
}
