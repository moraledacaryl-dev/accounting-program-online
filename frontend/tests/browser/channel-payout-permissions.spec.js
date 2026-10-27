const { test, expect } = require('@playwright/test');

async function openPayouts(page, permissions, { conflict = false, refreshFails = false } = {}) {
  const writes = [];
  let bookingLoads = 0;
  await page.route('**/api/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() !== 'GET') writes.push(path);
    let body = [];
    if (path === '/api/auth/me') body = {
      id: 1, username: 'isolated-role', role: 'auditor', full_name: 'Isolated role', permissions,
    };
    if (path === '/api/channel-reconciliation/channels') body = [{ id: 1, code: 'OTA', name: 'Isolated channel' }];
    if (path === '/api/channel-reconciliation/bookings') {
      bookingLoads += 1;
      if (refreshFails && bookingLoads > 1) {
        return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Refresh unavailable.' }) });
      }
      body = conflict && bookingLoads > 1 ? [] : [{
        booking_id: 7, booking_ref: 'ISOLATED-7', guest_name: 'Fixture guest',
        room_name: 'Fixture room', check_in: '2026-10-27', check_out: '2026-10-28',
        booking_status: 'confirmed', original_amount: 100, expected_net_amount: 90,
      }];
    }
    if (path === '/api/channel-reconciliation/reconcile' && conflict) {
      return route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ detail: 'Booking 7 is already marked paid.' }) });
    }
    if (path === '/api/channel-reconciliation/reconcile') {
      body = { booking_count: 1, allocated_amount: 90 };
    }
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

test('stale payout conflict refreshes the awaiting list without a success claim', async ({ page }) => {
  const writes = await openPayouts(page, ['cashflow.view', 'cashflow.money_in'], { conflict: true });
  await page.getByRole('checkbox', { name: 'Select booking ISOLATED-7' }).check();
  await page.getByRole('button', { name: /Record payout/ }).click();
  await expect(page.getByText('A selected booking was already recorded in another session.')).toBeVisible();
  await expect(page.getByRole('checkbox', { name: 'Select booking ISOLATED-7' })).toHaveCount(0);
  await expect(page.getByText(/booking reconciled/)).toHaveCount(0);
  expect(writes).toContain('/api/channel-reconciliation/reconcile');
});

test('stale payout conflict reports a failed refresh honestly', async ({ page }) => {
  await openPayouts(page, ['cashflow.view', 'cashflow.money_in'], { conflict: true, refreshFails: true });
  await page.getByRole('checkbox', { name: 'Select booking ISOLATED-7' }).check();
  await page.getByRole('button', { name: /Record payout/ }).click();
  await expect(page.getByText('The list could not be refreshed')).toBeVisible();
  await expect(page.getByRole('checkbox', { name: 'Select booking ISOLATED-7' })).toBeVisible();
});

test('recorded payout keeps its success message if the follow-up refresh fails', async ({ page }) => {
  await openPayouts(page, ['cashflow.view', 'cashflow.money_in'], { refreshFails: true });
  await page.getByRole('checkbox', { name: 'Select booking ISOLATED-7' }).check();
  await page.getByRole('button', { name: /Record payout/ }).click();
  await expect(page.getByText('1 booking reconciled.')).toBeVisible();
  await expect(page.getByText('Payout recorded, but the lists could not be refreshed.')).toBeVisible();
  await expect(page.getByText('Failed to reconcile payout.')).toHaveCount(0);
});
