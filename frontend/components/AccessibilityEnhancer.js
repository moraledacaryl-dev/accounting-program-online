'use client';

import { useEffect } from 'react';
import { usePathname } from 'next/navigation';

const CASHFLOW_FILTER_LABELS = [
  'Ledger start date',
  'Ledger end date',
  'Ledger direction',
  'Ledger status',
  'Search ledger reference or description',
];

export default function AccessibilityEnhancer() {
  const pathname = usePathname();

  useEffect(() => {
    if (pathname !== '/cashflow') return undefined;

    const applyLabels = () => {
      const controls = document.querySelectorAll('.cash-workspace .filter-bar input, .cash-workspace .filter-bar select');
      controls.forEach((control, index) => {
        if (!control.getAttribute('aria-label') && CASHFLOW_FILTER_LABELS[index]) {
          control.setAttribute('aria-label', CASHFLOW_FILTER_LABELS[index]);
        }
      });
    };

    applyLabels();
    const observer = new MutationObserver(applyLabels);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [pathname]);

  useEffect(() => {
    let frame;
    const applyScrollAccess = () => {
      document.querySelectorAll('.main .section, .main .table, .main .table-wrap, .context-nav-stack [class$="__links"]').forEach(element => {
        const style = getComputedStyle(element);
        const scrolls = element.clientWidth > 0 && element.scrollWidth > element.clientWidth + 1 && /auto|scroll/.test(style.overflowX);
        if (scrolls && !element.hasAttribute('tabindex')) {
          element.tabIndex = 0;
          element.dataset.scrollRegion = 'true';
          if (!element.hasAttribute('role') && element.tagName !== 'TABLE') { element.setAttribute('role', 'region'); element.dataset.scrollRole = 'true'; }
          if (!element.hasAttribute('aria-label') && !element.hasAttribute('aria-labelledby')) {
            const section = element.closest('.section');
            const heading = section?.querySelector('h2, h1, h3')?.textContent;
            element.setAttribute('aria-label', `${heading || (element.closest('nav') ? 'Section navigation' : 'Data table')} — scroll horizontally`);
            element.dataset.scrollLabel = 'true';
          }
        } else if (!scrolls && element.dataset.scrollRegion) {
          element.removeAttribute('tabindex');
          delete element.dataset.scrollRegion;
          if (element.dataset.scrollRole) { element.removeAttribute('role'); delete element.dataset.scrollRole; }
          if (element.dataset.scrollLabel) { element.removeAttribute('aria-label'); delete element.dataset.scrollLabel; }
        }
      });
    };
    const schedule = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(applyScrollAccess); };
    const observer = new MutationObserver(schedule);
    observer.observe(document.body, { childList: true, subtree: true });
    window.addEventListener('resize', schedule);
    schedule();
    return () => { cancelAnimationFrame(frame); observer.disconnect(); window.removeEventListener('resize', schedule); };
  }, [pathname]);

  return null;
}
