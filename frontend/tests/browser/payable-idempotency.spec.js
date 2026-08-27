const { test, expect } = require('@playwright/test');

const owner = {
  id: 1,
  username: 'payable-test-owner',
  full_name: 'Payable Test Owner',
  role: 'owner',
  permissions: ['*'],
  is_active: true,
};


test('payable retry reuses the same Idempotency-Key after an ambiguous failure', async ({ page }) => {
  const keys = [];
  let createAttempts = 0;

  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());

    if (url.pathname === '/api/auth/me') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(owner) });
    }
    if (url.pathname === '/api/auth/csrf') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ csrf_token: 'pass64-csrf' }) });
    }
    if (url.pathname === '/api/financial-accounts/') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 1, name: 'Pass 64 Bank', code: 'P64', account_type: 'bank', current_balance: 10000 }]),
      });
    }
    if (url.pathname === '/api/payables/' && request.method() === 'GET') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
    }
    if (url.pathname === '/api/payables/' && request.method() === 'POST') {
      createAttempts += 1;
      keys.push(request.headers()['idempotency-key']);
      if (createAttempts === 1) {
        return route.fulfill({
          status: 503,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Simulated ambiguous network/server failure' }),
        });
      }
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 64,
          supplier_name: 'Retry Safe Supplier',
          payable_type: 'supplier_bill',
          bill_date: '2026-08-27',
          due_date: null,
          gross_amount: 640,
          amount_paid: 0,
          balance_due: 640,
          status: 'open',
        }),
      });
    }

    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });

  await page.goto('/cashflow/payables');
  await expect(page.getByRole('heading', { name: 'Bills to Pay' })).toBeVisible();

  await page.getByLabel('Supplier').fill('Retry Safe Supplier');
  await page.getByLabel('Bill Amount').fill('640');

  await page.getByRole('button', { name: 'Save Bill' }).click();
  await expect(page.getByText('Simulated ambiguous network/server failure')).toBeVisible();

  // The exact same user action must reuse the original key rather than create
  // a second logical payable after an ambiguous first response.
  await page.getByRole('button', { name: 'Save Bill' }).click();
  await expect(page.getByText('Bill saved.')).toBeVisible();

  expect(keys).toHaveLength(2);
  expect(keys[0]).toBeTruthy();
  expect(keys[0]).toBe(keys[1]);
});
