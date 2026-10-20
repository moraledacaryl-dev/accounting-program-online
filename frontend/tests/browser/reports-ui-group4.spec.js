const { test, expect } = require('@playwright/test');

const owner = {
  id: 1, username: 'reports-ui-audit', full_name: 'Reports Owner',
  role: 'owner', permissions: ['*'], is_active: true,
};

async function mockReports(page) {
  await page.route('**/api/**', async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    let body = [];
    if (pathname === '/api/auth/me') body = owner;
    if (pathname === '/api/reports/management') body = {
      close_readiness: {
        status: 'blocked', score: 65, can_close: false,
        summary: 'Unreconciled accounts need review.', checks: [
          { key: 'unreconciled_cashflow_accounts', label: 'Unreconciled cash and bank accounts',
            value: 12, passed: false, severity: 'critical', action: 'Reconcile cash accounts' },
        ],
      },
      kpis: {
        income_total: 12345.67, expense_total: 5432.1, net_income: 6913.57,
        sales_net_total: 5000, inventory_value: 6540, ar_outstanding: 250,
        ap_outstanding: 120,
      },
      module_breakdown: [],
      exceptions: { unreconciled_cashflow_accounts: 12 },
    };
    if (pathname === '/api/reports/financial-statements') body = {
      profit_and_loss: { revenue: [{ account_code: '4000', account_name: 'Sales', family: 'revenue', balance: 12345.67 }], expenses: [], totals: { revenue: 12345.67, net_income: 6913.57 } },
      balance_sheet: { assets: [], liabilities: [], equity: [] },
      trial_balance: { debit_total: 0, credit_total: 0, rows: [] },
      cash_flow: { operating_activities: [], investing_activities: [], financing_activities: [], unclassified_activities: [], totals: { cash_in: 0, cash_out: 0, net_cash_flow: 0 } },
    };
    if (pathname === '/api/reports/ar-ap-aging') body = {
      receivables: { items: [], total_outstanding: 0, bucket_totals: {} },
      payables: { items: [], total_outstanding: 0, bucket_totals: {} },
    };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
}

test('financial report KPIs are readable and report sections remain accessible on a phone', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockReports(page);
  await page.goto('/reports');
  await expect(page.getByRole('heading', { name: 'Reports & Reconciliation' })).toBeVisible();
  const kpi = page.locator('.report-kpi');
  await expect(kpi).toHaveCount(7);
  await expect(kpi.filter({ hasText: 'Income' })).toContainText('₱12,345.67');

  const sizes = await page.evaluate(() => ({
    contentWidth: document.documentElement.scrollWidth,
    viewportWidth: document.documentElement.clientWidth,
    kpiColumns: getComputedStyle(document.querySelector('.report-kpi-grid')).gridTemplateColumns.split(' ').length,
    labelPx: Number.parseFloat(getComputedStyle(document.querySelector('.main[data-route="/reports"] > div > .section:first-child > .form-grid label')).fontSize),
  }));
  expect(sizes.contentWidth).toBeLessThanOrEqual(sizes.viewportWidth + 1);
  expect(sizes.kpiColumns).toBe(2);
  expect(sizes.labelPx).toBeGreaterThanOrEqual(12);

  await page.getByRole('button', { name: 'Financial Statements', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Profit & Loss' })).toBeVisible();
  await expect(page.locator('table[aria-label*="financial statement"]').first()).toBeVisible();
  await page.getByRole('button', { name: 'AR, AP & Settlements', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Add Settlement Evidence' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save Settlement Evidence' })).toBeDisabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBe(true);
});

test('reports show keyboard focus and announce successful refresh', async ({ page }) => {
  await mockReports(page);
  await page.goto('/reports');
  const refresh = page.getByRole('button', { name: 'Refresh', exact: true });
  await refresh.focus();
  const outline = await refresh.evaluate((node) => getComputedStyle(node).outlineStyle);
  expect(outline).not.toBe('none');
  await refresh.click();
  await expect(page.getByRole('status')).toContainText('Reports refreshed');
});
