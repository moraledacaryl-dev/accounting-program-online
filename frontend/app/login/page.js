'use client';

import { useState } from 'react';
import { login } from '../../lib/api';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [attempted, setAttempted] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const usernameError = attempted && !username.trim() ? 'Enter your username.' : '';
  const passwordError = attempted && !password ? 'Enter your password.' : '';

  async function submit(event) {
    event.preventDefault();
    setAttempted(true);
    setError('');
    if (!username.trim() || !password) return;

    setBusy(true);
    try {
      await login({ username: username.trim(), password });
      const searchParams = new URLSearchParams(window.location.search);
      const next = searchParams.get('next') || '/';
      window.location.href = next.startsWith('/') && !next.startsWith('//') ? next : '/';
    } catch (requestError) {
      setError(requestError.message || 'Invalid username or password.');
      setBusy(false);
    }
  }

  return (
    <div className="auth-login-shell">
      <main className="auth-login-card">
        <div className="auth-login-identity">
          <div className="auth-login-mark" aria-hidden="true">HO</div>
          <div>
            <div className="ho-eyebrow">Hidden Oasis</div>
            <h1>Accounting</h1>
            <p className="muted">Sign in to continue.</p>
          </div>
        </div>

        <form onSubmit={submit} className="auth-login-form" noValidate>
          <label>
            Username
            <input
              data-drawer-autofocus
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              aria-invalid={usernameError ? 'true' : undefined}
              aria-describedby={usernameError ? 'login-username-error' : undefined}
              disabled={busy}
            />
            {usernameError ? <span id="login-username-error" className="field-error" role="alert">{usernameError}</span> : null}
          </label>
          <label>
            Password
            <span className="auth-password-field">
              <input
                autoComplete="current-password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                aria-invalid={passwordError ? 'true' : undefined}
                aria-describedby={passwordError ? 'login-password-error' : undefined}
                disabled={busy}
              />
              <button
                type="button"
                className="auth-password-toggle secondary"
                onClick={() => setShowPassword((value) => !value)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                disabled={busy}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                  {showPassword ? (
                    <path d="M3 3l18 18M10.6 10.7a2 2 0 0 0 2.7 2.7M9.9 4.3A10.8 10.8 0 0 1 12 4c5.3 0 9 4.5 9 8a8.6 8.6 0 0 1-2 4.3M6.2 6.2C4.2 7.6 3 9.8 3 12c0 3.5 3.7 8 9 8a10.4 10.4 0 0 0 4.1-.8" />
                  ) : (
                    <><path d="M3 12s3.7-8 9-8 9 8 9 8-3.7 8-9 8-9-8-9-8Z" /><circle cx="12" cy="12" r="2.5" /></>
                  )}
                </svg>
              </button>
            </span>
            {passwordError ? <span id="login-password-error" className="field-error" role="alert">{passwordError}</span> : null}
          </label>
          {error ? <div className="ho-notice ho-notice--danger" role="alert">{error}</div> : null}
          <button type="submit" className="auth-submit" disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="auth-login-help">Contact your system administrator if you cannot access your account.</p>
      </main>
    </div>
  );
}
