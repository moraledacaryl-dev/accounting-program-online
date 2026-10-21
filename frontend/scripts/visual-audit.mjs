import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

const BASE = process.env.VISUAL_AUDIT_BASE_URL || 'http://127.0.0.1:3000';
const API = process.env.NEXT_PUBLIC_API_BASE || 'http://127.0.0.1:8000/api';
const OUT = path.resolve('visual-audit');
await fs.rm(OUT, { recursive: true, force: true });
await fs.mkdir(OUT, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  deviceScaleFactor: 1,
  reducedMotion: 'reduce',
});
const page = await context.newPage();

const consoleErrors = [];
const expectedUnauthenticatedChecks = [];
page.on('response', (response) => {
  if (response.status() !== 401) return;
  const requestPath = new URL(response.url()).pathname;
  const currentPath = new URL(page.url()).pathname;
  if (requestPath === '/api/auth/me' && currentPath === '/login') {
    expectedUnauthenticatedChecks.push({ requestPath, currentPath });
  }
});
page.on('console', (msg) => {
  if (msg.type() === 'error') consoleErrors.push({ url: page.url(), text: msg.text() });
});
page.on('pageerror', (err) => consoleErrors.push({ url: page.url(), text: err.message }));

async function api(pathname, options = {}) {
  return page.evaluate(async ({ url, options }) => {
    const token = '';
    const headers = { ...(options.headers || {}) };
    if (token) headers.Authorization = `Bearer ${token}`;
    if (options.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
    const res = await fetch(url, { credentials: 'include', ...options, headers });
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch { data = text; }
    if (!res.ok) throw new Error(`${res.status} ${url}: ${text}`);
    return data;
  }, { url: `${API}${pathname}`, options });
}

await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
await page.screenshot({ path: path.join(OUT, 'login--desktop.png'), fullPage: true });

await page.setViewportSize({ width: 390, height: 844 });
await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
await page.screenshot({ path: path.join(OUT, 'login--mobile.png'), fullPage: true });

await page.setViewportSize({ width: 1440, height: 1000 });
await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
await page.getByLabel('Username').fill('admin');
await page.locator('input[type="password"]').fill('admin123');
await page.getByRole('button', { name: 'Sign in' }).click();
await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
await page.waitForLoadState('networkidle');

const accounts = await api('/financial-accounts');
const firstAccountId = accounts?.[0]?.id;

const routes = [
  ['dashboard', '/dashboard'],
  ['start-of-day', '/start-of-day'],
  ['finance-workspace', '/workspace/finance'],
  ['cashflow-overview', '/cashflow'],
  ['cashflow-accounts', '/cashflow/accounts'],
  ['cashflow-ledger', '/cashflow/ledger'],
  ...(firstAccountId ? [['cashflow-account-history', `/cashflow/${firstAccountId}`]] : []),
  ['cashflow-money-in', '/cashflow/money-in'],
  ['cashflow-money-out', '/cashflow/money-out'],
  ['cashflow-transfers', '/cashflow/transfers'],
  ['cashflow-daily-cash', '/cashflow/daily-cash'],
  ['cashflow-receivables', '/cashflow/receivables'],
  ['cashflow-payables', '/cashflow/payables'],
  ['cashflow-reconciliation', '/cashflow/reconciliation'],
  ['cashflow-templates', '/cashflow/templates'],
  ['journals', '/journals'],
  ['reports', '/reports'],
  ['assets', '/assets'],
  ['bir', '/bir'],
  ['bookings', '/bookings'],
  ['booking-calendar', '/bookings/calendar'],
  ['inventory', '/inventory-items'],
  ['payroll', '/payroll'],
];

const manifest = [
  { name: 'login', route: '/login', viewport: '1440x1000', file: 'login--desktop.png', status: 'ok', title: 'Hidden Oasis Accounting' },
  { name: 'login', route: '/login', viewport: '390x844', file: 'login--mobile.png', status: 'ok', title: 'Hidden Oasis Accounting' },
];
for (const [name, route] of routes) {
  const started = Date.now();
  let status = 'ok';
  let error = '';
  try {
    await page.goto(`${BASE}${route}`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(350);
  } catch (err) {
    status = 'error';
    error = String(err?.message || err);
  }
  const file = `${name}--desktop.png`;
  await page.screenshot({ path: path.join(OUT, file), fullPage: true });
  manifest.push({ name, route, viewport: '1440x1000', file, status, error, duration_ms: Date.now() - started, title: await page.title() });
}


async function captureState(name, route, buttonName) {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(BASE + route, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(300);
  if (buttonName) await page.getByRole('button', { name: buttonName, exact: true }).first().click();
  await page.waitForTimeout(200);
  const file = name + '--desktop.png';
  await page.screenshot({ path: path.join(OUT, file) });
  manifest.push({ name, route, viewport: '1440x1000', file, status: 'ok', state: true, title: await page.title() });
}

await captureState('cashflow-overview-money-in-drawer', '/cashflow?tab=overview', 'Money In');
await captureState('cashflow-overview-money-out-drawer', '/cashflow?tab=overview', 'Money Out');
await captureState('cashflow-overview-transfer-drawer', '/cashflow?tab=overview', 'Transfer');
await captureState('cashflow-transfers-new-transfer-drawer', '/cashflow?tab=transfers', 'New Transfer');


await page.setViewportSize({ width: 1440, height: 1000 });
await page.goto(BASE + '/cashflow?tab=ledger', { waitUntil: 'networkidle', timeout: 30000 });
await page.locator('input[aria-label="Search ledger"]').fill('visual audit long reference sample');
await page.getByLabel('Flow').selectOption('in');
await page.getByLabel('Status').selectOption('posted');
await page.screenshot({ path: path.join(OUT, 'cashflow-ledger-filters-populated--desktop.png'), fullPage: true });
manifest.push({ name: 'cashflow-ledger-filters-populated', route: '/cashflow?tab=ledger', viewport: '1440x1000', file: 'cashflow-ledger-filters-populated--desktop.png', status: 'ok', state: true, title: await page.title() });

await page.goto(BASE + '/cashflow?tab=settings', { waitUntil: 'networkidle', timeout: 30000 });
await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
await page.waitForTimeout(150);
await page.screenshot({ path: path.join(OUT, 'cashflow-settings-bottom--desktop.png') });
manifest.push({ name: 'cashflow-settings-bottom', route: '/cashflow?tab=settings', viewport: '1440x1000', file: 'cashflow-settings-bottom--desktop.png', status: 'ok', state: true, title: await page.title() });

await page.setViewportSize({ width: 390, height: 844 });
for (const [name, route] of [
  ['dashboard', '/dashboard'],
  ['cashflow-overview', '/cashflow'],
  ['cashflow-accounts', '/cashflow/accounts'],
  ['cashflow-ledger', '/cashflow/ledger'],
  ...(firstAccountId ? [['cashflow-account-history', `/cashflow/${firstAccountId}`]] : []),
  ['reports', '/reports'],
]) {
  let status = 'ok';
  let error = '';
  try {
    await page.goto(`${BASE}${route}`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(350);
  } catch (err) {
    status = 'error';
    error = String(err?.message || err);
  }
  const file = `${name}--mobile.png`;
  await page.screenshot({ path: path.join(OUT, file), fullPage: true });
  manifest.push({ name, route, viewport: '390x844', file, status, error, title: await page.title() });
}

// Report tabs need their own mobile screenshots, not just the overview.
await page.goto(BASE + '/reports', { waitUntil: 'networkidle', timeout: 30000 });
for (const [view, label] of [
  ['statements', 'Financial Statements'],
  ['finance', 'AR, AP & Settlements'],
  ['payroll', 'Payroll & BIR'],
]) {
  await page.getByRole('button', { name: label, exact: true }).click();
  await page.waitForTimeout(150);
  const file = `reports-${view}--mobile.png`;
  await page.screenshot({ path: path.join(OUT, file), fullPage: true });
  manifest.push({ name: `reports-${view}`, route: '/reports', viewport: '390x844', file, status: 'ok', state: true, title: await page.title() });
}

// Also inspect the restricted owner/admin journal exception view at mobile size.
// This is a UI snapshot only; no export and no mutation are attempted.
await page.getByRole('button', { name: 'Journal Review', exact: true }).click();
await page.waitForTimeout(350);
await page.screenshot({ path: path.join(OUT, 'reports-journal-review--mobile.png'), fullPage: true });
manifest.push({ name: 'reports-journal-review', route: '/reports', viewport: '390x844', file: 'reports-journal-review--mobile.png', status: 'ok', state: true, title: await page.title() });

// Fixture-only evidence form screenshot. Synthetic data stays inside the visual test;
// no live transaction details or review submissions are captured in CI artifacts.
const mockJournalRoute = '**/api/reports/journal-linkage-review**';
const mockJournalHistoryRoute = (url) => url.pathname.endsWith('/api/reports/journal-linkage-review/909/history');
await page.route(mockJournalHistoryRoute, async (route) => {
  await route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ transaction_id: 909, items: [] }),
  });
});
await page.route(mockJournalRoute, async (route) => {
  const url = new URL(route.request().url());
  const response = url.pathname.endsWith('/history') ? { transaction_id: 909, items: [] } : {
    count: 1, page: 1, page_size: 25, total_pages: 1,
    source_counts: [{ source: 'visual-fixture', count: 1 }],
    items: [{
      id: 909, transaction_date: '2025-06-20',
      external_source: 'visual-fixture', external_id: 'synthetic-909',
      reference_no: 'TEST-RECEIPT', financial_account_id: 1,
      amount: 1234.56, review_status: 'unverified', latest_review: null,
    }],
  };
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(response) });
});
await page.reload({ waitUntil: 'networkidle' });
await page.getByRole('button', { name: 'Journal Review', exact: true }).click();
const historyResponsePromise = page.waitForResponse(
  (response) => new URL(response.url()).pathname.endsWith('/909/history') && response.status() === 200,
  { timeout: 10000 },
);
await page.getByRole('button', { name: 'Record evidence' }).click();
await historyResponsePromise;
await page.getByLabel('Review rationale (at least 10 characters)').fill('Reviewing synthetic example: inspect receipt and folio first.');
await page.evaluate(() => document.activeElement?.blur());
const evidenceFilename = 'reports-journal-evidence-fixture--mobile.png';
await page.screenshot({ path: path.join(OUT, evidenceFilename), fullPage: true });
manifest.push({ name: 'reports-journal-evidence-fixture', route: '/reports', viewport: '390x844', file: evidenceFilename, status: 'ok', state: true, title: await page.title() });
await page.unroute(mockJournalRoute);
await page.unroute(mockJournalHistoryRoute);

// Chromium emits a generic console error for expected 401 /auth/me probes on
// the public login screen. Match those known responses 1:1, and fail the audit
// on every other error instead of quietly passing.
let expectedRemaining = expectedUnauthenticatedChecks.length;
const unexpectedConsoleErrors = consoleErrors.filter((error) => {
  if (expectedRemaining > 0 && new URL(error.url).pathname === '/login'
    && /^Failed to load resource:.*401 \(Unauthorized\)$/.test(error.text)) {
    expectedRemaining -= 1;
    return false;
  }
  return true;
});

await fs.writeFile(path.join(OUT, 'manifest.json'), JSON.stringify({
  generated_at: new Date().toISOString(),
  base_url: BASE,
  account_count: accounts?.length || 0,
  screenshots: manifest,
  console_errors: unexpectedConsoleErrors,
  expected_unauthenticated_checks: expectedUnauthenticatedChecks.length,
  raw_browser_error_count: consoleErrors.length,
}, null, 2));

await browser.close();

const failed = manifest.filter((item) => item.status !== 'ok');
console.log(`Captured ${manifest.length} screenshots to ${OUT}`);
console.log(`Expected unauthenticated login checks: ${expectedUnauthenticatedChecks.length}; unexpected browser errors: ${unexpectedConsoleErrors.length}`);
if (unexpectedConsoleErrors.length) {
  console.error(`Unexpected browser errors on: ${[...new Set(unexpectedConsoleErrors.map((row) => new URL(row.url).pathname))].join(', ')}`);
  process.exitCode = 1;
}
if (failed.length) {
  console.error(`${failed.length} route captures reported navigation errors`);
  process.exitCode = 1;
}
