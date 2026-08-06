import './globals.css';
import './design-system.css';
import './app-shell.css';
import './page-hierarchy.css';
import './drawers.css';
import './hotel-operations.css';
import './finance-treasury.css';
import './accounting-reports.css';
import './procurement-inventory-restaurant.css';
import './people-payroll-approvals.css';
import './governance-administration.css';
import './settings-integrations.css';
import './interaction-overlays-polish.css';
import './final-responsive-closure.css';
import './review-inbox.css';
import './admin-settings.css';
import './final-qa.css';
import './pass-1-foundation.css';
import './pass-1-auth.css';
import './pass-3-hotel-operations.css';
import './pass-3-dashboard.css';
import './pass-4-finance.css';
import './pass-5-people-payroll.css';
import './pass-6-inventory-operations.css';
import './pass-7-setup-administration.css';
import './pass-8-final-qa.css';
import './pass-2-global-design-system.css';
import './pass-3-list-first-workflows.css';
import './pass-4-tables-search-filter.css';
import './pass-5-forms-validation-feedback.css';
import './pass-6-record-detail.css';
import './pass-7-dashboard-kpi-refinement.css';
import './pass-8-empty-loading-states.css';
import './pass-9-bulk-actions-selection.css';
import './pass-10-dialogs-drawers-overlays.css';
import './pass-11-notifications-toasts-feedback.css';
import './pass-12-accessibility-keyboard-focus.css';
import './pass-13-responsive-mobile-density.css';
import './pass-14-print-export-documents.css';
import './pass-15-final-consistency-polish.css';
import './pass-16-production-resilience-hardening.css';
import './pass-17-route-failure-recovery.css';
import './pass-19-sidebar-refinement.css';
import './pass-20-page-template-system.css';
import './pass-33-sidebar-search-containment.css';
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
