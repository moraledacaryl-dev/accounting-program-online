const { test, expect } = require('@playwright/test');

async function fixtures(page, options = {}) {
  const entries = [];
  const attempts = [];
  const accounts = [{ code: '1000', name: 'Cash', is_active: true }, { code: '4000', name: 'Revenue', is_active: true }];
  await page.route('**/api/**', async route => {
    const req = route.request(); const url = new URL(req.url());
    let body = [];
    if (url.pathname === '/api/auth/me') body = { id: 1, username: 'audit-owner', role: 'owner', permissions: options.permissions || ['*'], full_name: 'Review Owner' };
    else if (url.pathname === '/api/auth/csrf') body = { csrf_token: 'test-csrf' };
    else if (url.pathname.startsWith('/api/chart-of-accounts')) body = accounts;
    else if (url.pathname === '/api/dashboard/summary') body = { cash_on_hand: 1000, bank_balance: 2000, receivables_due: 500, payables_due: 200, unreconciled_accounts: 2, pending_review: 3, command_center: {} };
    else if (url.pathname === '/api/journals/entries' && req.method() === 'POST') {
      attempts.push({ key: req.headers()['idempotency-key'], body: req.postDataJSON() });
      if (options.failFirst && attempts.length === 1) return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Please retry this request.' }) });
      body = { id: 1, ...req.postDataJSON(), lines: req.postDataJSON().lines.map((line, id) => ({ id, ...line })) };
      entries.push(body);
    } else if (url.pathname === '/api/journals/entries') body = entries;
    else if (url.pathname === '/api/journals/entries/1') body = { entry: entries[0], audit: [] };
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
  return { attempts };
}

test('journals require meaningful lines and preserve retry identity', async ({ page }) => {
  const { attempts } = await fixtures(page, { failFirst: true });
  await page.goto('/journals');
  await expect(page.getByText('No journal entries on this page.', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Create Entry', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Save entry', exact: true })).toBeDisabled();
  await page.getByLabel('Account 1', { exact: true }).selectOption('1000');
  await page.getByLabel('Debit 1', { exact: true }).fill('100.25');
  await page.getByLabel('Account 2', { exact: true }).selectOption('4000');
  await page.getByLabel('Credit 2', { exact: true }).fill('100.25');
  await page.getByRole('button', { name: 'Save entry', exact: true }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'Please retry' })).toBeVisible();
  await page.getByRole('button', { name: 'Save entry', exact: true }).click();
  await expect(page.getByText('Draft saved. Review it before posting.')).toBeVisible();
  expect(attempts).toHaveLength(2);
  expect(attempts[0].key).toBeTruthy();
  expect(attempts[1].key).toBe(attempts[0].key);
  await page.getByRole('button', { name: 'View journal 1', exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('region', { name: 'Journal details' })).toBeFocused();
});

test('accountant dashboard uses actual finance totals and honest connection labels', async ({ page }) => {
  await fixtures(page);
  await page.goto('/dashboard');
  await expect(page.getByText('Cash and bank', { exact: true })).toBeVisible();
  await expect(page.getByText('₱3,000.00', { exact: true })).toBeVisible();
  await expect(page.getByText('3 events waiting for Accounting review')).toBeVisible();
  await expect(page.getByText('Connected', { exact: true })).toHaveCount(0);
  await expect(page.getByText('Not verified', { exact: true })).toHaveCount(3);
});

test('journal form remains usable on a phone', async ({ page }) => {
  await fixtures(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/journals');
  await page.getByRole('button', { name: 'Create Entry', exact: true }).click();
  await expect(page.getByLabel('Account 1', { exact: true })).toBeVisible();
  const size = await page.evaluate(() => ({ width: innerWidth, content: document.documentElement.scrollWidth }));
  expect(size.content).toBeLessThanOrEqual(size.width + 1);
});
