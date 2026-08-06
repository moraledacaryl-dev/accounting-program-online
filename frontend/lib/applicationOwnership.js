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
    ],
  },
  {
    appName: 'POS Cloud',
    appUrlEnv: 'NEXT_PUBLIC_POS_APP_URL',
    routes: [
      '/restaurant-ops',
      '/menu-categories',
      '/menu-items',
      '/recipes',
      '/staff-meals',
    ],
  },
];

function environmentUrl(key) {
  if (key === 'NEXT_PUBLIC_INVENTORY_APP_URL') return process.env.NEXT_PUBLIC_INVENTORY_APP_URL || '';
  if (key === 'NEXT_PUBLIC_POS_APP_URL') return process.env.NEXT_PUBLIC_POS_APP_URL || '';
  return '';
}

export function ownershipForPath(pathname = '') {
  const owner = EXTERNAL_OWNERSHIP.find((entry) => entry.routes.some((route) => pathname === route || pathname.startsWith(`${route}/`)));
  if (!owner) return null;
  return { ...owner, appUrl: environmentUrl(owner.appUrlEnv) };
}

export const externallyOwnedRoutes = EXTERNAL_OWNERSHIP.flatMap((entry) => entry.routes);
