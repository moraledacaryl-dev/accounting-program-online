const { test, expect } = require('@playwright/test');

const sourceItem = {
  id: 14, source_app: 'pos', source_event_id: 'synthetic-pos-refund-14',
  source_entity_type: 'refund', source_entity_id: '14',
  financial_effect: 'cash_out', amount: 150, currency: 'PHP',
  proposed_account_id: 11, proposed_links: { payment_method: 'bank_transfer' },
  status: 'ready_for_review', created_at: '2026-10-22T09:00:00Z',
  validation: {
    valid: true, errors: [],
    warnings: ['Select the actual financial account before posting this cash or settlement event.'],
  },
};

async function mockReviewApi(page, requests) {
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (route.request().method() !== 'GET') {
      requests.push({ path, method: route.request().method(), body: route.request().postDataJSON() });
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'accepted' }) });
    }
    let data = {};
    if (path === '/api/auth/me') data = {
      id: 1, username: 'reviewer', full_name: 'Reviewer', is_active: true, role: 'owner',
      permissions: ['integrations.view', 'integrations.manage', 'cashflow.view'],
    };
    if (path === '/api/integration-review/summary') data = {
      needs_review: 1, by_status: { ready_for_review: 1 },
    };
    if (path === '/api/integration-review/page') data = {
      items: [sourceItem], page: 1, page_size: 25, total: 1, total_pages: 1,
      has_previous: false, has_next: false,
    };
    if (path === '/api/financial-accounts/') data = [
      { id: 10, name: 'Actual GCash Wallet', account_type: 'ewallet', is_active: true, currency: 'PHP' },
      { id: 11, name: 'Inactive cash drawer', account_type: 'cash_drawer', is_active: false, currency: 'PHP' },
      { id: 12, name: 'Expense GL account', account_type: 'expense', is_active: true, currency: 'PHP' },
      { id: 13, name: 'USD bank account', account_type: 'bank', is_active: true, currency: 'USD' },
    ];
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) });
  });
}

test('Group 4: cash acceptance requires documented date, eligible account and verified payment method', async ({ page }) => {
  const requests = [];
  await mockReviewApi(page, requests);
  await page.goto('/review-inbox');
  await page.getByRole('button', { name: 'Review', exact: true }).click();

  await expect(page.getByRole('region', { name: 'Intake validation findings' })).toBeVisible();
  await expect(page.getByText('The previously proposed account is unavailable', { exact: false })).toBeVisible();
  await expect(page.getByText('Source suggested: bank_transfer', { exact: false })).toBeVisible();

  const account = page.getByLabel('Financial account');
  await expect(account.locator('option')).toHaveCount(2);
  await expect(account).not.toContainText('Inactive cash drawer');
  await expect(account).not.toContainText('Expense GL account');
  await expect(account).not.toContainText('USD bank account');

  const accept = page.getByRole('button', { name: 'Accept into accounting' });
  await expect(accept).toBeDisabled();
  await account.selectOption('10');
  await expect(accept).toBeDisabled();
  await page.getByLabel('Accounting posting date (required)').fill('2026-10-22');
  await expect(accept).toBeDisabled();
  await page.getByLabel('Verified payment method').fill('gcash');
  await page.getByLabel('Review notes').fill('Synthetic evidence reference for regression test');
  await expect(accept).toBeEnabled();
  expect(requests).toHaveLength(0);

  await test.info().attach('group4-review-desktop', {
    body: await page.screenshot({ fullPage: true }), contentType: 'image/png',
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(accept).toBeVisible();
  await test.info().attach('group4-review-mobile', {
    body: await page.screenshot({ fullPage: true }), contentType: 'image/png',
  });

  await accept.click();
  await expect.poll(() => requests.length).toBe(1);
  expect(requests[0].path).toBe('/api/integration-review/14/accept');
  expect(requests[0].method).toBe('POST');
  expect(requests[0].body).toMatchObject({
    account_id: 10, payment_method: 'gcash', transaction_date: '2026-10-22',
    notes: 'Synthetic evidence reference for regression test',
  });
});

test('Group 4: rejection requires a reviewer-authored reason and never accepts the event', async ({ page }) => {
  const requests = [];
  await mockReviewApi(page, requests);
  await page.goto('/review-inbox');
  await page.getByRole('button', { name: 'Review', exact: true }).click();

  const reject = page.getByRole('button', { name: 'Reject', exact: true });
  await expect(reject).toBeDisabled();
  await page.getByLabel('Rejection reason').fill('   ');
  await expect(reject).toBeDisabled();
  await page.getByLabel('Rejection reason').fill('Source receipt must be rechecked before posting');
  await expect(reject).toBeEnabled();
  expect(requests).toHaveLength(0);

  await reject.click();
  await expect.poll(() => requests.length).toBe(1);
  expect(requests[0].path).toBe('/api/integration-review/14/reject');
  expect(requests[0].body.reason).toBe('Source receipt must be rechecked before posting');
  expect(requests.filter((request) => request.path.endsWith('/accept'))).toHaveLength(0);
});
