import { chromium, request } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const CONFIGURED_BASE_URL = (process.env.AUDIT_BASE_URL || 'https://accounting.hiddenoasis.app').replace(/\/$/, '');
let BASE_URL = CONFIGURED_BASE_URL;
const OUT = path.resolve(process.env.AUDIT_OUTPUT_DIR || 'audit-artifacts/screenshots');
const USERS = JSON.parse(process.env.AUDIT_USERS_JSON || '{}');
const VIEWPORTS = { desktop: { width: 1440, height: 1000 }, tablet: { width: 768, height: 1024 }, mobile: { width: 390, height: 844 } };
const STATES = (process.env.AUDIT_STATES || 'live').split(',').map(v => v.trim()).filter(Boolean);
const STATIC_SKIP = new Set(['/login']);
const SERVICE_ROLE = role => /(?:^|_)(?:integration|service)(?:_|$)/.test(role);
const slug = value => value.replace(/^\//, '').replace(/[^a-zA-Z0-9._-]+/g, '-') || 'root';
const SETTLE_TIMEOUT_MS = Number(process.env.AUDIT_SETTLE_TIMEOUT_MS || 12_000);
const MIN_SETTLED_BODY_CHARS = Number(process.env.AUDIT_MIN_SETTLED_BODY_CHARS || 80);
const SETTLE_POLL_MS = Number(process.env.AUDIT_SETTLE_POLL_MS || 250);
const REQUIRED_READY_POLLS = 2;
const LOADING_MARKERS = [
  'Checking access',
  'Loading your permitted work areas',
  'Loading today’s accounting overview',
  'Loading today\'s accounting overview',
  'Refreshing queues…',
  'Refreshing queues...',
];

const DYNAMIC_ROUTE_EXPANSIONS = {
  '/records/[module]': ['rooms', 'events', 'restaurant', 'breakfast', 'cafe', 'bar', 'inventory', 'payroll', 'finance', 'settings'].map(module => `/records/${module}`),
  '/workspace/[module]': ['rooms', 'events', 'restaurant', 'breakfast', 'cafe', 'bar', 'inventory', 'payroll', 'finance', 'settings'].map(module => `/workspace/${module}`),
};

const LOCAL_VIEW_STATES = {
  '/reports': { group: 'Report views', labels: ['Overview', 'Financial Statements', 'Rooms, F&B & Inventory', 'AR, AP & Settlements', 'Payroll & BIR'] },
  '/bir': { group: 'Tax and period close views', labels: ['Review', 'Missing Documents', 'Candidate Records', 'Tax Books', 'Period Locks'] },
  '/approvals': { group: 'Approval queues', labels: ['Records', 'Procurement', 'Money Transactions', 'Payroll', 'Journal Entries', 'Reconciliations'] },
  '/integrations/payroll': { group: 'Payroll review status', labels: ['For Review', 'Ready to Post', 'Posted', 'Rejected', 'Errors', 'Already Applied'] },
  '/dashboard': { group: 'Guest movement', labels: ['Arrivals', 'Departures', 'In-house'] },
  '/cashflow': { group: 'Cash workspace views', labels: ['Cash Overview', 'Cash Ledger', 'Transfers', 'Daily Close & Reconciliation', 'Cash Settings'] },
};

async function resolveCanonicalBaseUrl() {
  const api = await request.newContext();
  const response = await api.get(`${CONFIGURED_BASE_URL}/api/healthz`, { failOnStatusCode: false });
  if (!response.ok()) {
    await api.dispose();
    throw new Error(`Cannot resolve canonical Accounting host: health check returned HTTP ${response.status()}`);
  }
  const final = new URL(response.url());
  await api.dispose();
  return `${final.protocol}//${final.host}`;
}

function discoverRoutes() {
  const root = path.resolve('app');
  const files = fs.readdirSync(root, { recursive: true }).filter(p => p.endsWith('page.js'));
  const routes = [];
  for (const file of files) {
    let route = '/' + file.replace(/\\/g, '/').replace(/\/page\.js$/, '').replace(/^page\.js$/, '');
    route = route || '/';
    if (STATIC_SKIP.has(route)) continue;
    if (DYNAMIC_ROUTE_EXPANSIONS[route]) { routes.push(...DYNAMIC_ROUTE_EXPANSIONS[route]); continue; }
    route = route.replace(/\[accountId\]/g, '1');
    if (route.includes('[id]')) continue;
    if (!route.includes('[')) routes.push(route);
  }
  return [...new Set(routes)].sort();
}

async function login(api, username, password) {
  const response = await api.post(`${BASE_URL}/api/auth/login`, { data: { username, password } });
  if (!response.ok()) throw new Error(`Login failed for ${username}: HTTP ${response.status()}`);
  return api.storageState();
}

async function discoverRoleMatrix(ownerState) {
  const api = await request.newContext({ baseURL: BASE_URL, storageState: ownerState });
  const response = await api.get('/api/roles-permissions/roles?active_only=true');
  if (!response.ok()) throw new Error(`Cannot enumerate active roles: HTTP ${response.status()}`);
  const roles = await response.json(); await api.dispose(); return roles;
}

async function discoverRepresentativeRoutes(ownerState, routes) {
  const api = await request.newContext({ baseURL: BASE_URL, storageState: ownerState });
  try {
    const response = await api.get('/api/payroll-periods/?limit=1', { failOnStatusCode: false });
    if (response.ok()) {
      const body = await response.json();
      const rows = Array.isArray(body) ? body : Array.isArray(body?.items) ? body.items : [];
      const id = rows[0]?.id;
      if (id) routes.push(`/payroll-periods/${id}`);
    }
  } finally {
    await api.dispose();
  }
  return [...new Set(routes)].sort();
}

function isBenignAbortedRequest(entry) {
  if (!String(entry.failure || '').includes('ERR_ABORTED')) return false;
  const url = String(entry.url || '');
  return url.includes('_rsc=') || url.includes('/_next/static/chunks/');
}

async function pageReadiness(page) {
  const text = await page.locator('body').innerText().catch(() => '');
  const normalized = text.replace(/\s+/g, ' ').trim();
  const loadingMarkers = LOADING_MARKERS.filter(marker => normalized.includes(marker));
  return {
    loadingMarkers,
    visibleBodyChars: normalized.length,
    sparseBody: normalized.length < MIN_SETTLED_BODY_CHARS,
  };
}

async function waitForSettledPage(page) {
  const started = Date.now();
  let readiness = await pageReadiness(page);
  let readyPolls = 0;
  while (Date.now() - started < SETTLE_TIMEOUT_MS) {
    const ready = readiness.loadingMarkers.length === 0 && !readiness.sparseBody;
    readyPolls = ready ? readyPolls + 1 : 0;
    if (readyPolls >= REQUIRED_READY_POLLS) break;
    await page.waitForTimeout(SETTLE_POLL_MS);
    readiness = await pageReadiness(page);
  }
  const settled = readiness.loadingMarkers.length === 0 && !readiness.sparseBody && readyPolls >= REQUIRED_READY_POLLS;
  return { settled, ...readiness, settleMs: Date.now() - started };
}

async function saveCapture(page, resultBase, suffix = 'default') {
  const file = path.join(OUT, slug(resultBase.role), resultBase.viewport, slug(resultBase.state), `${slug(resultBase.route)}--${slug(suffix)}.png`);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  await page.screenshot({ path: file, fullPage: true });
  return path.relative(OUT, file);
}

async function captureLocalViews(page, resultBase, results) {
  const config = LOCAL_VIEW_STATES[resultBase.route] || (resultBase.route.startsWith('/payroll-periods/') ? { group: 'Payroll period views', labels: ['Summary', 'Reports'] } : null);
  if (!config || resultBase.redirected || !resultBase.settled) return;
  const group = page.getByRole('group', { name: config.group, exact: true });
  if (!(await group.count())) return;
  for (const label of config.labels) {
    const button = group.getByRole('button', { name: new RegExp(`^${label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}( \\(\\d+\\))?$`) }).first();
    if (!(await button.count())) continue;
    try {
      await button.click({ timeout: 5_000 });
      await page.waitForTimeout(SETTLE_POLL_MS);
      const settled = await waitForSettledPage(page);
      const screenshot = await saveCapture(page, resultBase, `view-${label}`);
      results.push({ ...resultBase, ...settled, uiState: `view:${label}`, status: settled.settled ? 'ok' : 'incomplete-loading', screenshot });
    } catch (e) {
      results.push({ ...resultBase, uiState: `view:${label}`, status: 'state-capture-error', error: String(e) });
    }
  }
}

async function captureRole(browser, roleName, credentials, routes, states, progress) {
  const api = await request.newContext({ baseURL: BASE_URL });
  const storageState = await login(api, credentials.username, credentials.password); await api.dispose();
  const results = [];
  for (const [viewportName, viewport] of Object.entries(VIEWPORTS)) for (const state of states) {
    const context = await browser.newContext({ baseURL: BASE_URL, storageState, viewport, reducedMotion: 'reduce' });
    for (const route of routes) {
      progress.completed += 1;
      const prefix = `[${progress.completed}/${progress.total}] ${roleName} ${viewportName} ${state} ${route}`;
      console.log(`${prefix} START`);
      const page = await context.newPage(); const consoleErrors = []; const failedRequestsRaw = [];
      page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
      page.on('requestfailed', req => failedRequestsRaw.push({ url: req.url(), failure: req.failure()?.errorText || 'failed' }));
      if (state === 'api-error') await page.route('**/api/**', async r => r.request().url().includes('/api/auth/me') ? r.continue() : r.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Screenshot audit simulated API outage' }) }));
      const started = Date.now(); let status = 'ok'; let error = null; let screenshot = null;
      try {
        const response = await page.goto(route, { waitUntil: 'domcontentloaded', timeout: 30_000 });
        const settled = await waitForSettledPage(page);
        const finalUrl = new URL(page.url());
        const finalRoute = `${finalUrl.pathname}${finalUrl.search}`;
        const redirected = finalUrl.pathname !== new URL(route, BASE_URL).pathname;
        const failedRequests = failedRequestsRaw.filter(entry => !isBenignAbortedRequest(entry));
        const benignAbortedRequests = failedRequestsRaw.filter(isBenignAbortedRequest);
        const base = { role: roleName, viewport: viewportName, state, route, requestedUrl: new URL(route, BASE_URL).href, finalUrl: page.url(), finalRoute, redirected, ...settled, durationMs: Date.now() - started, consoleErrors, failedRequests, benignAbortedRequests };
        screenshot = await saveCapture(page, base);
        if (response && response.status() >= 400) status = `http-${response.status()}`;
        else if (!settled.settled) status = 'incomplete-loading';
        else if (redirected) status = 'redirected';
        results.push({ ...base, uiState: 'default', status, error, screenshot });
        await captureLocalViews(page, base, results);
        console.log(`${prefix} ${status.toUpperCase()} ${Date.now() - started}ms${redirected ? ` -> ${finalRoute}` : ''}${settled.sparseBody ? ` sparse=${settled.visibleBodyChars}` : ''}`);
      } catch (e) {
        status = 'capture-error'; error = String(e);
        results.push({ role: roleName, viewport: viewportName, state, route, requestedUrl: new URL(route, BASE_URL).href, finalUrl: page.url(), finalRoute: null, redirected: false, settled: false, loadingMarkers: [], visibleBodyChars: 0, sparseBody: true, uiState: 'default', status, error, screenshot, durationMs: Date.now() - started, consoleErrors, failedRequests: failedRequestsRaw.filter(entry => !isBenignAbortedRequest(entry)), benignAbortedRequests: failedRequestsRaw.filter(isBenignAbortedRequest) });
        console.log(`${prefix} CAPTURE-ERROR ${Date.now() - started}ms ${error}`);
      }
      await page.close();
    }
    await context.close();
  }
  return results;
}

fs.mkdirSync(OUT, { recursive: true });
BASE_URL = await resolveCanonicalBaseUrl();
if (BASE_URL !== CONFIGURED_BASE_URL) console.log(`Resolved canonical Accounting host: ${BASE_URL}`);
let routes = discoverRoutes();
if (!Object.keys(USERS).length) throw new Error('AUDIT_USERS_JSON is required. Provide one real audit account per active human role.');
const ownerEntry = USERS.owner || USERS.admin;
if (!ownerEntry) throw new Error('AUDIT_USERS_JSON must include owner or admin so active roles can be enumerated.');
const bootstrapApi = await request.newContext({ baseURL: BASE_URL });
const ownerState = await login(bootstrapApi, ownerEntry.username, ownerEntry.password); await bootstrapApi.dispose();
const activeRoles = await discoverRoleMatrix(ownerState);
routes = await discoverRepresentativeRoutes(ownerState, routes);
if (!activeRoles.every(role => role && typeof role.code === 'string' && role.code.trim())) throw new Error('Active role API returned a role without a canonical code.');
const allRoleNames = [...new Set(activeRoles.map(role => role.code.trim()))];
const serviceRoles = allRoleNames.filter(SERVICE_ROLE);
const roleNames = allRoleNames.filter(role => !SERVICE_ROLE(role));
const missing = roleNames.filter(role => !USERS[role]);
if (missing.length) throw new Error(`Missing audit credentials for active human roles: ${missing.join(', ')}`);

const browser = await chromium.launch({ headless: true }); const captures = [];
const totalBaseCaptures = roleNames.length * routes.length * Object.keys(VIEWPORTS).length * STATES.length;
const progress = { completed: 0, total: totalBaseCaptures };
for (const role of roleNames) captures.push(...await captureRole(browser, role, USERS[role], routes, STATES, progress));
await browser.close();
const manifest = { generatedAt: new Date().toISOString(), configuredBaseUrl: CONFIGURED_BASE_URL, baseUrl: BASE_URL, roles: roleNames, serviceRoles, activeRoleDefinitions: activeRoles, routes, dynamicRouteExpansions: DYNAMIC_ROUTE_EXPANSIONS, localViewStates: LOCAL_VIEW_STATES, viewports: VIEWPORTS, states: STATES, expectedBaseScreenshots: totalBaseCaptures, actualCaptureRecords: captures.length, captures };
fs.writeFileSync(path.join(OUT, 'manifest.json'), JSON.stringify(manifest, null, 2));
fs.writeFileSync(path.join(OUT, 'README.txt'), ['Hidden Oasis Accounting comprehensive screenshot audit', `Generated: ${manifest.generatedAt}`, `Canonical base URL: ${manifest.baseUrl}`, `Human roles: ${roleNames.join(', ')}`, `Service roles (endpoint-only; no human UI): ${serviceRoles.join(', ') || 'none'}`, `Pages/routes: ${routes.length}`, `Viewports: ${Object.keys(VIEWPORTS).join(', ')}`, `Environment states: ${STATES.join(', ')}`, `Base screenshots: ${totalBaseCaptures}`, `Capture records including local UI substates: ${captures.length}`, '', 'manifest.json records requested and final URLs, redirect classification, settled/loading status, visible body size/sparse-render status, console errors, meaningful failed requests, benign aborted Next.js requests, local UI state, role, environment state, viewport, active role definition, and dynamic route expansion.'].join('\n'));
console.log(JSON.stringify({ configuredBaseUrl: CONFIGURED_BASE_URL, baseUrl: BASE_URL, humanRoles: roleNames.length, serviceRoles: serviceRoles.length, routes: routes.length, states: STATES.length, baseScreenshots: totalBaseCaptures, captureRecords: captures.length }, null, 2));
