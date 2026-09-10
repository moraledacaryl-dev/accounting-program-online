import { chromium, request } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const BASE_URL = (process.env.AUDIT_BASE_URL || 'https://hiddenoasis.app').replace(/\/$/, '');
const OUT = path.resolve(process.env.AUDIT_OUTPUT_DIR || 'audit-artifacts/screenshots');
const USERS = JSON.parse(process.env.AUDIT_USERS_JSON || '{}');
const VIEWPORTS = { desktop: { width: 1440, height: 1000 }, tablet: { width: 768, height: 1024 }, mobile: { width: 390, height: 844 } };
const STATES = (process.env.AUDIT_STATES || 'live').split(',').map(v => v.trim()).filter(Boolean);
const STATIC_SKIP = new Set(['/login']);
const SERVICE_ROLE = role => /(?:^|_)(?:integration|service)(?:_|$)/.test(role);
const slug = value => value.replace(/^\//, '').replace(/[^a-zA-Z0-9._-]+/g, '-') || 'root';

const DYNAMIC_ROUTE_EXPANSIONS = {
  '/records/[module]': ['rooms', 'events', 'restaurant', 'breakfast', 'cafe', 'bar', 'inventory', 'payroll', 'finance', 'settings'].map(module => `/records/${module}`),
  '/workspace/[module]': ['rooms', 'events', 'restaurant', 'breakfast', 'cafe', 'bar', 'inventory', 'payroll', 'finance', 'settings'].map(module => `/workspace/${module}`),
};

const LOCAL_VIEW_STATES = {
  '/reports': { group: 'Report views', labels: ['Overview', 'Financial Statements', 'Rooms, F&B & Inventory', 'AR, AP & Settlements', 'Payroll & BIR'] },
  '/bir': { group: 'Tax and period close views', labels: ['Review', 'Missing Documents', 'Candidate Records', 'Tax Books', 'Period Locks'] },
  '/approvals': { group: 'Approval queues', labels: ['Records', 'Procurement', 'Money Transactions', 'Payroll', 'Journal Entries', 'Reconciliations'] },
  '/integrations/payroll': { group: 'Payroll review status', labels: ['For Review', 'Ready to Post', 'Posted', 'Rejected', 'Errors', 'Already Applied'] },
  '/payroll-periods/1': { group: 'Payroll period views', labels: ['Summary', 'Reports'] },
  '/dashboard': { group: 'Guest movement', labels: ['Arrivals', 'Departures', 'In-house'] },
  '/cashflow': { group: 'Cash workspace views', labels: ['Cash Overview', 'Cash Ledger', 'Transfers', 'Daily Close & Reconciliation', 'Cash Settings'] },
};

function discoverRoutes() {
  const root = path.resolve('app');
  const files = fs.readdirSync(root, { recursive: true }).filter(p => p.endsWith('page.js'));
  const routes = [];
  for (const file of files) {
    let route = '/' + file.replace(/\\/g, '/').replace(/\/page\.js$/, '').replace(/^page\.js$/, '');
    route = route || '/';
    if (STATIC_SKIP.has(route)) continue;
    if (DYNAMIC_ROUTE_EXPANSIONS[route]) { routes.push(...DYNAMIC_ROUTE_EXPANSIONS[route]); continue; }
    route = route.replace(/\[(id|accountId)\]/g, '1');
    if (!route.includes('[')) routes.push(route);
  }
  return [...new Set(routes)].sort();
}

async function login(api, username, password) {
  const response = await api.post(`${BASE_URL}/api/auth/login`, { form: { username, password } });
  if (!response.ok()) throw new Error(`Login failed for ${username}: HTTP ${response.status()}`);
  return api.storageState();
}

async function discoverRoleMatrix(ownerState) {
  const api = await request.newContext({ baseURL: BASE_URL, storageState: ownerState });
  const response = await api.get('/api/roles-permissions/roles?active_only=true');
  if (!response.ok()) throw new Error(`Cannot enumerate active roles: HTTP ${response.status()}`);
  const roles = await response.json(); await api.dispose(); return roles;
}

async function saveCapture(page, resultBase, suffix = 'default') {
  const file = path.join(OUT, slug(resultBase.role), resultBase.viewport, slug(resultBase.state), `${slug(resultBase.route)}--${slug(suffix)}.png`);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  await page.screenshot({ path: file, fullPage: true });
  return path.relative(OUT, file);
}

async function captureLocalViews(page, resultBase, results) {
  const config = LOCAL_VIEW_STATES[resultBase.route];
  if (!config) return;
  const group = page.getByRole('group', { name: config.group, exact: true });
  if (!(await group.count())) return;
  for (const label of config.labels) {
    const button = group.getByRole('button', { name: new RegExp(`^${label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}( \\(\\d+\\))?$`) }).first();
    if (!(await button.count())) continue;
    try {
      await button.click({ timeout: 5_000 });
      await page.waitForTimeout(250);
      const screenshot = await saveCapture(page, resultBase, `view-${label}`);
      results.push({ ...resultBase, uiState: `view:${label}`, status: 'ok', screenshot });
    } catch (e) {
      results.push({ ...resultBase, uiState: `view:${label}`, status: 'state-capture-error', error: String(e) });
    }
  }
}

async function captureRole(browser, roleName, credentials, routes, states) {
  const api = await request.newContext({ baseURL: BASE_URL });
  const storageState = await login(api, credentials.username, credentials.password); await api.dispose();
  const results = [];
  for (const [viewportName, viewport] of Object.entries(VIEWPORTS)) for (const state of states) {
    const context = await browser.newContext({ baseURL: BASE_URL, storageState, viewport, reducedMotion: 'reduce' });
    for (const route of routes) {
      const page = await context.newPage(); const consoleErrors = []; const failedRequests = [];
      page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
      page.on('requestfailed', req => failedRequests.push({ url: req.url(), failure: req.failure()?.errorText || 'failed' }));
      if (state === 'api-error') await page.route('**/api/**', async r => r.request().url().includes('/api/auth/me') ? r.continue() : r.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Screenshot audit simulated API outage' }) }));
      const started = Date.now(); let status = 'ok'; let error = null; let screenshot = null;
      try {
        const response = await page.goto(route, { waitUntil: 'domcontentloaded', timeout: 30_000 });
        await page.waitForTimeout(750);
        const base = { role: roleName, viewport: viewportName, state, route, durationMs: Date.now() - started, consoleErrors, failedRequests };
        screenshot = await saveCapture(page, base);
        if (response && response.status() >= 400) status = `http-${response.status()}`;
        results.push({ ...base, uiState: 'default', status, error, screenshot });
        await captureLocalViews(page, base, results);
      } catch (e) {
        status = 'capture-error'; error = String(e);
        results.push({ role: roleName, viewport: viewportName, state, route, uiState: 'default', status, error, screenshot, durationMs: Date.now() - started, consoleErrors, failedRequests });
      }
      await page.close();
    }
    await context.close();
  }
  return results;
}

fs.mkdirSync(OUT, { recursive: true });
const routes = discoverRoutes();
if (!Object.keys(USERS).length) throw new Error('AUDIT_USERS_JSON is required. Provide one real audit account per active human role.');
const ownerEntry = USERS.owner || USERS.admin;
if (!ownerEntry) throw new Error('AUDIT_USERS_JSON must include owner or admin so active roles can be enumerated.');
const bootstrapApi = await request.newContext({ baseURL: BASE_URL });
const ownerState = await login(bootstrapApi, ownerEntry.username, ownerEntry.password); await bootstrapApi.dispose();
const activeRoles = await discoverRoleMatrix(ownerState);
if (!activeRoles.every(role => role && typeof role.code === 'string' && role.code.trim())) throw new Error('Active role API returned a role without a canonical code.');
const allRoleNames = [...new Set(activeRoles.map(role => role.code.trim()))];
const serviceRoles = allRoleNames.filter(SERVICE_ROLE);
const roleNames = allRoleNames.filter(role => !SERVICE_ROLE(role));
const missing = roleNames.filter(role => !USERS[role]);
if (missing.length) throw new Error(`Missing audit credentials for active human roles: ${missing.join(', ')}`);

const browser = await chromium.launch({ headless: true }); const captures = [];
for (const role of roleNames) captures.push(...await captureRole(browser, role, USERS[role], routes, STATES));
await browser.close();
const baseScreenshots = roleNames.length * routes.length * Object.keys(VIEWPORTS).length * STATES.length;
const manifest = { generatedAt: new Date().toISOString(), baseUrl: BASE_URL, roles: roleNames, serviceRoles, activeRoleDefinitions: activeRoles, routes, dynamicRouteExpansions: DYNAMIC_ROUTE_EXPANSIONS, localViewStates: LOCAL_VIEW_STATES, viewports: VIEWPORTS, states: STATES, expectedBaseScreenshots: baseScreenshots, actualCaptureRecords: captures.length, captures };
fs.writeFileSync(path.join(OUT, 'manifest.json'), JSON.stringify(manifest, null, 2));
fs.writeFileSync(path.join(OUT, 'README.txt'), ['Hidden Oasis Accounting comprehensive screenshot audit', `Generated: ${manifest.generatedAt}`, `Human roles: ${roleNames.join(', ')}`, `Service roles (endpoint-only; no human UI): ${serviceRoles.join(', ') || 'none'}`, `Pages/routes: ${routes.length}`, `Viewports: ${Object.keys(VIEWPORTS).join(', ')}`, `Environment states: ${STATES.join(', ')}`, `Base screenshots: ${baseScreenshots}`, `Capture records including local UI substates: ${captures.length}`, '', 'manifest.json records every capture, local UI state, console error, failed request, route, role, environment state, viewport, active role definition, and dynamic route expansion.'].join('\n'));
console.log(JSON.stringify({ humanRoles: roleNames.length, serviceRoles: serviceRoles.length, routes: routes.length, states: STATES.length, baseScreenshots, captureRecords: captures.length }, null, 2));
