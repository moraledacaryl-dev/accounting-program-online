const { test, expect } = require('@playwright/test');

const owner = {
  id: 1,
  username: 'mobile-density-owner',
  full_name: 'Mobile Density Owner',
  role: 'owner',
  permissions: ['*'],
  is_active: true,
};

function taxonomyRows(count = 160) {
  return Array.from({ length: count }, (_, index) => ({
    id: index + 1,
    module_slug: `module-${Math.floor(index / 20) + 1}`,
    module_name: `Module ${Math.floor(index / 20) + 1}`,
    category: `Category ${Math.floor(index / 8) + 1}`,
    bucket: `Bucket ${Math.floor(index / 4) + 1}`,
    item: `Taxonomy item ${index + 1}`,
    is_active: index % 7 !== 0,
  }));
}

function beds24Logs(count = 100) {
  return Array.from({ length: count }, (_, index) => ({
    id: index + 1,
    created_at: `2026-08-26T09:${String(index % 60).padStart(2, '0')}:00Z`,
    source_type: 'beds24',
    event_type: index % 2 ? 'booking_sync' : 'webhook',
    status: index % 9 ? 'success' : 'partial',
    beds24_booking_id: `B${100000 + index}`,
    local_booking_id: index + 1,
    message: `Representative Beds24 synchronization message ${index + 1}`,
  }));
}

function beds24SyncState(count = 100) {
  return Array.from({ length: count }, (_, index) => ({
    beds24_booking_id: `B${100000 + index}`,
    beds24_property_id: '253718',
    beds24_room_id: `R${(index % 12) + 1}`,
    beds24_unit_id: `U${(index % 12) + 1}`,
    beds24_referer: index % 2 ? 'Booking.com' : 'Direct',
    beds24_channel: index % 2 ? 'booking' : 'direct',
    beds24_api_source: 'api-v2',
    local_booking_id: index + 1,
    local_guest_id: index + 1,
    local_room_id: (index % 12) + 1,
    local_channel_id: (index % 2) + 1,
    sync_status: index % 9 ? 'synced' : 'partial',
    warning_text: index % 9 ? '' : 'Representative mapping warning',
  }));
}

function beds24MappingHelpers(count = 60) {
  return {
    rooms: Array.from({ length: count }, (_, index) => ({
      id: index + 1,
      room_no: `${index + 1}`,
      name: `Room ${index + 1}`,
    })),
    channels: Array.from({ length: count }, (_, index) => ({
      id: index + 1,
      code: `channel-${index + 1}`,
      name: `Channel ${index + 1}`,
    })),
  };
}

async function installMobileFixtures(page) {
  await page.setViewportSize({ width: 390, height: 844 });

  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    let body = [];

    if (url.pathname === '/api/auth/me') {
      body = owner;
    } else if (url.pathname === '/api/integrations/beds24/settings') {
      body = { settings: {} };
    } else if (url.pathname === '/api/integrations/beds24/logs') {
      body = beds24Logs();
    } else if (url.pathname === '/api/integrations/beds24/sync-state') {
      body = beds24SyncState();
    } else if (url.pathname === '/api/integrations/beds24/mapping-helpers') {
      body = beds24MappingHelpers();
    } else if (url.pathname.includes('taxonomy')) {
      body = taxonomyRows();
    } else if (url.pathname.includes('system-settings')) {
      body = {};
    } else if (url.pathname.includes('dashboard')) {
      body = {};
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    });
  });
}

async function pageMetrics(page) {
  return page.evaluate(() => ({
    height: document.documentElement.scrollHeight,
    width: document.documentElement.scrollWidth,
    viewport: document.documentElement.clientWidth,
  }));
}

test('taxonomy admin bounds a large classification tree on mobile', async ({ page }) => {
  await installMobileFixtures(page);
  await page.goto('/taxonomy-admin');
  await expect(page.getByRole('heading', { name: 'Taxonomy Administration' })).toBeVisible();
  await expect(page.getByText('160 nodes')).toBeVisible();

  const tableViewport = page.locator('.main[data-route="/taxonomy-admin"] main.stack > .section:last-child > div:last-child');
  await expect(tableViewport).toBeVisible();

  const scroll = await tableViewport.evaluate((node) => ({
    clientHeight: node.clientHeight,
    scrollHeight: node.scrollHeight,
  }));
  expect(scroll.scrollHeight).toBeGreaterThan(scroll.clientHeight);

  const metrics = await pageMetrics(page);
  expect(metrics.width).toBeLessThanOrEqual(metrics.viewport + 1);
  expect(metrics.height).toBeLessThan(5000);
});

test('staff guide keeps all workflows accessible without an extreme document', async ({ page }) => {
  await installMobileFixtures(page);
  await page.goto('/staff-guide');
  await expect(page.getByRole('heading', { name: 'Staff Process Guide' })).toBeVisible();

  const grids = page.locator('.main[data-route="/staff-guide"] .guide-grid');
  expect(await grids.count()).toBeGreaterThanOrEqual(5);
  const first = grids.first();
  const scroll = await first.evaluate((node) => ({
    clientHeight: node.clientHeight,
    scrollHeight: node.scrollHeight,
  }));
  expect(scroll.scrollHeight).toBeGreaterThanOrEqual(scroll.clientHeight);

  const metrics = await pageMetrics(page);
  expect(metrics.width).toBeLessThanOrEqual(metrics.viewport + 1);
  expect(metrics.height).toBeLessThan(5200);
});

test('Beds24 stays bounded with production-scale debug data on mobile', async ({ page }) => {
  await installMobileFixtures(page);
  const response = await page.goto('/integrations/beds24');
  expect(response && response.status()).toBeLessThan(500);
  await expect(page.getByRole('heading', { name: 'Beds24 Integration' })).toBeVisible();
  await expect(page.getByText('Representative Beds24 synchronization message 1', { exact: true })).toBeVisible();

  const metrics = await pageMetrics(page);
  expect(metrics.width).toBeLessThanOrEqual(metrics.viewport + 1);
  expect(metrics.height).toBeLessThan(7200);

  const tableWraps = page.locator('.main[data-route="/integrations/beds24"] .table-wrap');
  expect(await tableWraps.count()).toBeGreaterThanOrEqual(4);
  const bounded = await tableWraps.evaluateAll((nodes) => nodes.some((node) => node.scrollHeight > node.clientHeight));
  expect(bounded).toBeTruthy();
});

for (const scenario of [
  { path: '/restaurant-ops', maxHeight: 6000 },
  { path: '/assets', maxHeight: 5200 },
  { path: '/bookings', maxHeight: 4200 },
  { path: '/roles-permissions', maxHeight: 3800 },
]) {
  test(`${scenario.path} stays within the mobile density and overflow contract`, async ({ page }) => {
    await installMobileFixtures(page);
    const response = await page.goto(scenario.path);
    expect(response && response.status()).toBeLessThan(500);
    await expect(page.locator('body')).not.toBeEmpty();

    const metrics = await pageMetrics(page);
    expect(metrics.width).toBeLessThanOrEqual(metrics.viewport + 1);
    expect(metrics.height).toBeLessThan(scenario.maxHeight);
  });
}
