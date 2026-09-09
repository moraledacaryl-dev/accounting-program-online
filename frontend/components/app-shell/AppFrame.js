'use client';

import { usePathname } from 'next/navigation';
import { Suspense } from 'react';
import AccessibilityEnhancer from '../AccessibilityEnhancer';
import ExternalOwnershipBoundary from '../ExternalOwnershipBoundary';
import Header from '../Header';
import SectionNavigation from './SectionNavigation';
import RouteGuard from '../RouteGuard';
import Sidebar from '../Sidebar';
import { useAppShell } from './AppShellContext';

export default function AppFrame({ children }) {
  const pathname = usePathname();
  const { loaded, user } = useAppShell();
  const isAuthenticationRoute = pathname === '/login';

  if (isAuthenticationRoute) {
    return (
      <div className="auth-frame">
        <a className="skip-link" href="#main-content">Skip to sign in</a>
        <div id="main-content" className="auth-main" role="main" tabIndex="-1">
          <RouteGuard>{children}</RouteGuard>
        </div>
      </div>
    );
  }

  if (!loaded || !user) {
    return (
      <main id="main-content" className="main" tabIndex="-1">
        <RouteGuard>{children}</RouteGuard>
      </main>
    );
  }

  return (
    <>
      <AccessibilityEnhancer />
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <div className="app-shell">
        <Suspense fallback={null}><Sidebar /></Suspense>
        <div className="main-shell">
          <Header />
          <Suspense fallback={null}><SectionNavigation /></Suspense>
          <div className="shell-content">
            <main id="main-content" className="main" data-route={pathname} tabIndex="-1">
              <RouteGuard>
                <ExternalOwnershipBoundary>{children}</ExternalOwnershipBoundary>
              </RouteGuard>
            </main>
          </div>
        </div>
      </div>
    </>
  );
}
