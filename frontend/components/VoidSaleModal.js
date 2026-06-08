'use client';

import { useEffect, useId, useState } from 'react';

export default function VoidSaleModal({ sale, onConfirm, onClose }) {
  const titleId = useId();
  const [reason, setReason] = useState('Customer cancellation');
  const [reverseInventory, setReverseInventory] = useState(true);
  const [autoPostAccounting, setAutoPostAccounting] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!sale) return;
    setReason('Customer cancellation');
    setReverseInventory(true);
    setAutoPostAccounting(true);
    setBusy(false);
    setError('');
  }, [sale]);

  useEffect(() => {
    if (!sale) return;
    const onKeyDown = (event) => {
      if (event.key === 'Escape' && !busy) onClose?.();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [busy, onClose, sale]);

  if (!sale) return null;

  async function submit(event) {
    event.preventDefault();
    if (!reason.trim()) return setError('Enter a void reason before continuing.');
    setBusy(true);
    setError('');
    try {
      await onConfirm?.({ reason: reason.trim(), reverseInventory, autoPostAccounting });
      onClose?.();
    } catch (err) {
      setError(err.message || 'Unable to void sale.');
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby={titleId}>
      <div className="modal-card" style={{ maxWidth: 560 }}>
        <div className="modal-header">
          <div><h2 id={titleId}>Void sale {sale.order_no}?</h2><p className="muted">The void remains visible in the audit trail. Review both reversal options before continuing.</p></div>
          <button type="button" className="secondary" onClick={onClose} disabled={busy}>Close</button>
        </div>
        <form className="modal-form stack" onSubmit={submit}>
          <label className="field">Void reason<textarea value={reason} onChange={(event) => setReason(event.target.value)} autoFocus /></label>
          <label className="field-inline"><input type="checkbox" checked={reverseInventory} onChange={(event) => setReverseInventory(event.target.checked)} /> Restore inventory deductions from this sale</label>
          <label className="field-inline"><input type="checkbox" checked={autoPostAccounting} onChange={(event) => setAutoPostAccounting(event.target.checked)} /> Create linked accounting reversal records</label>
          {!!error && <p className="error-text">{error}</p>}
          <div className="row wrap">
            <button type="submit" className="danger" disabled={busy}>{busy ? 'Voiding...' : 'Void sale'}</button>
            <button type="button" className="secondary" onClick={onClose} disabled={busy}>Cancel</button>
          </div>
        </form>
      </div>
    </div>
  );
}
