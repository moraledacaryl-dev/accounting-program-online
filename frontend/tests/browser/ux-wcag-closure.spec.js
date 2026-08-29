const { test, expect } = require('@playwright/test');

const owner = {
  id: 1,
  username: 'pass70-owner',
  full_name: 'Pass 70 Owner',
  role: 'owner',
  permissions: ['*'],
  is_active: true,
};

async function installShellFixtures(page) {
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    let body = [];
    if (url.pathname === '/api/auth/me') body = owner;
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
}

test('untouched required controls are neutral until user-invalid or aria-invalid', async ({ page }) => {
  await page.goto('/login');

  const colors = await page.evaluate(() => {
    const input = document.createElement('input');
    input.required = true;
    input.setAttribute('aria-label', 'Pass 70 required probe');
    document.body.appendChild(input);

    const neutral = getComputedStyle(input).borderColor;
    const nativeInvalid = input.matches(':invalid');

    input.setAttribute('aria-invalid', 'true');
    const explicitInvalid = getComputedStyle(input).borderColor;
    input.remove();

    return { neutral, nativeInvalid, explicitInvalid };
  });

  expect(colors.nativeInvalid).toBe(true);
  expect(colors.neutral).not.toBe(colors.explicitInvalid);
});

test('payroll detail header and tabs stay in normal flow without negative bottom overlap', async ({ page }) => {
  await page.goto('/login');

  const layout = await page.evaluate(() => {
    const host = document.createElement('div');
    host.className = 'main';
    host.dataset.route = '/payroll-periods/123';
    host.innerHTML = `
      <div class="stack">
        <section class="section" id="payroll-header">
          <h1>Payroll period</h1>
          <div class="tabs" id="payroll-tabs"><button class="tab active">Overview</button></div>
        </section>
        <section class="card-grid" id="payroll-kpis"><div class="stat-card">Gross pay</div></section>
      </div>`;
    document.body.appendChild(host);

    const headerStyle = getComputedStyle(document.getElementById('payroll-header'));
    const tabsStyle = getComputedStyle(document.getElementById('payroll-tabs'));
    const headerRect = document.getElementById('payroll-header').getBoundingClientRect();
    const kpiRect = document.getElementById('payroll-kpis').getBoundingClientRect();

    host.remove();
    return {
      position: headerStyle.position,
      top: headerStyle.top,
      marginBottom: Number.parseFloat(tabsStyle.marginBottom || '0'),
      headerBottom: headerRect.bottom,
      kpiTop: kpiRect.top,
    };
  });

  expect(layout.position).toBe('relative');
  expect(layout.marginBottom).toBeGreaterThanOrEqual(0);
  expect(layout.kpiTop).toBeGreaterThanOrEqual(layout.headerBottom);
});

test('payroll integration gets one context navigation and correct page title', async ({ page }) => {
  await installShellFixtures(page);
  await page.goto('/integrations/payroll');

  await expect(page.locator('.context-nav-stack')).toHaveAttribute('data-context-section', 'people-payroll');
  await expect(page.locator('.context-nav-stack nav')).toHaveCount(1);
  await expect(page.locator('.people-context-nav')).toBeVisible();
  await expect(page.locator('.setup-context-nav')).toHaveCount(0);
  await expect(page.locator('.topbar-title')).toHaveText('Payroll Integration');
});
