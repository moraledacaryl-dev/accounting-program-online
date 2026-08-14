const { test, expect } = require('@playwright/test');

const owner = {
  id: 1,
  username: 'route-test-owner',
  full_name: 'Route Test Owner',
  role: 'owner',
  permissions: ['*'],
  is_active: true,
};

async function installApiFixtures(page, undefinedRequests) {
  page.on('request', (request) => {
    if (request.url().includes('undefined')) undefinedRequests.push(request.url());
  });

  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const path = `${url.pathname}${url.search}`;
    let body = [];

    if (url.pathname === '/api/auth/me') {
      body = owner;
    } else if (url.pathname === '/api/reservations/bookings/2') {
      body = {
        id: 2,
        status: 'confirmed',
        guest_full_name: 'Route Test Guest',
        room_display_name: 'Route Test Room',
        room_type_display_name: 'Deluxe',
        check_in: '2026-08-15',
        check_out: '2026-08-16',
        gross_amount: 5000,
        deposit_amount: 1000,
        primary_folio_id: 1,
      };
    } else if (url.pathname === '/api/reservations/breakfast-logs') {
      body = [];
    } else if (url.pathname === '/api/guests/1/history') {
      body = {
        guest: { id: 1, full_name: 'Route Test Guest', is_active: true },
        bookings: [], stay_history: [], payment_history: [], folio_history: [], outstanding_balance: 0,
      };
    } else if (url.pathname === '/api/room-folios' && url.searchParams.get('guest_id') === '1') {
      body = [];
    } else if (url.pathname === '/api/room-folios/1') {
      body = {
        id: 1,
        folio_no: 'FOLIO-ROUTE-1',
        status: 'open',
        booking_id: 2,
        booking_ref: 'BOOK-2',
        guest_id: 1,
        guest_name: 'Route Test Guest',
        charges: 5000,
        deposits: 1000,
        payments: 1000,
        balance: 4000,
        lines: [],
      };
    } else if (url.pathname === '/api/payroll-periods/1') {
      body = {
        id: 1,
        name: 'Route Test Payroll',
        period_start: '2026-08-01',
        period_end: '2026-08-15',
        status: 'draft',
        source_type: 'manual',
        line_count: 0,
        gross_total: 0,
        net_total: 0,
        deductions_total: 0,
        employer_contribution_total: 0,
        lines: [],
      };
    } else if (url.pathname === '/api/dashboard/summary') {
      body = {};
    } else if (path.includes('/api/system-settings')) {
      body = {};
    } else if (path.includes('/api/roles') || path.includes('/api/permissions')) {
      body = [];
    } else if (path.includes('/api/taxonomy')) {
      body = [];
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
}

for (const scenario of [
  { path: '/bookings/2', text: 'Route Test Room' },
  { path: '/guests/1', text: 'Route Test Guest' },
  { path: '/room-folios/1', text: 'FOLIO-ROUTE-1' },
  { path: '/payroll-periods/1', text: 'Route Test Payroll' },
]) {
  test(`${scenario.path} resolves dynamic params and renders record content`, async ({ page }) => {
    const undefinedRequests = [];
    await installApiFixtures(page, undefinedRequests);
    await page.goto(scenario.path);
    await expect(page.getByText(scenario.text, { exact: false }).first()).toBeVisible();
    expect(undefinedRequests).toEqual([]);
  });
}

test('/records/inventory resolves module before redirecting', async ({ page }) => {
  const undefinedRequests = [];
  await installApiFixtures(page, undefinedRequests);
  await page.goto('/records/inventory');
  await expect(page).toHaveURL(/\/workspace\/inventory\?tab=records$/);
  expect(undefinedRequests).toEqual([]);
});

for (const path of ['/dashboard', '/settings', '/roles-permissions', '/taxonomy-admin']) {
  test(`${path} remains browser-loadable without undefined requests`, async ({ page }) => {
    const undefinedRequests = [];
    await installApiFixtures(page, undefinedRequests);
    const response = await page.goto(path);
    expect(response && response.status()).toBeLessThan(500);
    await expect(page.locator('body')).not.toBeEmpty();
    expect(undefinedRequests).toEqual([]);
  });
}
