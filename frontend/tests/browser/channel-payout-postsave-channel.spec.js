const { test, expect } = require('@playwright/test');

async function setup(page, { conflict = false } = {}) {
  let releasePayout;
  let payoutStarted;
  const payoutCanFinish = new Promise((resolve) => { releasePayout = resolve; });
  const payoutIsPending = new Promise((resolve) => { payoutStarted = resolve; });
  const bookingRequests = [];
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    let body = [];
    if (path === '/api/auth/me') body = {
      id: 1, username: 'isolated-cashier', role: 'cashier',
      full_name: 'Isolated Cashier', permissions: ['cashflow.view', 'cashflow.money_in'],
    };
    if (path === '/api/channel-reconciliation/channels') body = [
      { id: 1, code: 'A', name: 'Channel A' },
      { id: 2, code: 'B', name: 'Channel B' },
    ];
    if (path === '/api/channel-reconciliation/bookings') {
      const channel = url.searchParams.get('channel_id');
      bookingRequests.push(channel);
      body = [{
        booking_id: Number(channel), booking_ref: `CHANNEL-${channel}`,
        guest_name: `Synthetic ${channel}`, channel_id: Number(channel),
        original_amount: 100, expected_net_amount: 90,
      }];
    }
    if (path === '/api/channel-reconciliation/reconcile') {
      payoutStarted();
      await payoutCanFinish;
      return route.fulfill({
        status: conflict ? 409 : 200, contentType: 'application/json',
        body: JSON.stringify(conflict ? { detail: 'Already recorded.' } : { booking_count: 1, allocated_amount: 90 }),
      });
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.goto('/channel-payouts');
  await expect(page.getByText('CHANNEL-1')).toBeVisible();
  return { releasePayout, payoutIsPending, bookingRequests };
}

for (const conflict of [false, true]) {
  test(`${conflict ? 'conflicted' : 'recorded'} payout does not replace a newly selected channel`, async ({ page }) => {
    const { releasePayout, payoutIsPending, bookingRequests } = await setup(page, { conflict });
    await page.getByRole('checkbox', { name: 'Select booking CHANNEL-1' }).check();
    await page.getByRole('button', { name: /Record payout/ }).click();
    await payoutIsPending;
    await page.getByRole('combobox', { name: /Booking channel/ }).selectOption('2');
    await expect(page.getByText('CHANNEL-2')).toBeVisible();
    await page.getByRole('checkbox', { name: 'Select booking CHANNEL-2' }).check();
    await page.getByRole('textbox', { name: 'Statement / reference' }).fill('B-only');
    releasePayout();
    await expect(page.getByText(conflict ? /already recorded in another session/ : /booking reconciled/)).toBeVisible();
    await page.waitForTimeout(150);
    await expect(page.getByText('CHANNEL-2')).toBeVisible();
    await expect(page.getByRole('checkbox', { name: 'Select booking CHANNEL-2' })).toBeChecked();
    await expect(page.getByRole('textbox', { name: 'Statement / reference' })).toHaveValue('B-only');
    expect(bookingRequests).toEqual(['1', '2']);
  });
}

test('switching channels clears the prior channel payout reference', async ({ page }) => {
  await setup(page);
  const reference = page.getByRole('textbox', { name: 'Statement / reference' });
  await reference.fill('A-only');
  await page.getByRole('combobox', { name: /Booking channel/ }).selectOption('2');
  await expect(page.getByText('CHANNEL-2')).toBeVisible();
  await expect(reference).toHaveValue('');
});

