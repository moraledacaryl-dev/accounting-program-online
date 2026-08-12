'use client';

import { useEffect, useId, useRef, useState } from 'react';

export default function InputActionModal({
  open,
  title,
  description = '',
  fieldLabel,
  defaultValue = '',
  inputType = 'textarea',
  required = false,
  confirmLabel = 'Confirm',
  tone = 'danger',
  onConfirm,
  onClose,
}) {
  const titleId = useId();
  const descriptionId = useId();
  const errorId = useId();
  const inputRef = useRef(null);
  const cancelRef = useRef(null);
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setValue(String(defaultValue ?? ''));
    setBusy(false);
    setError('');
    const timer = window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => window.clearTimeout(timer);
  }, [defaultValue, open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event) => {
      if (event.key === 'Escape' && !busy) onClose?.();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [busy, onClose, open]);

  if (!open) return null;

  async function submit(event) {
    event.preventDefault();
    if (required && !String(value).trim()) {
      setError(`${fieldLabel} is required.`);
      inputRef.current?.focus();
      return;
    }
    setBusy(true);
    setError('');
    try {
      await onConfirm?.(value);
      onClose?.();
    } catch (err) {
      setError(err.message || 'Action failed.');
      setBusy(false);
    }
  }

  const isDanger = tone === 'danger';

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={description ? descriptionId : undefined}
      onClick={() => !busy && onClose?.()}
    >
      <div className={`modal-card input-action-modal ${isDanger ? 'is-danger' : 'is-neutral'}`} onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <div className="input-action-heading">
            <span className="input-action-icon" aria-hidden="true">{isDanger ? '!' : 'i'}</span>
            <div>
              <h2 id={titleId}>{title}</h2>
              {!!description && <p id={descriptionId}>{description}</p>}
            </div>
          </div>
          <button type="button" className="modal-close" onClick={onClose} disabled={busy} aria-label="Close dialog">×</button>
        </div>
        <form className="modal-form stack" onSubmit={submit}>
          <label className="field">
            {fieldLabel}
            {inputType === 'textarea'
              ? <textarea ref={inputRef} value={value} onChange={(event) => setValue(event.target.value)} aria-invalid={!!error} aria-describedby={error ? errorId : undefined} />
              : <input ref={inputRef} type={inputType} value={value} onChange={(event) => setValue(event.target.value)} aria-invalid={!!error} aria-describedby={error ? errorId : undefined} />}
          </label>
          {!!error && <p id={errorId} className="error-text" role="alert">{error}</p>}
          <div className="row wrap modal-actions">
            <button ref={cancelRef} type="button" className="secondary" onClick={onClose} disabled={busy}>Cancel</button>
            <button type="submit" className={isDanger ? 'danger' : ''} disabled={busy}>{busy ? 'Processing…' : confirmLabel}</button>
          </div>
        </form>
      </div>
    </div>
  );
}
