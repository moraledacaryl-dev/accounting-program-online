'use client';

import { usePathname } from 'next/navigation';
import Header from '../Header';
import RouteGuard from '../RouteGuard';
import Sidebar from '../Sidebar';

export default function AppFrame({ children }) {
  const pathname = usePathname();
  const isAuthenticationRoute = pathname === '/login';

  if (isAuthenticationRoute) {
    return (
      <div className="auth-frame">
        <a className="skip-link" href="#main-content">Skip to sign in</a>
        <main id="main-content" className="auth-main" tabIndex="-1">
          <RouteGuard>{children}</RouteGuard>
        </main>
      </div>
    );
  }

  return (
    <>
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <div className="app-shell">
        <Sidebar />
        <div className="main-shell">
          <Header />
          <main id="main-content" className="main" tabIndex="-1">
            <RouteGuard>{children}</RouteGuard>
          </main>
        </div>
      </div>
    </>
  );
}
