const { test, expect } = require('@playwright/test');
const { default: AxeBuilder } = require('@axe-core/playwright');

const routes = [
  '/dashboard', '/start-of-day', '/review-inbox', '/reconciliation-center',
  '/approvals', '/cashflow', '/cashflow/receivables', '/cashflow/payables',
  '/bookings', '/guests', '/channel-payouts', '/purchase-orders',
  '/journals', '/reports', '/attachments', '/users', '/system-settings',
];

async function fixture(page) {
  await page.route('**/api/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    const body = path === '/api/auth/me'
      ? { id: 1, username: 'isolated-a11y-owner', full_name: 'Isolated Owner', role: 'owner', permissions: ['*'] }
      : [];
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
}

for (const width of [320, 390, 768, 1024, 1440]) {
  for (const route of routes) {
    test(`major route accessibility ${width}px ${route}`, async ({ page }) => {
      await fixture(page);
      await page.setViewportSize({ width, height: 900 });
      await page.goto(route);
      await page.waitForLoadState('networkidle');
      await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible();
      const result = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
        .analyze();
      expect(result.violations.map(({ id, impact, nodes }) => ({
        id, impact, targets: nodes.map(({ target }) => target),
      }))).toEqual([]);
    });
  }
}

test('channel payout view controls expose the current view', async ({ page }) => {
  await fixture(page);
  await page.goto('/channel-payouts');
  const views = page.getByRole('group', { name: 'Channel payout views' });
  const awaiting = views.getByRole('button', { name: 'Awaiting payout' });
  const history = views.getByRole('button', { name: 'Payout history' });
  await expect(awaiting).toHaveAttribute('aria-pressed', 'true');
  await expect(history).toHaveAttribute('aria-pressed', 'false');
  await history.click();
  await expect(history).toHaveAttribute('aria-pressed', 'true');
  await expect(awaiting).toHaveAttribute('aria-pressed', 'false');
});
