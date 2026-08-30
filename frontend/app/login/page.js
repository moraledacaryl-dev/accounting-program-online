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
      <section className="auth-login-brand" aria-label="Hidden Oasis Accounting">
        <div className="auth-login-mark" aria-hidden="true">HO</div>
        <div>
          <div className="ho-eyebrow">Hidden Oasis</div>
          <h1>Accounting & Hotel Operations</h1>
          <p>Secure access to finance, treasury, bookings, folios, compliance, and connected-app review.</p>
        </div>
        <div className="auth-login-features" aria-hidden="true">
          <span>Hotel operations</span>
          <span>Cash & treasury</span>
          <span>Accounting controls</span>
        </div>
      </section>

      <section className="auth-login-card">
        <div>
          <div className="ho-eyebrow">Welcome back</div>
          <h2>Sign in</h2>
          <p className="muted">Use your Hidden Oasis account to continue.</p>
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
                {showPassword ? 'Hide' : 'Show'}
              </button>
            </span>
            {passwordError ? <span id="login-password-error" className="field-error" role="alert">{passwordError}</span> : null}
          </label>
          {error ? <div className="ho-notice ho-notice--danger" role="alert">{error}</div> : null}
          <button type="submit" className="auth-submit" disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="auth-login-help">Cannot access your account? Contact your system administrator.</p>
      </section>
    </div>
  );
}
