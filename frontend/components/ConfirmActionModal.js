'use client';

import { useEffect, useId, useState } from 'react';

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
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setReason('');
    setBusy(false);
    setError('');
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

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby={titleId} onClick={() => !busy && onClose?.()}>
      <div className="modal-card" style={{ maxWidth: 520 }} onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2 id={titleId}>{title}</h2>
            {!!description && <p className="muted">{description}</p>}
          </div>
          <button type="button" className="secondary" onClick={onClose} disabled={busy}>Close</button>
        </div>
        <div className="modal-form stack">
          {reasonRequired && <label className="field">Reason<textarea value={reason} onChange={(event) => setReason(event.target.value)} autoFocus placeholder="Explain why this action is needed." /></label>}
          {!!error && <p className="error-text">{error}</p>}
          <div className="row wrap">
            <button type="button" className={tone === 'danger' ? 'danger' : ''} onClick={runConfirm} disabled={busy}>{busy ? 'Processing...' : confirmLabel}</button>
            <button type="button" className="secondary" onClick={onClose} disabled={busy}>Cancel</button>
          </div>
        </div>
      </div>
    </div>
  );
}
