'use client';

import { usePathname } from 'next/navigation';
import Header from '../Header';
import SetupAdministrationNav from '../admin/SetupAdministrationNav';
import FinanceOperationsNav from '../finance/FinanceOperationsNav';
import HotelOperationsNav from '../hotel/HotelOperationsNav';
import InventoryRestaurantNav from '../operations/InventoryRestaurantNav';
import PeoplePayrollNav from '../people/PeoplePayrollNav';
import RouteGuard from '../RouteGuard';
import Sidebar from '../Sidebar';

export default function AppFrame({ children }) {
  const pathname = usePathname();
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

  return (
    <>
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <div className="app-shell">
        <Sidebar />
        <div className="main-shell">
          <Header />
          <HotelOperationsNav />
          <FinanceOperationsNav />
          <PeoplePayrollNav />
          <InventoryRestaurantNav />
          <SetupAdministrationNav />
          <main id="main-content" className="main" tabIndex="-1">
            <RouteGuard>{children}</RouteGuard>
          </main>
        </div>
      </div>
    </>
  );
}
