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

await fs.writeFile(path.join(OUT, 'manifest.json'), JSON.stringify({
  generated_at: new Date().toISOString(),
  base_url: BASE,
  account_count: accounts?.length || 0,
  screenshots: manifest,
  console_errors: consoleErrors,
}, null, 2));

await browser.close();

const failed = manifest.filter((item) => item.status !== 'ok');
console.log(`Captured ${manifest.length} screenshots to ${OUT}`);
if (consoleErrors.length) console.log(`Observed ${consoleErrors.length} browser console/page errors; see manifest.json`);
if (failed.length) {
  console.error(`${failed.length} route captures reported navigation errors`);
  process.exitCode = 1;
}
