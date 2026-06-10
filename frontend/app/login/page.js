'use client';
import { useState } from 'react';
import { clearToken, login } from '../../lib/api';

const styles = {
  shell: {
    minHeight: '100vh',
    display: 'grid',
    placeItems: 'center',
    padding: 24,
    background: 'radial-gradient(circle at top left, #f7fbf8 0, transparent 32%), radial-gradient(circle at bottom right, #edf5f0 0, transparent 28%), #f6f6f4',
  },
  card: {
    width: 'min(420px, 100%)',
    display: 'grid',
    gap: 18,
    padding: 30,
    borderRadius: 22,
    border: '1px solid #e1e6df',
    background: 'rgba(255,255,255,.9)',
    boxShadow: '0 24px 70px rgba(26,38,30,.09)',
  },
  mark: {
    width: 48,
    height: 48,
    display: 'grid',
    placeItems: 'center',
    borderRadius: 15,
    background: '#1f6a47',
    color: '#fff',
    fontWeight: 720,
    letterSpacing: '.03em',
  },
  title: { margin: 0, fontSize: 34, letterSpacing: '-.04em', lineHeight: 1 },
  form: { display: 'grid', gap: 13 },
  label: { display: 'grid', gap: 6, fontSize: 12, fontWeight: 650, color: '#565b55' },
  input: { width: '100%', padding: '11px 12px', borderRadius: 12, border: '1px solid #d7dad4', background: '#fff' },
  button: { width: '100%', padding: '11px 12px', borderRadius: 12, border: '1px solid #111', background: '#111', color: '#fff', fontWeight: 650, cursor: 'pointer' },
  credit: { color: '#7b8179', fontSize: 12 },
  error: { color: '#b42318', fontSize: 13, margin: 0 },
};

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
    <main style={styles.shell}>
      <section style={styles.card}>
        <div style={styles.mark}>HO</div>
        <h1 style={styles.title}>Accounting</h1>
        <form onSubmit={submit} style={styles.form}>
          <label style={styles.label}>Username<input style={styles.input} required autoComplete="username" value={username} onChange={e=>setUsername(e.target.value)} /></label>
          <label style={styles.label}>Password<input style={styles.input} required autoComplete="current-password" type="password" value={password} onChange={e=>setPassword(e.target.value)} /></label>
          {error && <p style={styles.error}>{error}</p>}
          <button style={styles.button} type="submit">Sign in</button>
        </form>
        <small style={styles.credit}>by C.M.</small>
      </section>
    </main>
  );
}
