import './globals.css';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import RouteGuard from '../components/RouteGuard';

export const metadata = { title: 'Resort Accounting ERP' };

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <div className="app-shell">
          <Sidebar />
          <div className="main-shell">
            <Header />
            <main className="main">
              <RouteGuard>{children}</RouteGuard>
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}
