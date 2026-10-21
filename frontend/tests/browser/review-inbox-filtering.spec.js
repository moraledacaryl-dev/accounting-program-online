const { test, expect } = require('@playwright/test');

test('Review Inbox applies draft filters explicitly without leaving stale rows', async ({ page }) => {
  const calls = [];
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    calls.push({ path, method: route.request().method(), status: url.searchParams.get('status') });
    let body = [];
    if (path === '/api/auth/me') body = {
      id: 1, username: 'integration-reviewer', full_name: 'Accounting Reviewer', role: 'owner',
      is_active: true, permissions: ['integrations.view', 'approvals.view', 'cashflow.view'],
    };
    if (path === '/api/integration-review/summary') body = {
      by_status: { ready_for_review: 1, validation_failed: 1 }, needs_review: 2,
    };
    if (path === '/api/integration-review') {
      const failed = url.searchParams.get('status') === 'validation_failed';
      body = [{
        id: failed ? 20 : 10, source_app: failed ? 'inventory' : 'pos',
        source_event_id: failed ? 'failed-inventory-event' : 'pending-pos-event',
        financial_effect: 'reference_only', amount: 0, currency: 'PHP',
        status: failed ? 'validation_failed' : 'ready_for_review',
        created_at: '2026-10-20T08:00:00Z',
      }];
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.goto('/review-inbox');
  await expect(page.getByText('pending-pos-event')).toBeVisible();
  await page.getByLabel('Status').selectOption('validation_failed');
  await expect(page.getByText('Filters changed. Select Apply filters to update the queue.')).toBeVisible();
  await expect(page.getByText('pending-pos-event')).toBeVisible();
  await page.getByRole('button', { name: 'Apply filters' }).click();
  await expect(page.getByText('failed-inventory-event')).toBeVisible();
  await expect(page.getByText('pending-pos-event')).toHaveCount(0);
  await expect(page.getByText('Filters changed. Select Apply filters to update the queue.')).toHaveCount(0);
  expect(calls.filter((c) => c.path === '/api/integration-review').at(-1).status).toBe('validation_failed');
  expect(calls.filter((c) => c.method !== 'GET')).toHaveLength(0);
});

test('Review Inbox failed-validation shortcut remains read-only and refresh keeps applied filters', async ({ page }) => {
  const calls = [];
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    calls.push({ path, status: url.searchParams.get('status') });
    let data = [];
    if (path === '/api/auth/me') data = {
      id: 1, username: 'accountant', full_name: 'Accounting Reviewer', role: 'owner',
      is_active: true, permissions: ['integrations.view', 'cashflow.view'],
    };
    if (path === '/api/integration-review/summary') data = { needs_review: 3, by_status: { validation_failed: 3 } };
    if (path === '/api/integration-review') data = [{
      id: 9, source_app: 'staff', source_event_id: 'failed-staff-event',
      amount: 50, financial_effect: 'cash_in', status: url.searchParams.get('status') || 'ready_for_review',
      created_at: '2026-10-21T09:00:00Z',
    }];
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) });
  });
  await page.goto('/review-inbox');
  await page.getByRole('button', { name: 'Review failed validations' }).click();
  await expect(page.getByLabel('Status')).toHaveValue('validation_failed');
  await expect(page.getByText('failed-staff-event')).toBeVisible();
  await page.getByRole('button', { name: 'Refresh inbox' }).click();
  await expect(page.getByText('failed-staff-event')).toBeVisible();
  expect(calls.filter((c) => c.path === '/api/integration-review').at(-1).status).toBe('validation_failed');
});
