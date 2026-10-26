'use client';

import { useState } from 'react';
import { login } from '../../lib/api';

function safeReturnPath(candidate) {
  if (!candidate || !candidate.startsWith('/') || candidate.startsWith('//')) return '/dashboard';
  try {
    const target = new URL(candidate, window.location.origin);
    if (target.origin !== window.location.origin || target.pathname === '/login') return '/dashboard';
    return `${target.pathname}${target.search}${target.hash}`;
  } catch {
    return '/dashboard';
  }
}

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
      window.location.href = safeReturnPath(searchParams.get('next'));
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
              autoFocus
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
                className="auth-password-toggle"
                onClick={() => setShowPassword((value) => !value)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                disabled={busy}
              >
                <span className="auth-password-toggle-label" aria-hidden="true">{showPassword ? 'Hide' : 'Show'}</span>
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
