import './globals.css';
import AppShell from '../components/AppShell';
import ConfirmActionProvider from '../components/ConfirmActionProvider';
import { CurrentUserProvider } from '../lib/useCurrentUser';

export const metadata = { title: 'Resort Accounting ERP' };

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <CurrentUserProvider>
          <ConfirmActionProvider>
            <AppShell>{children}</AppShell>
          </ConfirmActionProvider>
        </CurrentUserProvider>
      </body>
    </html>
  );
}
