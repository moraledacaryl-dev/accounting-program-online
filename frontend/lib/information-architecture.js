export const canonicalRoutes = {
  dashboard: '/dashboard',
  startOfDay: '/start-of-day',
  reviewInbox: '/review-inbox',
  approvals: '/approvals',
  bookings: '/bookings',
  guests: '/guests',
  folios: '/room-folios',
  events: '/events',
  bookingChannels: '/booking-channels',
  roomTypes: '/room-types',
  payrollPeriods: '/payroll-periods',
  cashTreasury: '/cashflow',
  restaurantOperations: '/restaurant-ops',
  inventoryItems: '/inventory-items',
  systemSettings: '/system-settings',
};

export const legacyRouteRedirects = {
  '/channels': canonicalRoutes.bookingChannels,
  '/treasury': canonicalRoutes.cashTreasury,
  '/payroll': canonicalRoutes.payrollPeriods,
  '/recipes': '/menu-items',
  '/room-setup': canonicalRoutes.roomTypes,
};

export const workspaceRedirects = {
  rooms: canonicalRoutes.bookings,
  events: canonicalRoutes.events,
  restaurant: canonicalRoutes.restaurantOperations,
  breakfast: `${canonicalRoutes.restaurantOperations}?station=breakfast`,
  cafe: `${canonicalRoutes.restaurantOperations}?station=cafe`,
  bar: `${canonicalRoutes.restaurantOperations}?station=bar`,
  inventory: canonicalRoutes.inventoryItems,
  payroll: canonicalRoutes.payrollPeriods,
  finance: canonicalRoutes.cashTreasury,
  settings: canonicalRoutes.systemSettings,
};

export const productTerminology = {
  reviewInbox: {
    label: 'Review Inbox',
    definition: 'Validate financial events received from connected applications before Accounting accepts or rejects them.',
  },
  approvals: {
    label: 'Approvals',
    definition: 'Authorize operational or financial actions that require a manager or designated approver.',
  },
  folios: {
    label: 'Guest Folios',
    definition: 'Guest stay charges, deposits, payments, refunds, adjustments, and balances.',
  },
  assets: {
    label: 'Fixed Assets',
    definition: 'Capitalized property and equipment, depreciation, impairment, maintenance, and disposal.',
  },
  taxClose: {
    label: 'Tax & Period Close',
    definition: 'BIR books, compliance review, accounting-period locks, and controlled reopening.',
  },
  evidence: {
    label: 'Files & Evidence',
    definition: 'Documents and supporting files linked to operational and accounting records.',
  },
};

export function humanizeStatus(value) {
  return String(value || '')
    .replaceAll('_', ' ')
    .replaceAll('-', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
