import './globals.css';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import RouteGuard from '../components/RouteGuard';
import ConfirmActionProvider from '../components/ConfirmActionProvider';
import { AppShellProvider } from '../components/app-shell/AppShellContext';

export const metadata = { title: 'Hidden Oasis Accounting' };

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
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
      </body>
    </html>
  );
}
