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
    if (path === '/api/integration-review/page') {
      const failed = url.searchParams.get('status') === 'validation_failed';
      body = [{
        id: failed ? 20 : 10, source_app: failed ? 'inventory' : 'pos',
        source_event_id: failed ? 'failed-inventory-event' : 'pending-pos-event',
        financial_effect: 'reference_only', amount: 0, currency: 'PHP',
        status: failed ? 'validation_failed' : 'ready_for_review',
        created_at: '2026-10-20T08:00:00Z',
      }];
    }
    if (path === '/api/integration-review/page') body = {
      items: body, page: 1, page_size: 25, total: body.length, total_pages: 1,
      has_previous: false, has_next: false,
    };
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
  expect(calls.filter((c) => c.path === '/api/integration-review/page').at(-1).status).toBe('validation_failed');
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
    if (path === '/api/integration-review/page') data = [{
      id: 9, source_app: 'staff', source_event_id: 'failed-staff-event',
      amount: 50, financial_effect: 'cash_in', status: url.searchParams.get('status') || 'ready_for_review',
      created_at: '2026-10-21T09:00:00Z',
    }];
    if (path === '/api/integration-review/page') data = {
      items: data, page: 1, page_size: 25, total: data.length, total_pages: 1,
      has_previous: false, has_next: false,
    };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) });
  });
  await page.goto('/review-inbox');
  await page.getByRole('button', { name: 'Review failed validations' }).click();
  await expect(page.getByLabel('Status')).toHaveValue('validation_failed');
  await expect(page.getByText('failed-staff-event')).toBeVisible();
  await page.getByRole('button', { name: 'Refresh inbox' }).click();
  await expect(page.getByText('failed-staff-event')).toBeVisible();
  expect(calls.filter((c) => c.path === '/api/integration-review/page').at(-1).status).toBe('validation_failed');
});


test('per-source intake counts filter review events without claiming source connection health', async ({ page }) => {
  const requestedSources = [];
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    let data = [];
    if (path === '/api/auth/me') data = {
      id: 1, username: 'reviewer', full_name: 'Reviewer', role: 'owner',
      permissions: ['integrations.view', 'cashflow.view'], is_active: true,
    };
    if (path === '/api/integration-review/summary') data = {
      needs_review: 2, by_status: { ready_for_review: 1, validation_failed: 1 },
      by_source: {
        pos: { total: 7, needs_review: 1, accepted: 6, validation_failed: 0 },
        inventory: { total: 2, needs_review: 1, accepted: 0, validation_failed: 1 },
      },
      source_coverage_note: 'Received Accounting review events only; not a live connectivity or delivery guarantee.',
    };
    if (path === '/api/integration-review/page') {
      const source = url.searchParams.get('source_app') || '';
      requestedSources.push(source);
      data = [{ id: source ? 8 : 7, source_app: source || 'pos',
        source_event_id: source ? 'inventory-movement-8' : 'pos-sale-7',
        amount: 10, financial_effect: 'journal_only', status: 'ready_for_review',
        created_at: '2026-10-21T09:00:00Z',
      }];
    }
    if (path === '/api/integration-review/page') data = {
      items: data, page: 1, page_size: 25, total: data.length, total_pages: 1,
      has_previous: false, has_next: false,
    };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) });
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/review-inbox');
  const hero = page.locator('.review-inbox-hero');
  await expect(hero.getByText('Review each external financial event once.', { exact: false })).toBeVisible();
  const heroBounds = await hero.boundingBox();
  expect(heroBounds).toBeTruthy();
  expect(heroBounds.height).toBeLessThan(290);
  const heroCopyColor = await hero.locator('.muted').evaluate((el) => getComputedStyle(el).color);
  expect(heroCopyColor).toBe('rgb(76, 98, 86)');
  const coverage = page.getByRole('region', { name: 'Received integration events by source' });
  await expect(coverage).toBeVisible();
  await expect(coverage.getByText('not a live connectivity or delivery guarantee.', { exact: false })).toBeVisible();
  await coverage.getByRole('button', { name: /inventory/i }).click();
  await expect(page.getByLabel('Source application')).toHaveValue('inventory');
  await expect(page.getByText('inventory-movement-8')).toBeVisible();
  expect(requestedSources.at(-1)).toBe('inventory');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBe(true);
});


test('Review Inbox walks all server pages and resets pagination after filtering', async ({ page }) => {
  const visited = [];
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    let data = {};
    if (path === '/api/auth/me') data = {
      id: 5, username: 'reviewer', role: 'owner', is_active: true,
      permissions: ['integrations.view', 'cashflow.view'],
    };
    if (path === '/api/financial-accounts/') data = [];
    if (path === '/api/integration-review/summary') data = { needs_review: 51, by_status: { ready_for_review: 51 } };
    if (path === '/api/integration-review/page') {
      const n = Number(url.searchParams.get('page') || 1);
      const filtered = url.searchParams.get('source_app') === 'inventory';
      visited.push({ n, filtered });
      const total = filtered ? 1 : 51;
      const start = (n - 1) * 25;
      const size = Math.max(0, Math.min(25, total - start));
      data = {
        page: n, page_size: 25, total, total_pages: Math.ceil(total / 25),
        has_previous: n > 1, has_next: n * 25 < total,
        items: Array.from({ length: size }, (_, i) => ({
          id: start + i + 1, source_app: filtered ? 'inventory' : 'pos',
          source_event_id: 'event-' + String(start + i + 1),
          financial_effect: 'reference_only', status: 'ready_for_review', amount: 0,
          currency: 'PHP', created_at: '2026-10-21T09:00:00Z',
        })),
      };
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) });
  });
  await page.goto('/review-inbox');
  await expect(page.getByText('Showing 1–25 of 51 matching events')).toBeVisible();
  await page.getByRole('navigation', { name: 'Review Inbox pages' }).getByRole('button', { name: 'Next' }).click();
  await expect(page.getByText('Showing 26–50 of 51 matching events')).toBeVisible();
  await expect(page.getByText('event-26', { exact: true })).toBeVisible();
  await page.getByRole('navigation', { name: 'Review Inbox pages' }).getByRole('button', { name: 'Next' }).click();
  await expect(page.getByText('Showing 51–51 of 51 matching events')).toBeVisible();
  await expect(page.getByText('event-51', { exact: true })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Review Inbox pages' }).getByRole('button', { name: 'Next' })).toBeDisabled();
  await page.getByLabel('Source application').selectOption('inventory');
  await page.getByRole('button', { name: 'Apply filters' }).click();
  await expect(page.getByText('Showing 1–1 of 1 matching events')).toBeVisible();
  await expect(page.getByText('Page 1 of 1')).toBeVisible();
  expect(visited.map((v) => v.n)).toEqual([1, 2, 3, 1]);
});
