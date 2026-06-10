'use client';
import { useState } from 'react';
import { clearToken, login } from '../../lib/api';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  async function submit(e) {
    e.preventDefault();
    setError('');
    try {
      await login({ username, password });
      clearToken();
      const searchParams = new URLSearchParams(window.location.search);
      const next = searchParams.get('next') || '/';
      window.location.href = next.startsWith('/') && !next.startsWith('//') ? next : '/';
    } catch (e) {
      setError(e.message || 'Invalid username or password.');
    }
  }

  return (
    <section className="section login-panel" style={{maxWidth: 520}}>
      <div className="login-mark">HO</div>
      <h1>Accounting</h1>
      <form onSubmit={submit}>
        <div className="form-grid">
          <label>Username<input required autoComplete="username" value={username} onChange={e=>setUsername(e.target.value)} /></label>
          <label>Password<input required autoComplete="current-password" type="password" value={password} onChange={e=>setPassword(e.target.value)} /></label>
        </div>
        {error && <p className="small error-text">{error}</p>}
        <button type="submit">Sign in</button>
      </form>
      <small className="muted">by C.M.</small>
    </section>
  );
}
