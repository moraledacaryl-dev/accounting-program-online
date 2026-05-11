'use client';
import { useState } from 'react';
import { login, setToken } from '../../lib/api';

export default function LoginPage() {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('admin123');
  const [error, setError] = useState('');

  async function submit(e) {
    e.preventDefault();
    setError('');
    try {
      const data = await login({ username, password });
      setToken(data.access_token);
      window.location.href = '/';
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <section className="section" style={{maxWidth: 520}}>
      <h1>Login</h1>
      <p className="muted">Use bootstrap on the home page first if this is your first run.</p>
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
