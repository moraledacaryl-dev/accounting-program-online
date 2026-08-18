const { test, expect } = require('@playwright/test');

const owner = {
  id: 1,
  username: 'ownership-test-owner',
  full_name: 'Ownership Test Owner',
  role: 'owner',
  permissions: ['*'],
  is_active: true,
};

async function installOwnershipFixtures(page) {
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    let body = [];

    if (url.pathname === '/api/auth/me') {
      body = owner;
    } else if (url.pathname === '/api/stock/items') {
      body = [{ id: 11, name: 'Read Only Rice', category_name: 'Food', subcategory_name: 'Dry Goods', unit: 'kg', reorder_level: 5 }];
    } else if (url.pathname === '/api/master/values') {
      body = [];
    } else if (url.pathname === '/api/menu/items') {
      body = [{ id: 21, name: 'Read Only Coffee', category: 'Beverages', price: 120, is_active: true }];
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
}

test('Inventory & Procurement workflow renders as visibly read-only', async ({ page }) => {
  await installOwnershipFixtures(page);
  await page.goto('/inventory-items');

  await expect(page.getByRole('heading', { name: /Inventory & Procurement owns this operational workflow/i })).toBeVisible();
  await expect(page.getByRole('button', { name: /Save item/i })).toBeDisabled();
  await expect(page.getByRole('button', { name: /^Edit$/i })).toBeDisabled();
  await expect(page.getByRole('button', { name: /^Delete$/i })).toBeDisabled();
  await expect(page.getByLabel('Name')).toBeDisabled();
});

test('POS-owned workflow renders ownership notice', async ({ page }) => {
  await installOwnershipFixtures(page);
  await page.goto('/menu-items');

  await expect(page.getByRole('heading', { name: /POS Cloud owns this operational workflow/i })).toBeVisible();
  const forms = page.locator('.external-ownership-boundary form');
  if (await forms.count()) {
    await expect(forms.first().locator('input, select, textarea, button').first()).toBeDisabled();
  }
});
