'use client';

import { Component, useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

const FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

class DrawerErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error) {
    console.error('Drawer content failed to render', error);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="ho-drawer-error" role="alert">
        <div className="ho-drawer-error__icon" aria-hidden="true">!</div>
        <div>
          <h3>This panel could not be displayed</h3>
          <p>Close it and try again. Your underlying page has not been changed.</p>
        </div>
        <button type="button" className="secondary" onClick={this.props.onClose}>Close panel</button>
      </div>
    );
  }
}

export default function Drawer({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = 'medium',
  eyebrow = 'Quick entry',
  busy = false,
  dirty = false,
  closeOnBackdrop = true,
  onBeforeClose,
  initialFocusRef,
}) {
  const titleId = useId();
  const descriptionId = useId();
  const panelRef = useRef(null);
  const closeRef = useRef(null);
  const openerRef = useRef(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  function requestClose(reason = 'close-button') {
    if (busy) return;
    if (onBeforeClose && onBeforeClose(reason) === false) return;
    if (!onBeforeClose && dirty && typeof window !== 'undefined') {
      const shouldDiscard = window.confirm('Discard your unsaved changes?');
      if (!shouldDiscard) return;
    }
    onClose?.(reason);
  }

  useEffect(() => {
    if (!open || !mounted) return undefined;
    openerRef.current = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    document.body.classList.add('ho-drawer-open');

    const timer = window.setTimeout(() => {
      const preferred = initialFocusRef?.current
        || panelRef.current?.querySelector('[data-drawer-autofocus]')
        || panelRef.current?.querySelector('.ho-drawer__body input:not([disabled]):not([type="hidden"]), .ho-drawer__body select:not([disabled]), .ho-drawer__body textarea:not([disabled])')
        || closeRef.current;
      preferred?.focus();
    }, 0);

    function onKeyDown(event) {
      if (event.key === 'Escape') {
        event.preventDefault();
        requestClose('escape');
        return;
      }
      if (event.key !== 'Tab' || !panelRef.current) return;
      const focusable = Array.from(panelRef.current.querySelectorAll(FOCUSABLE)).filter((element) => !element.hasAttribute('hidden') && element.offsetParent !== null);
      if (!focusable.length) {
        event.preventDefault();
        panelRef.current.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = previousOverflow;
      document.body.classList.remove('ho-drawer-open');
      if (openerRef.current instanceof HTMLElement) openerRef.current.focus();
    };
  }, [open, mounted, busy, dirty, onBeforeClose, onClose, initialFocusRef]);

  if (!mounted || !open) return null;

  return createPortal(
    <div className="ho-drawer-layer" role="presentation">
      <button
        className="ho-drawer-scrim"
        type="button"
        aria-label="Close panel"
        tabIndex="-1"
        onClick={() => closeOnBackdrop && requestClose('backdrop')}
      />
      <section
        ref={panelRef}
        className={`ho-drawer ho-drawer--${size}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        aria-busy={busy || undefined}
        tabIndex="-1"
      >
        <header className="ho-drawer__header">
          <div className="ho-drawer__heading">
            {eyebrow ? <div className="ho-eyebrow">{eyebrow}</div> : null}
            <h2 id={titleId}>{title}</h2>
            {description ? <p id={descriptionId}>{description}</p> : null}
          </div>
          <button
            ref={closeRef}
            type="button"
            className="ho-drawer__close"
            onClick={() => requestClose('close-button')}
            aria-label="Close panel"
            disabled={busy}
          >
            ×
          </button>
        </header>
        <div className="ho-drawer__body">
          <DrawerErrorBoundary key={`${title}-${open}`} onClose={() => requestClose('error-fallback')}>
            {children}
          </DrawerErrorBoundary>
        </div>
        {footer ? <footer className="ho-drawer__footer">{footer}</footer> : null}
        {busy ? <div className="ho-drawer__busy" role="status" aria-live="polite">Working…</div> : null}
      </section>
    </div>,
    document.body,
  );
}
