const { test, expect } = require('@playwright/test');

async function mockOwnerReports(page, role = 'owner') {
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    let payload = [];
    if (path === '/api/auth/me') payload = {
      id: 101, username: 'review-user', full_name: 'Audit Reviewer',
      role, permissions: ['reports.view'], is_active: true,
    };
    if (path === '/api/reports/journal-linkage-review') {
      const pageNumber = Number(url.searchParams.get('page') || 1);
      const source = url.searchParams.get('source') || '';
      payload = {
        count: source ? 1 : 26,
        page: pageNumber, page_size: 25,
        total_pages: source ? 1 : 2,
        source_counts: [{ source: 'beds24', count: 1 }, { source: 'cashbook', count: 25 }],
        classification: 'unverified_journal_linkage',
        items: [
          {
            id: pageNumber === 1 ? 11 : 36, transaction_date: '2025-06-20',
            financial_account_id: 1, external_source: source || 'cashbook',
            external_id: 'source-001', reference_no: 'REF-001',
            amount: 1234.56, review_status: 'unverified',
          },
        ],
      };
    }
    if (path === '/api/reports/management') payload = { kpis: {}, close_readiness: {} };
    if (path === '/api/reports/financial-statements') payload = {};
    if (path === '/api/reports/ar-ap-aging') payload = { receivables: { items: [] }, payables: { items: [] } };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) });
  });
}

test('owner can review paginated journal linkage evidence without changing balances', async ({ page }) => {
  await mockOwnerReports(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/reports');
  const journalButton = page.getByRole('button', { name: 'Journal Review', exact: true });
  await expect(journalButton).toBeVisible();
  await journalButton.click();
  await expect(page.getByRole('heading', { name: 'Journal Linkage Review' })).toBeVisible();
  const reviewTable = page.getByRole('table', { name: 'Unverified journal linkage records' });
  await expect(reviewTable).toContainText('REF-001');
  await expect(reviewTable).toContainText('1,234.56');
  await expect(page.getByText('Unverified records: 26')).toBeVisible();
  await page.getByRole('button', { name: 'Next', exact: true }).click();
  await expect(reviewTable).toContainText('36');
  await expect(page.getByText('Page 2 of 2')).toBeVisible();
  await page.getByLabel('External Source').selectOption('beds24');
  await expect(page.getByText('Unverified records: 1')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Next', exact: true })).toBeDisabled();
  const widths = await page.evaluate(() => ({
    page: document.documentElement.scrollWidth,
    viewport: document.documentElement.clientWidth,
    table: document.querySelector('.journal-review-table').scrollWidth,
    panel: document.querySelector('.journal-review-table-scroll').clientWidth,
  }));
  expect(widths.page).toBeLessThanOrEqual(widths.viewport + 1);
  expect(widths.table).toBeGreaterThan(widths.panel);
  await expect(page.getByText('No automatic matching or posting is performed.')).toBeVisible();
});

test('non-owner cannot see sensitive journal review tab', async ({ page }) => {
  await mockOwnerReports(page, 'front_desk');
  await page.goto('/reports');
  await expect(page.getByRole('heading', { name: 'Reports & Reconciliation' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Journal Review' })).toHaveCount(0);
});
