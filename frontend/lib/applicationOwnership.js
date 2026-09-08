const EXTERNAL_OWNERSHIP = [
  {
    appName: 'Inventory & Procurement',
    appUrlEnv: 'NEXT_PUBLIC_INVENTORY_APP_URL',
    routes: [
      '/inventory-items',
      '/inventory-reconciliation',
      '/stock-movements',
      '/suppliers',
      '/purchase-requests',
      '/purchase-orders',
      '/receiving',
      '/setup-imports',
      '/staff-meals',
      '/recipes',
      '/menu-items',
      '/menu-categories',
    ],
  },
  {
    appName: 'POS Cloud',
    appUrlEnv: 'NEXT_PUBLIC_POS_APP_URL',
    routes: [
      '/restaurant-ops',
    ],
  },
];

function environmentUrl(key) {
  if (key === 'NEXT_PUBLIC_INVENTORY_APP_URL') return process.env.NEXT_PUBLIC_INVENTORY_APP_URL || 'https://inventory.hiddenoasis.app';
  if (key === 'NEXT_PUBLIC_POS_APP_URL') return process.env.NEXT_PUBLIC_POS_APP_URL || 'https://pos.hiddenoasis.app';
  return '';
}

export function ownershipForPath(pathname = '') {
  const owner = EXTERNAL_OWNERSHIP.find((entry) => entry.routes.some((route) => pathname === route || pathname.startsWith(`${route}/`)));
  if (!owner) return null;
  const destinations = {
    '/inventory-items': '/items', '/inventory-reconciliation': '/counts',
    '/stock-movements': '/stock', '/suppliers': '/suppliers',
    '/purchase-requests': '/purchasing', '/purchase-orders': '/purchasing',
    '/receiving': '/receiving', '/setup-imports': '/items',
    '/restaurant-ops': '/pos', '/menu-items': '/fnb', '/menu-categories': '/fnb',
    '/recipes': '/production', '/staff-meals': '/stock',
  };
  const route = owner.routes.find(route => pathname === route || pathname.startsWith(`${route}/`));
  const base = environmentUrl(owner.appUrlEnv);
  return { ...owner, appUrl: base ? `${base.replace(/\/$/, '')}${destinations[route] || ''}` : '',
    explanation: route === '/staff-meals' ? 'Record ingredients used for staff meals in Inventory → Stock → Issue, with the meal date, dish, and department in the notes. This records stock usage; a dedicated meal log is not yet available in Inventory. Accounting retains the earlier meal history below.' : undefined,
    actionLabel: route === '/staff-meals' ? 'Record ingredient usage in Inventory' : undefined,
  };
}

export const externallyOwnedRoutes = EXTERNAL_OWNERSHIP.flatMap((entry) => entry.routes);
