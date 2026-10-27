const { test, expect } = require('@playwright/test');

test('older authorized attachments can be loaded after the first page', async ({ page }) => {
  const requests = [];
  const firstPage = Array.from({ length: 300 }, (_, index) => ({
    id: 1000 - index, entity_type: 'booking', entity_id: 1,
    file_name: `Recent ${index + 1}.pdf`, size_bytes: 100,
    created_at: '2026-10-27',
  }));
  await page.route('**/api/**', route => {
    const url = new URL(route.request().url());
    let body = [];
    if (url.pathname === '/api/auth/me') body = {
      id: 1, username: 'isolated-auditor', role: 'auditor',
      permissions: ['reports.view', 'bookings.view'], full_name: 'Isolated auditor',
    };
    if (url.pathname === '/api/attachments/') {
      requests.push(url.searchParams.get('before_id'));
      body = url.searchParams.get('before_id') === '701'
        ? [{ id: 700, entity_type: 'booking', entity_id: 1,
          file_name: 'Historical receipt.pdf', size_bytes: 100,
          created_at: '2025-01-01' }]
        : firstPage;
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });

  await page.goto('/attachments');
  await expect(page.getByRole('button', { name: 'Load older files' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Historical receipt.pdf' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Load older files' }).click();
  await expect(page.getByRole('button', { name: 'Historical receipt.pdf' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Load older files' })).toHaveCount(0);
  expect(requests).toEqual([null, '701']);
});
