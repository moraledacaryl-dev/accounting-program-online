import './globals.css';
import './design-system.css';
import './app-shell.css';
import './page-hierarchy.css';
import './drawers.css';
import './hotel-operations.css';
import './finance-treasury.css';
import './review-inbox.css';
import './admin-settings.css';
import './final-qa.css';
import './pass-1-foundation.css';
import ConfirmActionProvider from '../components/ConfirmActionProvider';
import AppFrame from '../components/app-shell/AppFrame';
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
              <AppFrame>{children}</AppFrame>
            </ConfirmActionProvider>
          </AppShellProvider>
        </CurrentUserProvider>
      </body>
    </html>
  );
}
