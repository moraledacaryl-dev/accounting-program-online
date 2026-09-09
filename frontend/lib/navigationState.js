import { navigationChildren } from './navigationChildren';

export function canonicalNavigationPath(pathname, search = '') {
  const aliases = { '/channels': '/booking-channels', '/room-setup': '/room-types', '/recipes': '/menu-items', '/payroll': '/payroll-periods', '/treasury': '/cashflow', '/cashflow/accounts': '/cashflow/ledger', '/cashflow/reconciliation': '/cashflow/daily-cash' };
  pathname = aliases[pathname] || pathname;
  if (/^\/cashflow\/\d+$/.test(pathname)) return '/cashflow/ledger';
  if (pathname !== '/cashflow') return pathname;
  const params = new URLSearchParams(search);
  const action = params.get('action');
  if (action === 'money-in') return '/cashflow/money-in';
  if (action === 'money-out') return '/cashflow/money-out';
  if (action === 'transfer' || params.get('tab') === 'transfers') return '/cashflow/transfers';
  if (params.get('tab') === 'close') return '/cashflow/daily-cash';
  if (params.get('tab') === 'ledger') return '/cashflow/ledger';
  if (params.get('tab') === 'settings') return '/cashflow/settings';
  return pathname;
}

export function activeNavigationItem(pathname, search, groups) {
  const current = canonicalNavigationPath(pathname, search);
  return groups.flatMap(group => group.items.flatMap(item => [item, ...(navigationChildren[item.href] || [])]
    .filter(candidate => current === candidate.href || current.startsWith(`${candidate.href}/`))
    .map(candidate => ({ ...item, groupId: group.id, groupLabel: group.label, page: candidate, matchLength: candidate.href.length }))))
    .sort((a, b) => b.matchLength - a.matchLength)[0] || null;
}
