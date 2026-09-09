const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { default: AxeBuilder } = require('@axe-core/playwright');

async function fixture(page, permissions = ['*']) {
  await page.route('**/api/**', route => {
    const url = new URL(route.request().url());
    let body = [];
    if (url.pathname === '/api/auth/me') body = { id: 1, username: 'navigation-review', full_name: 'Navigation Review', role: 'owner', permissions };
    if (url.pathname === '/api/payroll-periods/1') body = { id: 1, name: 'Retained period', status: 'posted', lines: [] };
    if (url.pathname === '/api/guests/1/history') body = { guest: { id: 1, name: 'Fixture Guest' }, bookings: [], stay_history: [], payment_history: [], folio_history: [] };
    if (url.pathname === '/api/room-folios/1') body = { id: 1, lines: [] };
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
}

// Explicit route ownership, including aliases and detail pages. Keep every route
// in this inventory so a new page cannot silently lose its sidebar location.
const routeGroups = {
  overview: ['/dashboard', '/start-of-day', '/review-inbox', '/approvals', '/'],
  money: ['/cashflow', '/cashflow/ledger', '/cashflow/settings', '/cashflow/money-in', '/cashflow/money-out', '/cashflow/transfers', '/cashflow/daily-cash', '/cashflow/reconciliation', '/cashflow/accounts', '/cashflow/templates', '/cashflow/1', '/treasury'],
  sales: ['/cashflow/receivables', '/bookings', '/bookings/calendar', '/bookings/1', '/guests', '/guests/1', '/room-folios', '/room-folios/1', '/channel-payouts', '/events'],
  purchases: ['/cashflow/payables', '/suppliers', '/purchase-requests', '/purchase-orders', '/receiving'],
  accounting: ['/journals', '/chart-of-accounts', '/account-mapping', '/bir', '/assets', '/reports', '/attachments'],
  integrations: ['/integrations/beds24', '/integrations/payroll', '/restaurant-ops', '/inventory-items', '/inventory-reconciliation', '/stock-movements', '/menu-items', '/menu-categories', '/recipes', '/staff-meals', '/setup-imports', '/employees', '/attendance', '/payroll-periods', '/payroll-periods/1', '/payroll'],
  administration: ['/room-types', '/rooms', '/room-setup', '/rate-plans', '/room-package-rules', '/booking-channels', '/channels', '/users', '/roles-permissions', '/master-data', '/taxonomy-admin', '/system-settings', '/staff-guide'],
};
for (const [group, routes] of Object.entries(routeGroups)) for (const route of routes) {
  test(`navigation ownership ${route}`, async ({ page }) => {
    await fixture(page);
    await page.goto(route);
    await expect(page.locator('.section-navigation')).toHaveAttribute('data-context-section', group);
    await expect(page.locator('.sidebar a[aria-current="page"]')).toHaveCount(1);
    await expect(page.getByRole('navigation', { name: 'Page location' })).toBeVisible();
    await expect(page.locator('.finance-context-nav,.people-context-nav,.operations-context-nav,.hotel-context-nav,.setup-context-nav')).toHaveCount(0);
  });
}

test('inventory includes every static and dynamic page source', () => {
  const root = path.resolve(__dirname, '../../app');
  const sourceRoutes = fs.readdirSync(root, { recursive: true }).filter(p => p.endsWith('page.js')).map(p => '/' + p.replace(/\/page\.js$|^page\.js$/g, '').replace(/\[(id|accountId)\]/g, '1'));
  const reviewed = Object.values(routeGroups).flat();
  for (const route of sourceRoutes) {
    if (['/login', '/workspace/[module]', '/records/[module]'].includes(route)) continue;
    expect(reviewed, `Missing route audit: ${route}`).toContain(route);
  }
});
for (const [module, group] of [['rooms', 'sales'], ['events', 'sales'], ['restaurant', 'integrations'], ['breakfast', 'integrations'], ['cafe', 'integrations'], ['bar', 'integrations'], ['inventory', 'integrations'], ['payroll', 'integrations'], ['finance', 'money'], ['settings', 'administration']]) {
  test(`legacy workspace ${module} resolves to the correct group`, async ({ page }) => {
    await fixture(page); await page.goto(`/records/${module}`);
    await expect(page.locator('.section-navigation')).toHaveAttribute('data-context-section', group);
    await expect(page.locator('.sidebar a[aria-current="page"]')).toHaveCount(1);
  });
}

test('cash view tabs follow sidebar navigation and browser history', async ({ page }) => {
  await fixture(page); await page.goto('/cashflow');
  const views = page.getByRole('group', { name: 'Cash workspace views' });
  for (const [label, heading] of [['Cash Ledger', 'Account Ledger'], ['Transfers', 'Transfers'], ['Daily Close & Reconciliation', 'Daily Close'], ['Cash Settings', 'Money account settings'], ['Cash Overview', 'Account position']]) {
    await views.getByRole('button', { name: label, exact: true }).click();
    await expect(page.locator('.sidebar a[aria-current="page"]')).toHaveText(label);
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible();
    await expect(views.getByRole('button', { name: label, exact: true })).toHaveAttribute('aria-pressed', 'true');
  }
  await page.goBack(); await expect(views.getByRole('button', { name: 'Cash Settings', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.goForward(); await expect(views.getByRole('button', { name: 'Cash Overview', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.goto('/cashflow/transfers'); await expect(page.getByRole('heading', { name: 'Transfers', exact: true })).toBeVisible();
  await expect(page.locator('.workspace-drawer')).toHaveCount(0);
});

test('closing a money action removes stale sidebar selection', async ({ page }) => {
  await fixture(page); await page.goto('/cashflow/money-in');
  await page.locator('.workspace-drawer').getByRole('button', { name: 'Close', exact: true }).click();
  await expect(page.locator('.sidebar a[aria-current="page"]')).toHaveText('Cash Overview');
});

for (const [route, label, names] of [
  ['/reports', 'Report views', ['Overview', 'Financial Statements', 'Rooms, F&B & Inventory', 'AR, AP & Settlements', 'Payroll & BIR']],
  ['/bir', 'Tax and period close views', ['Review', 'Missing Documents', 'Candidate Records', 'Tax Books', 'Period Locks']],
  ['/approvals', 'Approval queues', ['Records', 'Procurement', 'Money Transactions', 'Payroll', 'Journal Entries', 'Reconciliations']],
  ['/integrations/payroll', 'Payroll review status', ['For Review', 'Ready to Post', 'Posted', 'Rejected', 'Errors', 'Already Applied']],
  ['/payroll-periods/1', 'Payroll period views', ['Summary', 'Reports']],
]) test(`every local view switches at ${route}`, async ({ page }) => {
  await fixture(page); await page.goto(route); const views = page.getByRole('group', { name: label, exact: true });
  for (const name of names) {
    const button = views.getByRole('button', { name: new RegExp(`^${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}( \\(\\d+\\))?$`) });
    await button.click(); await expect(button).toHaveAttribute('aria-pressed', 'true');
    await expect(views.locator('[aria-pressed="true"]')).toHaveCount(1);
    await expect(page.locator('.sidebar a[aria-current="page"]')).toHaveCount(1);
  }
});

test('limited roles only receive accessible sidebar and child links', async ({ page }) => {
  await fixture(page, ['users.manage', 'payroll_periods.view']); await page.goto('/users');
  const sidebar = page.getByRole('complementary', { name: 'Accounting navigation' });
  await expect(sidebar.getByRole('link', { name: 'Users', exact: true })).toHaveAttribute('href', '/users');
  await expect(sidebar.getByRole('link', { name: 'Roles & Permissions', exact: true })).toHaveCount(0);
  await sidebar.getByRole('button', { name: 'Operations Integration', exact: true }).click();
  await expect(sidebar.getByRole('link', { name: 'Payroll Integration', exact: true })).toHaveAttribute('href', '/payroll-periods');
  await sidebar.getByRole('link', { name: 'Payroll Integration', exact: true }).click();
  await expect(page.locator('.sidebar a[aria-current="page"]')).toHaveCount(1);
  await expect(page.locator('.section-navigation__links')).toHaveCount(0);
  await expect(page.getByRole('navigation', { name: 'Page location' })).toContainText('Payroll Period History');
});

for (const width of [390, 768, 1440]) test(`navigation geometry and accessibility at ${width}`, async ({ page }) => {
  await fixture(page); await page.setViewportSize({ width, height: 900 }); await page.goto('/reports');
  await page.waitForLoadState('networkidle');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  const title = await page.getByRole('heading', { name: 'Reports & Reconciliation' }).boundingBox();
  const trail = await page.locator('.section-navigation').boundingBox(); expect(title.y).toBeGreaterThanOrEqual(trail.y + trail.height);
  if (width === 1440) {
    const sidebar = page.getByRole('complementary', { name: 'Accounting navigation' });
    const position = await sidebar.getByRole('link', { name: 'Reports', exact: true }).locator('.nav-text').boundingBox(); expect(position.x).toBeLessThanOrEqual(45);
  }
  const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze(); expect(result.violations).toEqual([]);
});


test('retired catalog editing tabs remain hidden on the read-only POS page', async ({ page }) => {
  await fixture(page); await page.goto('/restaurant-ops');
  await expect(page.getByRole('heading', { name: 'POS Cloud owns this operational workflow' })).toBeVisible();
  await expect(page.locator('[aria-label="Retained catalog views"]')).toBeHidden();
});

test('dashboard movement filters expose the current view', async ({ page }) => {
  await fixture(page); await page.goto('/dashboard');
  const views = page.getByRole('group', { name: 'Guest movement' });
  for (const label of ['Arrivals', 'Departures', 'In-house']) {
    const button = views.getByRole('button', { name: new RegExp('^' + label) });
    await button.click(); await expect(button).toHaveAttribute('aria-pressed', 'true');
    await expect(views.locator('[aria-pressed="true"]')).toHaveCount(1);
  }
});

test('sidebar search finds child pages and keeps their location', async ({ page }) => {
  await fixture(page); await page.goto('/dashboard');
  await page.getByRole('textbox', { name: 'Filter navigation' }).fill('Staff Meals');
  await page.getByRole('navigation', { name: 'Matching pages' }).getByRole('link', { name: /Staff Meals/ }).click();
  await expect(page.locator('.sidebar a[aria-current="page"]')).toHaveText('Inventory');
  await expect(page.getByRole('navigation', { name: 'Page location' })).toContainText('Staff Meals');
});


for (const route of ['/room-types', '/inventory-items', '/integrations/payroll']) test(`every child link stays inside the phone viewport at ${route}`, async ({ page }) => {
  await fixture(page); await page.setViewportSize({ width: 390, height: 900 }); await page.goto(route);
  const links = page.locator('.section-navigation__links a'); await expect(links.first()).toBeVisible();
  const geometry = await links.evaluateAll(items => items.map(item => { const r = item.getBoundingClientRect(); return { left: r.left, right: r.right, height: r.height }; }));
  for (const rect of geometry) { expect(rect.left).toBeGreaterThanOrEqual(0); expect(rect.right).toBeLessThanOrEqual(390); expect(rect.height).toBeGreaterThanOrEqual(40); }
});
