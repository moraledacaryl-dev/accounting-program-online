'use client';

import { useEffect, useId, useRef, useState } from 'react';

export default function ConfirmActionModal({
  open,
  title,
  description,
  confirmLabel = 'Confirm',
  tone = 'danger',
  reasonRequired = false,
  onConfirm,
  onClose,
}) {
  const titleId = useId();
  const cancelRef = useRef(null);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setReason('');
    setBusy(false);
    setError('');
    const timer = window.setTimeout(() => cancelRef.current?.focus(), 0);
    return () => window.clearTimeout(timer);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event) => {
      if (event.key === 'Escape' && !busy) onClose?.();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, onClose, busy]);

  if (!open) return null;

  async function runConfirm() {
    if (reasonRequired && !reason.trim()) {
      setError('Enter a reason before continuing.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await onConfirm?.(reason.trim());
      onClose?.();
    } catch (err) {
      setError(err.message || 'Action failed.');
      setBusy(false);
    }
  }

  const isDanger = tone === 'danger';

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby={titleId} onClick={() => !busy && onClose?.()}>
      <div className={`modal-card confirm-action-modal ${isDanger ? 'is-danger' : 'is-neutral'}`} onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <div className="confirm-action-heading">
            <span className="confirm-action-icon" aria-hidden="true">{isDanger ? '!' : 'i'}</span>
            <div>
              <h2 id={titleId}>{title}</h2>
              {!!description && <p>{description}</p>}
            </div>
          </div>
          <button type="button" className="modal-close" onClick={onClose} disabled={busy} aria-label="Close confirmation">×</button>
        </div>
        <div className="modal-form stack">
          {reasonRequired && (
            <label className="field">
              Reason
              <textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Explain why this action is needed." />
            </label>
          )}
          {!!error && <p className="error-text" role="alert">{error}</p>}
          <div className="row wrap modal-actions">
            <button ref={cancelRef} type="button" className="secondary" onClick={onClose} disabled={busy}>Cancel</button>
            <button type="button" className={isDanger ? 'danger' : ''} onClick={runConfirm} disabled={busy}>{busy ? 'Processing…' : confirmLabel}</button>
          </div>
        </div>
      </div>
    </div>
  );
}
