const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const read = (relative) => fs.readFileSync(path.join(root, relative), 'utf8');
const requireText = (source, text, label) => {
  if (!source.includes(text)) throw new Error(`Missing ${label}: ${text}`);
};
const forbidText = (source, text, label) => {
  if (source.includes(text)) throw new Error(`Forbidden ${label}: ${text}`);
};

const appFrame = read('components/app-shell/AppFrame.js');
const header = read('components/Header.js');
const validationCss = read('app/pass-5-forms-validation-feedback.css');
const closureCss = read('app/pass-70-final-ux-wcag.css');
const ownership = read('components/ExternalOwnershipBoundary.js');
const envExample = read('.env.production.example');

requireText(appFrame, '<SectionNavigation />', 'single shared location navigation');
requireText(read('components/app-shell/SectionNavigation.js'), 'data-context-section={location.groupId}', 'sidebar-aligned section identity');
forbidText(appFrame, '<HotelOperationsNav />\n            <FinanceOperationsNav />', 'simultaneous nav mounting');
requireText(header, "'/integrations/payroll': ['Payroll Integration'", 'payroll integration metadata');
forbidText(validationCss, 'input:invalid:not(:placeholder-shown)', 'premature invalid selector');
requireText(validationCss, ":user-invalid", 'user-invalid selector');
requireText(closureCss, 'position: relative;', 'payroll normal-flow correction');
requireText(read('app/shell-controls.css'), '.section-navigation > .section-navigation__links', 'owned child navigation styles');
requireText(read('app/shell-controls.css'), 'flex-wrap: wrap', 'visible wrapped mobile navigation');
requireText(closureCss, ':focus-visible', 'keyboard focus visibility');
requireText(ownership, 'ownership-mutation-section', 'compact external mutation handling');
requireText(envExample, 'NEXT_PUBLIC_INVENTORY_APP_URL=https://inventory.hiddenoasis.app', 'inventory handoff URL');
requireText(envExample, 'NEXT_PUBLIC_POS_APP_URL=https://pos.hiddenoasis.app', 'POS handoff URL');

console.log('PASS 70 UX/WCAG SOURCE CONTRACT: PASS');
