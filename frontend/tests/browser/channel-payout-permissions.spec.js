const { test, expect } = require('@playwright/test');

async function openPayouts(page, permissions) {
  const writes = [];
  await page.route('**/api/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() !== 'GET') writes.push(path);
    let body = [];
    if (path === '/api/auth/me') body = {
      id: 1, username: 'isolated-role', role: 'auditor', full_name: 'Isolated role', permissions,
    };
    if (path === '/api/channel-reconciliation/channels') body = [{ id: 1, code: 'OTA', name: 'Isolated channel' }];
    if (path === '/api/channel-reconciliation/bookings') body = [{
      booking_id: 7, booking_ref: 'ISOLATED-7', guest_name: 'Fixture guest',
      room_name: 'Fixture room', check_in: '2026-10-27', check_out: '2026-10-28',
      booking_status: 'confirmed', original_amount: 100, expected_net_amount: 90,
    }];
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.goto('/channel-payouts');
  await expect(page.getByText('ISOLATED-7')).toBeVisible();
  return writes;
}

test('report reader can inspect payouts without recording controls', async ({ page }) => {
  const writes = await openPayouts(page, ['reports.view']);
  await expect(page.getByRole('status')).toContainText('read-only for your role');
  await expect(page.getByRole('checkbox', { name: 'Select booking ISOLATED-7' })).toHaveCount(0);
  await expect(page.getByRole('spinbutton', { name: 'Expected payout for ISOLATED-7' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /Record payout/ })).toHaveCount(0);
  await page.getByRole('button', { name: 'Payout history' }).click();
  await expect(page.getByText('No reconciled booking payouts yet.')).toBeVisible();
  expect(writes).toEqual([]);
});

test('cashflow writer retains payout selection and recording controls', async ({ page }) => {
  const writes = await openPayouts(page, ['cashflow.view', 'cashflow.money_in']);
  await expect(page.getByRole('checkbox', { name: 'Select booking ISOLATED-7' })).toBeVisible();
  await page.getByRole('checkbox', { name: 'Select booking ISOLATED-7' }).check();
  await expect(page.getByRole('button', { name: /Record payout/ })).toBeEnabled();
  expect(writes).toEqual([]);
});
