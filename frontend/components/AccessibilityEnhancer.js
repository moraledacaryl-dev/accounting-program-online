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

  return null;
}
