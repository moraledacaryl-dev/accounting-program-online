import { chromium, request } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const BASE_URL = (process.env.AUDIT_BASE_URL || 'https://hiddenoasis.app').replace(/\/$/, '');
const OUT = path.resolve(process.env.AUDIT_OUTPUT_DIR || 'audit-artifacts/screenshots');
const USERS = JSON.parse(process.env.AUDIT_USERS_JSON || '{}');
const VIEWPORTS = {
  desktop: { width: 1440, height: 1000 },
  tablet: { width: 768, height: 1024 },
  mobile: { width: 390, height: 844 },
};
const STATES = (process.env.AUDIT_STATES || 'live').split(',').map(v => v.trim()).filter(Boolean);
const STATIC_SKIP = new Set(['/login']);

function slug(value) {
  return value.replace(/^\//, '').replace(/[^a-zA-Z0-9._-]+/g, '-') || 'root';
}

function discoverRoutes() {
  const root = path.resolve('app');
  const files = fs.readdirSync(root, { recursive: true }).filter(p => p.endsWith('page.js'));
  return [...new Set(files.map(p => {
    let route = '/' + p.replace(/\\/g, '/').replace(/\/page\.js$/, '').replace(/^page\.js$/, '');
    route = route.replace(/\[(id|accountId)\]/g, '1');
    return route || '/';
  }).filter(route => !STATIC_SKIP.has(route) && !route.includes('[')))].sort();
}

async function login(api, username, password) {
  const response = await api.post(`${BASE_URL}/api/auth/login`, { form: { username, password } });
  if (!response.ok()) throw new Error(`Login failed for ${username}: HTTP ${response.status()}`);
  return api.storageState();
}

async function discoverRoleMatrix(ownerState) {
  const api = await request.newContext({ baseURL: BASE_URL, storageState: ownerState });
  const rolesResponse = await api.get('/api/roles-permissions/roles?active_only=true');
  if (!rolesResponse.ok()) throw new Error(`Cannot enumerate active roles: HTTP ${rolesResponse.status()}`);
  const roles = await rolesResponse.json();
  await api.dispose();
  return roles;
}

async function endpointManifest(ownerState) {
  const api = await request.newContext({ baseURL: BASE_URL, storageState: ownerState });
  let spec = null;
  for (const url of ['/openapi.json', '/api/openapi.json']) {
    const response = await api.get(url);
    if (response.ok()) { spec = await response.json(); break; }
  }
  await api.dispose();
  if (!spec) return { available: false, reason: 'OpenAPI is disabled in production; generate static manifest in workflow.' };
  const endpoints = [];
  for (const [route, methods] of Object.entries(spec.paths || {})) {
    for (const [method, meta] of Object.entries(methods)) {
      if (!['get','post','put','patch','delete','head','options'].includes(method)) continue;
      endpoints.push({ method: method.toUpperCase(), route, operationId: meta.operationId || null, tags: meta.tags || [] });
    }
  }
  return { available: true, count: endpoints.length, endpoints };
}

async function captureRole(browser, roleName, credentials, routes, states) {
  const api = await request.newContext({ baseURL: BASE_URL });
  const storageState = await login(api, credentials.username, credentials.password);
  await api.dispose();
  const results = [];

  for (const [viewportName, viewport] of Object.entries(VIEWPORTS)) {
    for (const state of states) {
      const context = await browser.newContext({ baseURL: BASE_URL, storageState, viewport, reducedMotion: 'reduce' });
      for (const route of routes) {
        const page = await context.newPage();
        const consoleErrors = [];
        const failedRequests = [];
        page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
        page.on('requestfailed', req => failedRequests.push({ url: req.url(), failure: req.failure()?.errorText || 'failed' }));
        if (state === 'api-error') {
          await page.route('**/api/**', async r => {
            if (r.request().url().includes('/api/auth/me')) return r.continue();
            return r.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Screenshot audit simulated API outage' }) });
          });
        }
        const started = Date.now();
        let status = 'ok';
        let error = null;
        try {
          const response = await page.goto(route, { waitUntil: 'domcontentloaded', timeout: 30_000 });
          await page.waitForTimeout(750);
          const file = path.join(OUT, slug(roleName), viewportName, slug(state), `${slug(route)}.png`);
          fs.mkdirSync(path.dirname(file), { recursive: true });
          await page.screenshot({ path: file, fullPage: true });
          if (response && response.status() >= 400) status = `http-${response.status()}`;
        } catch (e) {
          status = 'capture-error'; error = String(e);
        }
        results.push({ role: roleName, viewport: viewportName, state, route, status, error, durationMs: Date.now() - started, consoleErrors, failedRequests });
        await page.close();
      }
      await context.close();
    }
  }
  return results;
}

fs.mkdirSync(OUT, { recursive: true });
const routes = discoverRoutes();
if (!Object.keys(USERS).length) throw new Error('AUDIT_USERS_JSON is required. Provide one real audit account per active role.');
const ownerEntry = USERS.owner || USERS.admin;
if (!ownerEntry) throw new Error('AUDIT_USERS_JSON must include owner or admin so active roles can be enumerated.');

const bootstrapApi = await request.newContext({ baseURL: BASE_URL });
const ownerState = await login(bootstrapApi, ownerEntry.username, ownerEntry.password);
await bootstrapApi.dispose();
const activeRoles = await discoverRoleMatrix(ownerState);
const roleNames = [...new Set(activeRoles.map(r => r.slug || r.key || r.name).filter(Boolean))];
const missing = roleNames.filter(role => !USERS[role]);
if (missing.length) throw new Error(`Missing audit credentials for active roles: ${missing.join(', ')}`);

const browser = await chromium.launch({ headless: true });
const captures = [];
for (const role of roleNames) captures.push(...await captureRole(browser, role, USERS[role], routes, STATES));
await browser.close();

const manifest = {
  generatedAt: new Date().toISOString(),
  baseUrl: BASE_URL,
  roles: roleNames,
  routes,
  viewports: VIEWPORTS,
  states: STATES,
  expectedScreenshots: roleNames.length * routes.length * Object.keys(VIEWPORTS).length * STATES.length,
  captures,
  endpoints: await endpointManifest(ownerState),
};
fs.writeFileSync(path.join(OUT, 'manifest.json'), JSON.stringify(manifest, null, 2));
fs.writeFileSync(path.join(OUT, 'README.txt'), [
  'Hidden Oasis Accounting comprehensive screenshot audit',
  `Generated: ${manifest.generatedAt}`,
  `Roles: ${roleNames.join(', ')}`,
  `Pages: ${routes.length}`,
  `Viewports: ${Object.keys(VIEWPORTS).join(', ')}`,
  `States: ${STATES.join(', ')}`,
  `Expected screenshots: ${manifest.expectedScreenshots}`,
  '',
  'manifest.json records every capture, console error, failed request, route, role, state, and viewport.',
].join('\n'));
console.log(JSON.stringify({ roles: roleNames.length, routes: routes.length, states: STATES.length, screenshots: manifest.expectedScreenshots }, null, 2));