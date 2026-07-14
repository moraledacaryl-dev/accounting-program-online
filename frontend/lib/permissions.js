export const ROLE_PERMISSION_FALLBACKS = {
  owner: ['*'],
  admin: ['*'],
  manager: [
    'dashboard.view',
    'bookings.view', 'bookings.create', 'bookings.edit', 'bookings.cancel',
    'folios.view', 'folios.manage',
    'guests.view', 'guests.create', 'guests.edit',
    'room_setup.view', 'room_setup.manage',
    'restaurant.view', 'menu.view', 'menu.manage', 'recipes.manage',
    'staff_meals.view', 'staff_meals.manage',
    'inventory.view', 'inventory.manage', 'stock_movements.create', 'inventory_reconciliation.manage',
    'suppliers.view', 'suppliers.manage',
    'purchase_requests.view', 'purchase_requests.create', 'purchase_requests.approve',
    'purchase_orders.view', 'purchase_orders.create', 'purchase_orders.approve',
    'receiving.view', 'receiving.post',
    'employees.view', 'employees.manage', 'attendance.view', 'attendance.manage',
    'payroll_periods.view', 'payroll_periods.manage', 'approvals.view', 'approvals.act',
    'cashflow.view', 'cashflow.money_in', 'cashflow.money_out', 'cashflow.transfers', 'cashflow.reconcile',
    'journals.view', 'journals.post', 'reports.view', 'assets.view', 'assets.manage', 'bir.view', 'bir.manage',
    'master_data.manage', 'taxonomy.manage', 'chart_of_accounts.manage', 'account_mapping.manage',
    'integrations.view', 'integrations.manage', 'integrations.sync', 'integrations.logs.view',
  ],
  accounting_admin: [
    'dashboard.view',
    'cashflow.view', 'cashflow.money_in', 'cashflow.money_out', 'cashflow.transfers', 'cashflow.reconcile',
    'journals.view', 'journals.post', 'reports.view', 'assets.view', 'assets.manage', 'bir.view', 'bir.manage',
    'chart_of_accounts.manage', 'account_mapping.manage',
    'integrations.view', 'integrations.sync', 'integrations.logs.view',
  ],
  front_desk: [
    'dashboard.view',
    'bookings.view', 'bookings.create', 'bookings.edit',
    'folios.view', 'folios.manage',
    'guests.view', 'guests.create', 'guests.edit',
    'room_setup.view',
    'cashflow.view', 'cashflow.money_in', 'cashflow.reconcile',
  ],
  cashier: [
    'dashboard.view', 'folios.view', 'cashflow.view', 'cashflow.money_in', 'cashflow.reconcile',
    'integrations.view',
  ],
  auditor: [
    'dashboard.view', 'bookings.view', 'folios.view', 'guests.view',
    'cashflow.view', 'journals.view', 'reports.view', 'assets.view', 'bir.view',
    'integrations.view', 'integrations.logs.view',
  ],
  staff: [
    'dashboard.view',
    'bookings.view', 'guests.view', 'restaurant.view', 'inventory.view',
    'cashflow.view',
  ],
};

export function effectivePermissions(user) {
  const explicit = Array.isArray(user?.permissions) ? user.permissions.filter(Boolean) : [];
  if (explicit.length) return new Set(explicit);
  const role = String(user?.role || '').toLowerCase();
  const fallback = ROLE_PERMISSION_FALLBACKS[role] || [];
  return new Set(fallback);
}

export function canAccess(user, key) {
  if (!key) return true;
  const perms = effectivePermissions(user);
  if (perms.has('*')) return true;
  return perms.has(key);
}

export function filterByPermission(items, user) {
  return (items || []).filter((item) => canAccess(user, item.permission));
}
