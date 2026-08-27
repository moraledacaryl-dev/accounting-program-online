const { test, expect } = require('@playwright/test');

const owner = {
  id: 1,
  username: 'business-clock-owner',
  full_name: 'Business Clock Owner',
  role: 'owner',
  permissions: ['*'],
  is_active: true,
};


test('cashflow date default uses Manila business day at the UTC boundary', async ({ page }) => {
  await page.addInitScript(() => {
    const RealDate = Date;
    const fixed = RealDate.parse('2026-08-26T16:30:00.000Z');
    class FixedDate extends RealDate {
      constructor(...args) {
        super(...(args.length ? args : [fixed]));
      }
      static now() {
        return fixed;
      }
    }
    globalThis.Date = FixedDate;
  });

  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());

    if (url.pathname === '/api/auth/me') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(owner) });
    }
    if (url.pathname === '/api/auth/csrf') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ csrf_token: 'pass65-csrf' }) });
    }
    if (url.pathname.startsWith('/api/financial-accounts')) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
    }
    if (url.pathname === '/api/payables' || url.pathname === '/api/payables/') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
    }

    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });

  await page.goto('/cashflow/payables');
  await expect(page.getByRole('heading', { name: 'Bills to Pay', exact: true })).toBeVisible();
  await expect(page.getByLabel('Bill Date', { exact: true })).toHaveValue('2026-08-27');
});
