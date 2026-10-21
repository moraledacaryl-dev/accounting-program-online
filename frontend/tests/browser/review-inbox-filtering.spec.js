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
    if (path === '/api/integration-review') {
      const source = url.searchParams.get('source_app') || '';
      requestedSources.push(source);
      data = [{ id: source ? 8 : 7, source_app: source || 'pos',
        source_event_id: source ? 'inventory-movement-8' : 'pos-sale-7',
        amount: 10, financial_effect: 'journal_only', status: 'ready_for_review',
        created_at: '2026-10-21T09:00:00Z',
      }];
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) });
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/review-inbox');
  const hero = page.locator('.review-inbox-hero');
  await expect(hero.getByText('Review each external financial event once.', { exact: false })).toBeVisible();
  const heroBounds = await hero.boundingBox();
  expect(heroBounds).toBeTruthy();
  // Capture computed layout details when this regression fails in CI.
  if (heroBounds.height >= 290) {
    const debugLayout = await hero.evaluate((element) => {
      const c = getComputedStyle(element);
      return {
        height: c.height, minHeight: c.minHeight, minBlockSize: c.minBlockSize,
        display: c.display, flexDirection: c.flexDirection,
        justifyContent: c.justifyContent, alignItems: c.alignItems,
        padding: c.padding, margin: c.margin, aspectRatio: c.aspectRatio,
        children: Array.from(element.children).map((child) => ({
          tag: child.tagName, className: child.className,
          height: child.getBoundingClientRect().height,
          offsetTop: child.getBoundingClientRect().top - element.getBoundingClientRect().top,
          style: (() => {
            const st = getComputedStyle(child);
            return { height: st.height, minHeight: st.minHeight, blockSize: st.blockSize,
              display: st.display, flex: st.flex, padding: st.padding, margin: st.margin,
              overflow: st.overflow, justifyContent: st.justifyContent, alignItems: st.alignItems };
          })(),
          inner: Array.from(child.children).map((el) => ({
            tag: el.tagName, height: el.getBoundingClientRect().height,
            top: el.getBoundingClientRect().top - child.getBoundingClientRect().top,
          })),
        })),
      };
    });
    console.log('REVIEW INBOX MOBILE HEADER DEBUG', JSON.stringify(debugLayout));
  }
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
