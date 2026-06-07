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
      setError(e.message);
    }
  }

  return (
    <section className="section" style={{maxWidth: 520}}>
      <h1>Login</h1>
      <p className="muted">Sign in with your assigned Accounting account.</p>
      <form onSubmit={submit}>
        <div className="form-grid">
          <label>Username<input required autoComplete="username" value={username} onChange={e=>setUsername(e.target.value)} /></label>
          <label>Password<input required autoComplete="current-password" type="password" value={password} onChange={e=>setPassword(e.target.value)} /></label>
        </div>
        {error && <p className="small error-text">{error}</p>}
        <button type="submit">Login</button>
      </form>
    </section>
  );
}
