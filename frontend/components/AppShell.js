'use client';

import { useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { clearToken } from '../lib/api';
import { useCurrentUser } from '../lib/useCurrentUser';
import Header from './Header';
import RouteGuard from './RouteGuard';
import Sidebar from './Sidebar';

export default function AppShell({ children }) {
  const pathname = usePathname();
  const isLogin = pathname === '/login';
  const { loaded, user } = useCurrentUser();

  useEffect(() => {
    if (isLogin || !loaded || user) return;
    clearToken();
    const next = pathname && pathname !== '/' ? `?next=${encodeURIComponent(pathname)}` : '';
    window.location.replace(`/login${next}`);
  }, [isLogin, loaded, pathname, user]);

  if (!isLogin && !loaded) {
    return (
      <div className="app-shell auth-shell">
        <main className="main auth-main">
          <section className="section auth-status-card">
            <h1>Checking Access</h1>
            <p className="muted">Confirming your session before opening the workspace.</p>
          </section>
        </main>
      </div>
    );
  }

  if (!isLogin && loaded && !user) {
    return (
      <div className="app-shell auth-shell">
        <main className="main auth-main">
          <section className="section auth-status-card">
            <h1>Opening Login</h1>
            <p className="muted">Your session is not active. Redirecting to the login page.</p>
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className={isLogin ? 'app-shell auth-shell' : 'app-shell'}>
      {!isLogin && <Sidebar />}
      <div className="main-shell">
        {!isLogin && <Header />}
        <main className={isLogin ? 'main auth-main' : 'main'}>
          <RouteGuard>{children}</RouteGuard>
        </main>
      </div>
    </div>
  );
}
