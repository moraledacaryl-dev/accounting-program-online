'use client';

import { useState } from 'react';
import { clearToken, login } from '../../lib/api';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      await login({ username, password });
      clearToken();
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

        <form onSubmit={submit} className="auth-login-form">
          <label>
            Username
            <input
              data-drawer-autofocus
              required
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              disabled={busy}
            />
          </label>
          <label>
            Password
            <span className="auth-password-field">
              <input
                required
                autoComplete="current-password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
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
