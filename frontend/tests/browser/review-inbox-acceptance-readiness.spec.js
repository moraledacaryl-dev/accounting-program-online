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

async function mockReviewApi(page, requests, actor = {}) {
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
      permissions: ['review_inbox.view', 'review_inbox.act', 'integrations.view', 'integrations.manage', 'cashflow.view'],
      ...actor,
    };
    if (path === '/api/integration-review/summary') data = {
      needs_review: 1, by_status: { ready_for_review: 1 },
    };
    if (path === '/api/integration-review/page') data = {
      items: [sourceItem], page: 1, page_size: 25, total: 1, total_pages: 1,
      has_previous: false, has_next: false,
    };
    if (path === '/api/financial-accounts/' && !(
      (actor.permissions || ['review_inbox.act']).includes('review_inbox.act')
      || (actor.permissions || []).includes('cashflow.view')
    )) return route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ detail: 'Missing permissions' }) });
    if (path === '/api/financial-accounts/') data = [
      { id: 10, name: 'Actual GCash Wallet', account_type: 'ewallet', is_active: true, currency: 'PHP' },
      { id: 11, name: 'Inactive cash drawer', account_type: 'cash_drawer', is_active: false, currency: 'PHP' },
      { id: 12, name: 'Expense GL account', account_type: 'expense', is_active: true, currency: 'PHP' },
      { id: 13, name: 'USD bank account', account_type: 'bank', is_active: true, currency: 'USD' },
    ];
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) });
  });
}

test('payroll approver and integration operator have read-only review controls', async ({ page }) => {
  const requests = [];
  await mockReviewApi(page, requests, {
    role: 'payroll_admin', permissions: ['review_inbox.view', 'approvals.act', 'integrations.manage', 'integrations.view'],
  });
  await page.goto('/review-inbox');
  await page.getByRole('button', { name: 'Review', exact: true }).click();
  await expect(page.getByText('Review Inbox approval permission is required', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Accept into accounting' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Reject', exact: true })).toHaveCount(0);
  await expect(page.getByLabel('Accounting posting date (required)')).toHaveCount(0);
  await expect(page.getByLabel('Financial account')).toHaveCount(0);
  expect(requests).toHaveLength(0);
  for (const width of [1440, 1024, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    await expect(page.getByText('Review Inbox approval permission is required', { exact: false })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    const dir = process.env.ACCOUNTING_AUDIT_SCREENSHOT_DIR;
    if (dir) await page.screenshot({ path: `${dir}/read-only-review-${width}.png`, fullPage: true });
  }
});

test('Cashier can open the dedicated read-only Review Inbox without decision controls', async ({ page }) => {
  const requests = [];
  await mockReviewApi(page, requests, {
    role: 'cashier', permissions: ['dashboard.view', 'review_inbox.view', 'cashflow.view'],
  });
  await page.goto('/review-inbox');
  await expect(page.getByRole('heading', { name: 'Review Inbox' })).toBeVisible();
  await expect(page.locator('.metric-card').first().locator('strong')).toHaveText('1');
  await expect(page.getByRole('link', { name: 'Open Review Inbox' })).toBeVisible();
  await page.getByRole('button', { name: 'Review', exact: true }).click();
  await expect(page.getByText('Review Inbox approval permission is required', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Accept into accounting' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Reject', exact: true })).toHaveCount(0);
  expect(requests).toHaveLength(0);
});

test('revoked review permission removes posting controls after a rejected save', async ({ page }) => {
  const requests = [];
  const actor = {
    role: 'accounting_admin',
    permissions: ['review_inbox.view', 'review_inbox.act', 'integrations.view'],
  };
  await mockReviewApi(page, requests, actor);
  await page.route('**/api/integration-review/14/accept', async (route) => {
    actor.permissions = ['review_inbox.view', 'integrations.view'];
    await route.fulfill({ status: 403, contentType: 'application/json',
      body: JSON.stringify({ detail: 'Missing permissions: review_inbox.act' }) });
  });
  await page.goto('/review-inbox');
  await page.getByRole('button', { name: 'Review', exact: true }).click();
  await page.getByLabel('Financial account').selectOption('10');
  await page.getByLabel('Accounting posting date (required)').fill('2026-10-25');
  await page.getByLabel('Verified payment method').fill('gcash');
  await page.getByRole('button', { name: 'Accept into accounting' }).click();
  await page.getByRole('button', { name: 'Review', exact: true }).click();
  await expect(page.getByText('Review Inbox approval permission is required', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Accept into accounting' })).toHaveCount(0);
  expect(requests).toHaveLength(0);
});

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
