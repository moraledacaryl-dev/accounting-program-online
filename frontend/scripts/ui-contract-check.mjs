import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const sourceRoots = ['app', 'components', 'lib'];
const nativeDialogPattern = /\b(?:window\.)?(?:confirm|alert|prompt)\s*\(/g;
const failures = [];

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return walk(full);
    return /\.(?:js|jsx|ts|tsx)$/.test(entry.name) ? [full] : [];
  });
}

for (const sourceRoot of sourceRoots) {
  const dir = path.join(root, sourceRoot);
  if (!fs.existsSync(dir)) continue;
  for (const file of walk(dir)) {
    const source = fs.readFileSync(file, 'utf8');
    if (nativeDialogPattern.test(source)) {
      failures.push(`${path.relative(root, file)} uses a native browser dialog`);
    }
    nativeDialogPattern.lastIndex = 0;
  }
}

const shellContext = fs.readFileSync(path.join(root, 'components/app-shell/AppShellContext.js'), 'utf8');
for (const callback of ['openMobileNav', 'closeMobileNav', 'toggleMobileNav']) {
  if (!new RegExp(`const ${callback} = useCallback`).test(shellContext)) {
    failures.push(`AppShellContext must keep ${callback} stable with useCallback`);
  }
}

const sidebar = fs.readFileSync(path.join(root, 'components/Sidebar.js'), 'utf8');
if (!sidebar.includes('MIN_SEARCH_LENGTH = 2')) failures.push('Sidebar search minimum length contract is missing');
if (!sidebar.includes("searchActive ? 'search-active' : ''")) failures.push('Sidebar search containment class is missing');

const login = fs.readFileSync(path.join(root, 'app/login/page.js'), 'utf8');
if (!login.includes('aria-invalid')) failures.push('Login fields must expose aria-invalid after validation');

const enhancer = fs.readFileSync(path.join(root, 'components/AccessibilityEnhancer.js'), 'utf8');
if (!enhancer.includes('Ledger start date') || !enhancer.includes('Ledger status')) {
  failures.push('Cash & Treasury filter accessibility labels are missing');
}

const colorState = fs.readFileSync(path.join(root, 'app/pass-56-color-state-verification.css'), 'utf8');
const recertification = fs.readFileSync(path.join(root, 'app/pass-57-final-visual-recertification.css'), 'utf8');
const layout = fs.readFileSync(path.join(root, 'app/layout.js'), 'utf8');
const pass56Import = "import './pass-56-color-state-verification.css';";
const pass57Import = "import './pass-57-final-visual-recertification.css';";
if (!layout.includes(pass56Import)) {
  failures.push('Pass 56 color-state verification layer is not loaded');
}
if (!layout.includes(pass57Import) || layout.indexOf(pass57Import) < layout.indexOf(pass56Import)) {
  failures.push('Pass 57 visual recertification layer must load after Pass 56');
}
if (!colorState.includes('--state-selected-ink: #214934')) {
  failures.push('Selected light surfaces must keep a dark readable ink color');
}
if (!colorState.includes('.main .tab.active') || !colorState.includes("[aria-selected='true']")) {
  failures.push('Selected tab state normalization is missing');
}
if (!colorState.includes('--state-disabled-bg') || !colorState.includes('.main button:disabled')) {
  failures.push('Intentional disabled-button state is missing');
}
if (!colorState.includes('.sidebar .nav-group-items a.active') || !colorState.includes('var(--sidebar-active-ink')) {
  failures.push('Sidebar active state must remain a soft surface with dark text');
}
if (!recertification.includes('.main[data-route="/reports"] > div > .section:first-child > .tabs .tab.active')) {
  failures.push('Report-family selected state is not protected from the route-specific cascade');
}
if (!recertification.includes(':where(input, select, textarea):disabled')) {
  failures.push('Disabled form-field state normalization is missing');
}

if (failures.length) {
  console.error('UI contract check failed:\n- ' + failures.join('\n- '));
  process.exit(1);
}

console.log('UI contract check passed.');