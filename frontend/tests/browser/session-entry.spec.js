const { test, expect } = require('@playwright/test');

const owner = { id: 1, username: 'session-review', full_name: 'Session Review', role: 'owner', permissions: ['*'] };
const json = (route, status, body) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

for (const path of ['/', '/dashboard', '/staff-guide', '/journals']) {
  test(`inactive session opens sign-in from ${path}`, async ({ page }) => {
    let releaseSession;
    const waiting = new Promise(resolve => { releaseSession = resolve; });
    await page.route('**/api/**', async route => {
      if (new URL(route.request().url()).pathname === '/api/auth/me') await waiting;
      return json(route, 401, { detail: 'Could not validate credentials' });
    });
    await page.goto(path);
    try {
      await expect(page.getByRole('heading', { name: 'Checking access' })).toBeVisible();
      await expect(page.locator('.app-shell')).toHaveCount(0);
      await expect(page.getByRole('link', { name: 'Staff Guide', exact: true })).toHaveCount(0);
    } finally {
      releaseSession();
    }
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible();
    await expect(page.locator('.app-shell')).toHaveCount(0);
  });
}

test('session expiry during use removes the shell and opens sign-in', async ({ page }) => {
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/auth/me') return json(route, 200, owner);
    if (path.startsWith('/api/search/')) return json(route, 401, { detail: 'Session expired' });
    return json(route, 200, []);
  });
  await page.goto('/staff-guide');
  await expect(page.locator('.app-shell')).toBeVisible();
  await page.getByRole('textbox', { name: 'Search guests, bookings, folios, and records' }).fill('test');
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.locator('.app-shell')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible();
});

test('sign-in works after an expired session without logging out first', async ({ page }) => {
  let signedIn = false;
  let logoutRequests = 0;
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/auth/logout') logoutRequests += 1;
    if (path === '/api/auth/login') {
      const credentials = route.request().postDataJSON();
      if (credentials.password === 'wrong-test-password') return json(route, 401, { detail: 'Invalid username or password.' });
      signedIn = true;
      return json(route, 200, { ok: true });
    }
    if (path === '/api/auth/me') return json(route, signedIn ? 200 : 401, signedIn ? owner : { detail: 'Session expired' });
    return json(route, 200, []);
  });
  const loginReady = page.waitForResponse(response => new URL(response.url()).pathname === '/api/auth/me' && new URL(page.url()).pathname === '/login');
  await page.goto('/');
  await expect(page).toHaveURL(/\/login$/);
  await loginReady;
  await page.getByRole('textbox', { name: 'Username', exact: true }).fill(owner.username);
  await page.locator('input[autocomplete="current-password"]').fill('wrong-test-password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'Invalid username or password.' })).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
  await page.locator('input[autocomplete="current-password"]').fill('browser-fixture-password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.locator('.app-shell')).toBeVisible();
  await expect(page.getByRole('button', { name: /Session Review Owner/ })).toBeVisible();
  expect(logoutRequests).toBe(0);
});

test('a forbidden request does not log out a valid session', async ({ page }) => {
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/auth/me') return json(route, 200, owner);
    if (path.startsWith('/api/search/')) return json(route, 403, { detail: 'Access denied' });
    return json(route, 200, []);
  });
  await page.goto('/staff-guide');
  await page.getByRole('textbox', { name: 'Search guests, bookings, folios, and records' }).fill('test');
  await expect(page.getByText('Access denied', { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/\/staff-guide$/);
  await expect(page.locator('.app-shell')).toBeVisible();
});
