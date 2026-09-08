export function canonicalNavigationPath(pathname, search = '') {
  if (pathname !== '/cashflow') return pathname;
  const params = new URLSearchParams(search);
  const action = params.get('action');
  if (action === 'money-in') return '/cashflow/money-in';
  if (action === 'money-out') return '/cashflow/money-out';
  if (action === 'transfer' || params.get('tab') === 'transfers') return '/cashflow/transfers';
  if (params.get('tab') === 'close') return '/cashflow/daily-cash';
  return pathname;
}

export function activeNavigationItem(pathname, search, groups) {
  const current = canonicalNavigationPath(pathname, search);
  return groups.flatMap(group => group.items.map(item => ({ ...item, groupId: group.id })))
    .filter(item => current === item.href || current.startsWith(`${item.href}/`))
    .sort((a, b) => b.href.length - a.href.length)[0] || null;
}
