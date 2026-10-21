const { test, expect } = require('@playwright/test');

async function mockReconciliationCenter(page, { role = 'owner', unavailable = '' } = {}) {
  const requests = [];
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    requests.push(path);
    if (path === unavailable) {
      await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Temporary outage' }) });
      return;
    }
    let data = {};
    if (path === '/api/auth/me') data = {
      id: 99, username: 'reconciler', role, full_name: 'Accounting Reviewer', is_active: true,
      permissions: role === 'owner'
        ? ['reports.view', 'cashflow.view', 'integrations.view', 'dashboard.view']
        : ['reports.view', 'cashflow.view', 'dashboard.view'],
    };
    if (path === '/api/reports/journal-linkage-review') data = {
      count: 166, review_summary: { missing_journal_links: 166, never_reviewed: 155, evidence_recorded: 11 },
      items: [], page: 1, page_size: 1,
    };
    if (path === '/api/cashflow/summary') data = { summary_cards: { unreconciled_accounts: 3 } };
    if (path === '/api/integration-review/summary') data = { needs_review: 7, by_status: { ready_for_review: 7 } };
    if (path === '/api/reports/management') data = { close_readiness: {
      status: 'blocked', checks: [
        { key: 'unreconciled_cashflow_accounts', label: 'Unreconciled cash/bank accounts', severity: 'critical', passed: false, value: 3, action: 'Finish cash checks.' },
        { key: 'draft_records', label: 'Draft records', severity: 'critical', passed: true, value: 0, action: 'OK' },
        { key: 'ar_over_30_days', label: 'Overdue receivables', severity: 'warning', passed: false, value: 2, action: 'Collect.' },
      ],
    } };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) });
  });
  return requests;
}

test('reconciliation center displays grounded workstreams and direct links on desktop and mobile', async ({ page }) => {
  await mockReconciliationCenter(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/reconciliation-center');
  await expect(page.getByRole('heading', { name: 'Reconciliation Control Center' })).toBeVisible();
  await expect(page.getByText('4 / 4')).toBeVisible();
  const journal = page.getByRole('article').filter({ hasText: 'Investigate historical journal links' });
  await expect(journal.getByText('155')).toBeVisible();
  await expect(journal.getByText('166 still lack a direct journal link')).toBeVisible();
  await expect(page.getByRole('article').filter({ hasText: 'Complete cash and account reconciliation' }).getByText('3')).toBeVisible();
  await expect(page.getByRole('article').filter({ hasText: 'Review connected financial events' }).getByText('7')).toBeVisible();
  await expect(page.getByRole('article').filter({ hasText: 'Clear period-close blockers' }).getByText('1')).toBeVisible();
  await expect(page.getByText('Saved review evidence does not automatically resolve a linkage.', { exact: false })).toBeVisible();
  await expect(journal.getByRole('link', { name: 'Open Journal Review' })).toHaveAttribute('href', '/reports?view=journal-review');
  await expect(page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).resolves.toBe(true);
});

test('reconciliation center does not leak owner-only evidence to authorized non-owner report viewers', async ({ page }) => {
  const requests = await mockReconciliationCenter(page, { role: 'accounting_admin' });
  await page.goto('/reconciliation-center');
  await expect(page.getByRole('heading', { name: 'Reconciliation Control Center' })).toBeVisible();
  await expect(page.getByText('1', { exact: true }).first()).toBeVisible();
  await expect(page.getByRole('article').filter({ hasText: 'Investigate historical journal links' }).getByText('—')).toBeVisible();
  expect(requests).not.toContain('/api/reports/journal-linkage-review');
  expect(requests).not.toContain('/api/integration-review/summary');
});

test('failed control source is never presented as zero exceptions and refresh recovers', async ({ page }) => {
  const broken = '/api/cashflow/summary';
  let fail = true;
  await page.route('**/api/cashflow/summary*', async (route) => {
    if (fail) return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Unavailable' }) });
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ summary_cards: { unreconciled_accounts: 2 } }) });
  });
  await mockReconciliationCenter(page);
  await page.goto('/reconciliation-center');
  const cash = page.getByRole('article').filter({ hasText: 'Complete cash and account reconciliation' });
  await expect(cash.getByText('Unavailable')).toBeVisible();
  await expect(cash.getByText('—')).toBeVisible();
  fail = false;
  await page.getByRole('button', { name: 'Refresh checks' }).click();
  await expect(cash.getByText('2')).toBeVisible();
});
