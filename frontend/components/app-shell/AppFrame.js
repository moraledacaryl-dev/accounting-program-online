'use client';

import { usePathname } from 'next/navigation';
import AccessibilityEnhancer from '../AccessibilityEnhancer';
import ExternalOwnershipBoundary from '../ExternalOwnershipBoundary';
import Header from '../Header';
import SetupAdministrationNav from '../admin/SetupAdministrationNav';
import FinanceOperationsNav from '../finance/FinanceOperationsNav';
import HotelOperationsNav from '../hotel/HotelOperationsNav';
import InventoryRestaurantNav from '../operations/InventoryRestaurantNav';
import PeoplePayrollNav from '../people/PeoplePayrollNav';
import RouteGuard from '../RouteGuard';
import Sidebar from '../Sidebar';

const CONTEXT_NAVIGATION = [
  {
    key: 'people-payroll',
    prefixes: ['/employees', '/attendance', '/payroll-periods', '/approvals', '/integrations/payroll', '/staff-guide'],
    Component: PeoplePayrollNav,
  },
  {
    key: 'finance',
    prefixes: ['/cashflow', '/journals', '/bir', '/assets', '/reports', '/attachments'],
    Component: FinanceOperationsNav,
  },
  {
    key: 'inventory-restaurant',
    prefixes: [
      '/inventory-items', '/inventory-reconciliation', '/stock-movements', '/suppliers',
      '/purchase-requests', '/purchase-orders', '/receiving', '/setup-imports',
      '/restaurant-ops', '/menu-categories', '/menu-items', '/recipes', '/staff-meals',
    ],
    Component: InventoryRestaurantNav,
  },
  {
    key: 'hotel',
    prefixes: [
      '/bookings', '/guests', '/room-folios', '/channel-payouts', '/events',
      '/workspace/rooms', '/workspace/events',
    ],
    Component: HotelOperationsNav,
  },
  {
    key: 'setup',
    prefixes: [
      '/room-types', '/rooms', '/room-setup', '/rate-plans', '/room-package-rules',
      '/booking-channels', '/channels', '/chart-of-accounts', '/account-mapping',
      '/master-data', '/taxonomy-admin', '/users', '/roles-permissions',
      '/integrations/beds24', '/system-settings',
    ],
    Component: SetupAdministrationNav,
  },
];

function contextNavigationForPath(pathname = '') {
  return CONTEXT_NAVIGATION.find(({ prefixes }) =>
    prefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)),
  ) || null;
}

export default function AppFrame({ children }) {
  const pathname = usePathname();
  const isAuthenticationRoute = pathname === '/login';
  const contextNavigation = contextNavigationForPath(pathname);
  const ContextNavigation = contextNavigation?.Component || null;

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

  return (
    <>
      <AccessibilityEnhancer />
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <div className="app-shell">
        <Sidebar />
        <div className="main-shell">
          <Header />
          {ContextNavigation && (
            <div className="context-nav-stack" data-context-section={contextNavigation.key}>
              <ContextNavigation />
            </div>
          )}
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
