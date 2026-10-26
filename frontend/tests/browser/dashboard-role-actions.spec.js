const { test, expect } = require('@playwright/test');

const summary = {
  pending_review: 3,
  pending_approvals: 2,
  cash_on_hand: 100,
  bank_balance: 200,
  command_center: { open_folio_alerts: [{ id: 1, balance: 50 }] },
};

async function openDashboard(page, role, permissions) {
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname;
    const body = path === '/api/auth/me'
      ? { id: 1, username: `fixture-${role}`, full_name: `Fixture ${role}`, role, permissions }
      : path === '/api/dashboard/summary' ? summary : [];
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.goto('/dashboard');
  await expect(page.getByRole('heading', { name: /Fixture/ })).toBeVisible();
}

test('Owner sees actionable review count and allowed work links', async ({ page }) => {
  await openDashboard(page, 'owner', ['*']);
  const actions = page.locator('.dashboard-action-center');
  await expect(actions.getByRole('link', { name: /Validate connected-app events 3 events waiting/ })).toBeVisible();
  await expect(actions.getByRole('link', { name: /Review pending approvals/ })).toBeVisible();
  await expect(actions.getByRole('link', { name: /Complete cash close/ })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Booking calendar' })).toBeVisible();
});

test('Staff dashboard does not offer actions outside its role', async ({ page }) => {
  await openDashboard(page, 'staff', ['dashboard.view', 'bookings.view', 'cashflow.view', 'inventory.view', 'restaurant.view']);
  const actions = page.locator('.dashboard-action-center');
  await expect(actions.getByRole('link', { name: /Validate connected-app events/ })).toHaveCount(0);
  await expect(actions.getByRole('link', { name: /Resolve guest balances/ })).toHaveCount(0);
  await expect(actions.getByRole('link', { name: /Complete cash close/ })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'New booking' })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Open Review Inbox' })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Booking calendar' })).toBeVisible();
  await expect(page.locator('.dashboard-integrations')).toContainText('Inventory & Procurement');
  await expect(page.locator('.dashboard-integrations')).not.toContainText('Staff & Payroll');
});

test('Accounting reviewer sees reports and integration history without forbidden approval links', async ({ page }) => {
  await openDashboard(page, 'accounting_admin', ['dashboard.view', 'reports.view', 'journals.view', 'cashflow.view', 'integrations.view']);
  const actions = page.locator('.dashboard-action-center');
  await expect(actions.getByRole('link', { name: /Review pending approvals/ })).toHaveCount(0);
  await expect(actions.getByRole('link', { name: /Validate connected-app events/ })).toHaveCount(0);
  await expect(actions.getByRole('link', { name: /Resolve guest balances/ })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Booking calendar' })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Review financial reports' })).toBeVisible();
  await expect(page.locator('.dashboard-integrations-panel').getByRole('link', { name: 'Open Review Inbox' })).toBeVisible();
  await expect(page.locator('.dashboard-integrations')).not.toContainText('Staff & Payroll');
});
