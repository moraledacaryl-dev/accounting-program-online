export const navigationGroups = [
  {
    label: 'Main',
    items: [
      { href: '/dashboard', label: 'Dashboard', short: 'DB', permissionsAny: ['dashboard.view'] },
      { href: '/start-of-day', label: 'Start of Day', short: 'SD', permissionsAny: ['dashboard.view', 'cashflow.view'] },
      { href: '/review-inbox', label: 'Review Inbox', short: 'RI', permissionsAny: ['approvals.view', 'integrations.view'] },
      { href: '/staff-guide', label: 'Staff Guide', short: 'SG', permissionsAny: [] },
    ],
  },
  {
    label: 'Hotel Operations',
    items: [
      { href: '/bookings', label: 'Bookings', short: 'BK', permissionsAny: ['bookings.view'] },
      { href: '/guests', label: 'Guests', short: 'GU', permissionsAny: ['guests.view'] },
      { href: '/room-folios', label: 'Folios', short: 'FO', permissionsAny: ['folios.view'] },
      { href: '/events', label: 'Events', short: 'EV', permissionsAny: ['bookings.view', 'cashflow.view'] },
      { href: '/channel-payouts', label: 'Channel Payouts', short: 'CP', permissionsAny: ['bookings.view', 'cashflow.view', 'reports.view'] },
    ],
  },
  {
    label: 'Finance',
    items: [
      { href: '/cashflow', label: 'Cash & Treasury', short: 'CT', permissionsAny: ['cashflow.view'] },
      { href: '/cashflow/payables', label: 'Payables', short: 'AP', permissionsAny: ['cashflow.view'] },
      { href: '/cashflow/receivables', label: 'Receivables', short: 'AR', permissionsAny: ['cashflow.view'] },
      { href: '/journals', label: 'Journals', short: 'JE', permissionsAny: ['journals.view'] },
      { href: '/bir', label: 'BIR & Periods', short: 'BR', permissionsAny: ['bir.view'] },
      { href: '/assets', label: 'Financial Assets', short: 'FA', permissionsAny: ['assets.view'] },
      { href: '/reports', label: 'Reports', short: 'RP', permissionsAny: ['reports.view'] },
      { href: '/attachments', label: 'Attachments', short: 'AT', permissionsAny: ['reports.view', 'cashflow.view', 'bookings.view', 'assets.view', 'bir.view'] },
    ],
  },
  {
    label: 'Setup',
    items: [
      { href: '/room-setup', label: 'Hotel Setup', short: 'HS', permissionsAny: ['room_setup.view'] },
      { href: '/chart-of-accounts', label: 'Chart of Accounts', short: 'CO', permissionsAny: ['chart_of_accounts.manage'] },
      { href: '/account-mapping', label: 'Account Mapping', short: 'AM', permissionsAny: ['account_mapping.manage'] },
      { href: '/master-data', label: 'Master Data', short: 'MD', permissionsAny: ['master_data.manage', 'taxonomy.manage'] },
      { href: '/roles-permissions', label: 'Users & Access', short: 'UA', permissionsAny: ['roles.manage', 'users.manage'] },
      { href: '/integrations/beds24', label: 'Beds24', short: 'B2', permissionsAny: ['integrations.view'] },
      { href: '/system-settings', label: 'System Settings', short: 'SS', permissionsAny: ['system_settings.manage', 'integrations.manage'] },
    ],
  },
];

export const legacyWorkspaceLinks = [
  { href: '/workspace/restaurant', label: 'Restaurant & F&B', app: 'POS Cloud' },
  { href: '/workspace/inventory', label: 'Inventory & Purchasing', app: 'Inventory & Procurement' },
  { href: '/workspace/payroll', label: 'People & Payroll', app: 'Staff & Payroll' },
];
