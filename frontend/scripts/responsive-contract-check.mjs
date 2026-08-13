import fs from 'node:fs';

const shell = fs.readFileSync(new URL('../app/app-shell.css', import.meta.url), 'utf8');
const closure = fs.readFileSync(new URL('../app/pass-54-responsive-edge-case-closure.css', import.meta.url), 'utf8');
const layout = fs.readFileSync(new URL('../app/layout.js', import.meta.url), 'utf8');

const failures = [];
const requireMatch = (condition, message) => {
  if (!condition) failures.push(message);
};

requireMatch(shell.includes('@media (max-width: 760px)'), 'App shell mobile breakpoint contract is missing.');
requireMatch(closure.includes('@media (min-width: 981px) and (max-width: 1000px)'), 'Narrow-laptop breakpoint seam is not closed.');
requireMatch(closure.includes('@media (max-width: 980px)'), 'Drawer/tablet breakpoint closure is missing.');
requireMatch(closure.includes('@media (max-width: 430px)'), 'Small-phone breakpoint closure is missing.');
requireMatch(closure.includes('100dvh'), 'Dynamic viewport height protection is missing.');
requireMatch(closure.includes('env(safe-area-inset-bottom)'), 'Mobile safe-area protection is missing.');
requireMatch(closure.includes('.page-header-actions > *'), 'Mobile page-header action sizing contract is missing.');
requireMatch(layout.includes("import './pass-54-responsive-edge-case-closure.css';"), 'Pass 54 responsive closure is not loaded.');

if (failures.length) {
  console.error('Responsive contract check failed:');
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log('Responsive contract check passed.');
