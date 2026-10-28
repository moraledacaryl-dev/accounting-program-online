const { test, expect } = require('@playwright/test');

async function delayedChannelFixture(page, { firstFails = false, currentFails = false } = {}) {
  let releaseFirst;
  let firstRequested;
  const firstCanFinish = new Promise((resolve) => { releaseFirst = resolve; });
  const firstStarted = new Promise((resolve) => { firstRequested = resolve; });
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    let body = [];
    if (url.pathname === '/api/auth/me') body = {
      id: 1, username: 'isolated-cashier', role: 'cashier',
      full_name: 'Isolated Cashier', permissions: ['cashflow.view', 'cashflow.money_in'],
    };
    if (url.pathname === '/api/channel-reconciliation/channels') body = [
      { id: 1, code: 'A', name: 'Channel A' },
      { id: 2, code: 'B', name: 'Channel B' },
    ];
    if (url.pathname === '/api/channel-reconciliation/bookings') {
      if (url.searchParams.get('channel_id') === '1') {
        firstRequested();
        await firstCanFinish;
        if (firstFails) return route.fulfill({
          status: 503, contentType: 'application/json',
          body: JSON.stringify({ detail: 'Old channel unavailable.' }),
        });
        body = [{ booking_id: 1, booking_ref: 'CHANNEL-A-1', guest_name: 'Synthetic A',
          channel_id: 1, original_amount: 100, expected_net_amount: 90 }];
      } else {
        if (currentFails) return route.fulfill({
          status: 503, contentType: 'application/json',
          body: JSON.stringify({ detail: 'Current channel unavailable.' }),
        });
        body = [{ booking_id: 2, booking_ref: 'CHANNEL-B-2', guest_name: 'Synthetic B',
          channel_id: 2, original_amount: 100, expected_net_amount: 90 }];
      }
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.goto('/channel-payouts');
  await Promise.race([
    firstStarted,
    new Promise((_, reject) => setTimeout(() => reject(new Error('Channel A request did not start')), 5000)),
  ]);
  return releaseFirst;
}

test('slow previous channel response cannot replace the current booking list', async ({ page }) => {
  const releaseFirst = await delayedChannelFixture(page);
  await expect(page.getByText('Loading channel bookings…')).toBeVisible();
  await page.getByLabel('Booking channel').selectOption('2');
  await expect(page.getByText('CHANNEL-B-2')).toBeVisible();
  const oldResponse = page.waitForResponse((response) => response.url().includes('/channel-reconciliation/bookings?channel_id=1'));
  releaseFirst();
  await oldResponse;
  await page.waitForTimeout(150);
  await expect(page.getByText('CHANNEL-B-2')).toBeVisible();
  await expect(page.getByText('CHANNEL-A-1')).toHaveCount(0);
});

test('old channel failure cannot show an error over the current channel', async ({ page }) => {
  const releaseFirst = await delayedChannelFixture(page, { firstFails: true });
  await page.getByLabel('Booking channel').selectOption('2');
  await expect(page.getByText('CHANNEL-B-2')).toBeVisible();
  const oldResponse = page.waitForResponse((response) => response.url().includes('/channel-reconciliation/bookings?channel_id=1'));
  releaseFirst();
  await oldResponse;
  await page.waitForTimeout(150);
  await expect(page.getByText('CHANNEL-B-2')).toBeVisible();
  await expect(page.getByText('Old channel unavailable.')).toHaveCount(0);
});

test('current channel failure is not presented as no unpaid bookings', async ({ page }) => {
  const releaseFirst = await delayedChannelFixture(page, { currentFails: true });
  await page.getByLabel('Booking channel').selectOption('2');
  await expect(page.getByText('Current channel unavailable.')).toBeVisible();
  await expect(page.getByText('Channel bookings could not be loaded. Refresh to try again.')).toBeVisible();
  await expect(page.getByText('No unpaid bookings for this channel.')).toHaveCount(0);
  releaseFirst();
});

test('loading state remains readable on a narrow phone', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const releaseFirst = await delayedChannelFixture(page);
  const status = page.getByText('Loading channel bookings…');
  await expect(status).toBeVisible();
  const box = await status.boundingBox();
  expect(box).not.toBeNull();
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(390);
  releaseFirst();
});
