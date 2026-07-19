import './globals.css';
import './design-system.css';
import './app-shell.css';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import RouteGuard from '../components/RouteGuard';
import ConfirmActionProvider from '../components/ConfirmActionProvider';
import { AppShellProvider } from '../components/app-shell/AppShellContext';
import { CurrentUserProvider } from '../lib/useCurrentUser';

export const metadata = { title: 'Hidden Oasis Accounting' };

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <CurrentUserProvider>
          <AppShellProvider>
            <ConfirmActionProvider>
              <div className="app-shell">
                <Sidebar />
                <div className="main-shell">
                  <Header />
                  <main className="main">
                    <RouteGuard>{children}</RouteGuard>
                  </main>
                </div>
              </div>
            </ConfirmActionProvider>
          </AppShellProvider>
        </CurrentUserProvider>
      </body>
    </html>
  );
}
