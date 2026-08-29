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

test('Inventory & Procurement workflow renders as compact read-only handoff', async ({ page }) => {
  await installOwnershipFixtures(page);
  await page.goto('/inventory-items');

  await expect(page.getByRole('heading', { name: /Inventory & Procurement owns this operational workflow/i })).toBeVisible();
  await expect(page.getByRole('link', { name: /Open Inventory & Procurement/i })).toBeVisible();
  await expect(page.getByRole('link', { name: /Open Inventory & Procurement/i })).toHaveAttribute('href', 'https://inventory.hiddenoasis.app');

  const mutationSections = page.locator('.ownership-mutation-section');
  if (await mutationSections.count()) {
    await expect(mutationSections.first()).toBeHidden();
  }

  const saveButton = page.getByRole('button', { name: /Save item/i });
  if (await saveButton.count()) await expect(saveButton).toBeHidden();

  await expect(page.getByText('Read Only Rice')).toBeVisible();
});

test('POS-owned workflow renders authoritative handoff and hides mutation forms', async ({ page }) => {
  await installOwnershipFixtures(page);
  await page.goto('/menu-items');

  await expect(page.getByRole('heading', { name: /POS Cloud owns this operational workflow/i })).toBeVisible();
  await expect(page.getByRole('link', { name: /Open POS Cloud/i })).toHaveAttribute('href', 'https://pos.hiddenoasis.app');

  const mutationSections = page.locator('.ownership-mutation-section');
  if (await mutationSections.count()) {
    await expect(mutationSections.first()).toBeHidden();
  }

  await expect(page.getByText('Read Only Coffee')).toBeVisible();
});
