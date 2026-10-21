const { test, expect } = require('@playwright/test');

async function mockOwnerReports(page, role = 'owner') {
  let latestReview = null;
  let postedPayload = null;
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    let payload = [];
    if (path === '/api/auth/me') payload = {
      id: 101, username: 'review-user', full_name: 'Audit Reviewer',
      role, permissions: ['reports.view'], is_active: true,
    };
    if (path === '/api/reports/journal-linkage-review/11/history') {
      payload = { transaction_id: 11, items: latestReview ? [latestReview] : [] };
    }
    if (path === '/api/reports/journal-linkage-review/11/decisions' && route.request().method() === 'POST') {
      postedPayload = route.request().postDataJSON();
      latestReview = {
        id: 1, transaction_id: 11, reviewed_at: '2026-10-21T09:00:00Z',
        reviewed_by: 'review-user', decision: postedPayload.decision,
        supporting_reference: postedPayload.supporting_reference, notes: postedPayload.notes,
        suggested_journal_entry_id: postedPayload.suggested_journal_entry_id,
        accounting_posting_created: false, journal_link_changed: false,
      };
      payload = latestReview;
    }
    if (path === '/api/reports/journal-linkage-review') {
      const pageNumber = Number(url.searchParams.get('page') || 1);
      const source = url.searchParams.get('source') || '';
      const queue = url.searchParams.get('queue') || 'all';
      const scopeCount = source ? 1 : 26;
      const reviewedCount = latestReview && (!source || source === 'cashbook') ? 1 : 0;
      const count = queue === 'unreviewed' ? scopeCount - reviewedCount
        : queue === 'reviewed' ? reviewedCount : scopeCount;
      payload = {
        count,
        queue,
        scope_count: scopeCount,
        review_summary: {
          missing_journal_links: scopeCount,
          never_reviewed: scopeCount - reviewedCount,
          evidence_recorded: reviewedCount,
          classifications: {
            needs_evidence: 0,
            cashflow_only_documented: reviewedCount,
            journal_candidate_identified: 0,
            requires_accounting_review: 0,
          },
          journal_links_resolved_by_review: 0,
          is_financially_reconciled: false,
        },
        page: pageNumber, page_size: 25,
        total_pages: Math.ceil(count / 25),
        source_counts: [{ source: 'beds24', count: 1 }, { source: 'cashbook', count: 25 }],
        classification: 'unverified_journal_linkage',
        items: count > 0 ? [
          {
            id: (queue === 'reviewed' || pageNumber === 1) ? 11 : 36, transaction_date: '2025-06-20',
            financial_account_id: 1, external_source: source || 'cashbook',
            external_id: 'source-001', reference_no: 'REF-001',
            amount: 1234.56, review_status: latestReview ? 'evidence_recorded' : 'unverified',
            latest_review: latestReview,
          },
        ] : [],
      };
    }
    if (path === '/api/reports/management') payload = { kpis: {}, close_readiness: {} };
    if (path === '/api/reports/financial-statements') payload = {};
    if (path === '/api/reports/ar-ap-aging') payload = { receivables: { items: [] }, payables: { items: [] } };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) });
  });
  return { submitted: () => postedPayload };
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
  await expect(page.getByText('Missing journal links', { exact: true })).toBeVisible();
  await expect(page.getByText('Missing journal links', { exact: true }).locator('..')).toContainText('26');
  await expect(page.getByRole('progressbar', { name: 'Evidence review coverage' })).toHaveAttribute('aria-valuenow', '0');
  await expect(page.getByLabel('Review Queue')).toHaveValue('unreviewed');
  await page.getByRole('button', { name: 'Next', exact: true }).click();
  await expect(reviewTable).toContainText('36');
  await expect(page.getByText('Page 2 of 2')).toBeVisible();
  await page.getByLabel('External Source').selectOption('beds24');
  await expect(page.getByText('Evidence recorded', { exact: true })).toBeVisible();
  await expect(page.getByRole('progressbar', { name: 'Evidence review coverage' })).toHaveAttribute('aria-valuemax', '1');
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

test('owner can record evidence without creating or linking a journal', async ({ page }) => {
  const session = await mockOwnerReports(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/reports');
  await page.getByRole('button', { name: 'Journal Review', exact: true }).click();
  await page.getByLabel('Review Queue').selectOption('all');
  await expect(page.getByRole('button', { name: 'Record evidence' })).toBeVisible();
  await page.getByRole('button', { name: 'Record evidence' }).click();
  await expect(page.getByRole('heading', { name: 'Evidence for transaction #11' })).toBeVisible();
  const submit = page.getByRole('button', { name: 'Save review evidence' });
  await expect(submit).toBeDisabled();
  await page.getByLabel('Review classification').selectOption('cashflow_only_documented');
  await page.getByLabel('Evidence reference').fill('Receipt book page 21');
  await page.getByLabel('Review rationale (at least 10 characters)').fill(
    'Physical receipt and 2025 cashbook line inspected; still requires Accounting approval.',
  );
  await expect(submit).toBeEnabled();
  await submit.click();
  await expect(page.getByRole('status')).toContainText('Evidence recorded. No accounting journal or cash balance was modified.');
  await expect(page.getByText('cashflow only documented', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Review again' })).toBeVisible();
  await expect(page.getByRole('progressbar', { name: 'Evidence review coverage' })).toHaveAttribute('aria-valuenow', '1');
  await expect(page.getByText('Evidence recorded is not the same as a journal link verified, reconciled or posted.')).toBeVisible();
  const payload = session.submitted();
  expect(payload.decision).toBe('cashflow_only_documented');
  expect(payload.supporting_reference).toBe('Receipt book page 21');
  expect(payload.suggested_journal_entry_id).toBe(null);
  expect(payload.idempotency_key.length).toBeGreaterThanOrEqual(16);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBe(true);
});

test('review queue filters the worklist without changing the missing journal total', async ({ page }) => {
  await mockOwnerReports(page);
  await page.goto('/reports');
  await page.getByRole('button', { name: 'Journal Review', exact: true }).click();
  const queue = page.getByLabel('Review Queue');
  await expect(queue).toHaveValue('unreviewed');
  await expect(page.getByText('Showing 26 records in this queue')).toBeVisible();
  await queue.selectOption('reviewed');
  await expect(page.getByText('Showing 0 records in this queue')).toBeVisible();
  await expect(page.getByText('No matching records in this queue.', { exact: false })).toBeVisible();
  await expect(page.getByText('Missing journal links', { exact: true }).locator('..')).toContainText('26');
  await queue.selectOption('all');
  await expect(page.getByText('Showing 26 records in this queue')).toBeVisible();
  await expect(page.getByRole('table', { name: 'Unverified journal linkage records' })).toContainText('REF-001');
});
