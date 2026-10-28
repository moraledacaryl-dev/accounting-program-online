const { test, expect } = require('@playwright/test');

const firstPage = Array.from({ length: 200 }, (_, index) => ({
  id: 300 - index,
  booking_id: 300 - index,
  booking_ref: `ISOLATED-${300 - index}`,
  channel_id: 1,
  channel_name: 'Synthetic channel',
  actual_payout_date: '2026-10-28',
  expected_amount: 100,
  actual_amount: 90,
  gross_amount: 120,
}));

async function openHistory(page, { olderFails = false, initialFails = false, initialMalformed = false } = {}) {
  const cursors = [];
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    let body = [];
    if (url.pathname === '/api/auth/me') body = {
      id: 1, username: 'isolated-reader', role: 'auditor',
      full_name: 'Isolated reader', permissions: ['reports.view'],
    };
    if (url.pathname === '/api/channel-reconciliation/channels') body = [{
      id: 1, code: 'SYNTH', name: 'Synthetic channel',
    }];
    if (url.pathname === '/api/channel-reconciliation/history') {
      cursors.push({
        date: url.searchParams.get('before_date'),
        id: url.searchParams.get('before_id'),
        limit: url.searchParams.get('limit'),
      });
      if (cursors.length === 1 && initialFails) return route.fulfill({
        status: 503, contentType: 'application/json',
        body: JSON.stringify({ detail: 'Synthetic history outage.' }),
      });
      if (cursors.length === 1 && initialMalformed) body = { items: [] };
      else if (cursors.length === 1) body = firstPage;
      else if (olderFails) return route.fulfill({
        status: 503, contentType: 'application/json',
        body: JSON.stringify({ detail: 'Synthetic history outage.' }),
      });
      else body = [{
        id: 100, booking_id: 100, booking_ref: 'ISOLATED-100',
        channel_id: 1, channel_name: 'Synthetic channel',
        actual_payout_date: '2026-10-27', expected_amount: 100,
        actual_amount: 90, gross_amount: 120,
      }];
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.goto('/channel-payouts');
  await page.getByRole('button', { name: 'Payout history' }).click();
  if (!initialFails && !initialMalformed) await expect(page.getByText('Showing 200 payout records; older records are available below.')).toBeVisible();
  return cursors;
}

test('read-only payout history loads older records with a stable cursor', async ({ page }) => {
  const cursors = await openHistory(page);
  await page.getByRole('button', { name: 'Load older payouts' }).click();
  await expect(page.getByText('Showing 201 payout records.')).toBeVisible();
  await expect(page.getByText('ISOLATED-100')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Load older payouts' })).toHaveCount(0);
  expect(cursors).toEqual([
    { date: null, id: null, limit: '200' },
    { date: '2026-10-28', id: '101', limit: '200' },
  ]);
});

test('failed older-history request preserves the loaded records', async ({ page }) => {
  await openHistory(page, { olderFails: true });
  await page.getByRole('button', { name: 'Load older payouts' }).click();
  await expect(page.getByText('Synthetic history outage.')).toBeVisible();
  await expect(page.getByText('Showing 200 payout records; older records are available below.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Load older payouts' })).toBeEnabled();
});

test('initial history failure does not claim there are no reconciled payouts', async ({ page }) => {
  await openHistory(page, { initialFails: true });
  await expect(page.getByText('Payout history could not be loaded. Refresh the page to try again.')).toBeVisible();
  await expect(page.getByText('No reconciled booking payouts yet.')).toHaveCount(0);
});

test('unexpected history response does not appear as an empty payout history', async ({ page }) => {
  await openHistory(page, { initialMalformed: true });
  await expect(page.getByText('Payout history returned an unexpected response.')).toBeVisible();
  await expect(page.getByText('No reconciled booking payouts yet.')).toHaveCount(0);
});
