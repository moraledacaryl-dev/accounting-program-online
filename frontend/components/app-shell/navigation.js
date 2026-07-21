export const navigationGroups = [
  {
    id: 'main',
    label: 'Main',
    items: [
      { href: '/dashboard', label: 'Dashboard', icon: 'dashboard', permissionsAny: ['dashboard.view'] },
      { href: '/start-of-day', label: 'Start of Day', icon: 'sun', permissionsAny: ['dashboard.view', 'cashflow.view'] },
      { href: '/review-inbox', label: 'Review Inbox', icon: 'review', permissionsAny: ['approvals.view', 'integrations.view'] },
      { href: '/staff-guide', label: 'Staff Guide', icon: 'book', permissionsAny: [] },
    ],
  },
  {
    id: 'hotel',
    label: 'Hotel Operations',
    items: [
      { href: '/bookings', label: 'Bookings', icon: 'calendar', permissionsAny: ['bookings.view'] },
      { href: '/guests', label: 'Guests', icon: 'users', permissionsAny: ['guests.view'] },
      { href: '/room-folios', label: 'Folios', icon: 'receipt', permissionsAny: ['folios.view'] },
      { href: '/events', label: 'Events', icon: 'event', permissionsAny: ['bookings.view', 'cashflow.view'] },
      { href: '/channel-payouts', label: 'Channel Payouts', icon: 'payout', permissionsAny: ['bookings.view', 'cashflow.view', 'reports.view'] },
    ],
  },
  {
    id: 'finance',
    label: 'Finance',
    items: [
      { href: '/cashflow', label: 'Cash & Treasury', icon: 'wallet', permissionsAny: ['cashflow.view'] },
      { href: '/cashflow/payables', label: 'Payables', icon: 'payable', permissionsAny: ['cashflow.view'] },
      { href: '/cashflow/receivables', label: 'Receivables', icon: 'receivable', permissionsAny: ['cashflow.view'] },
      { href: '/journals', label: 'Journals', icon: 'journal', permissionsAny: ['journals.view'] },
      { href: '/bir', label: 'BIR & Periods', icon: 'file', permissionsAny: ['bir.view'] },
      { href: '/assets', label: 'Financial Assets', icon: 'asset', permissionsAny: ['assets.view'] },
      { href: '/reports', label: 'Reports', icon: 'chart', permissionsAny: ['reports.view'] },
      { href: '/attachments', label: 'Attachments', icon: 'paperclip', permissionsAny: ['reports.view', 'cashflow.view', 'bookings.view', 'assets.view', 'bir.view'] },
    ],
  },
  {
    id: 'setup',
    label: 'Setup & Administration',
    items: [
      { href: '/room-setup', label: 'Hotel Setup', icon: 'hotel', permissionsAny: ['room_setup.view'] },
      { href: '/chart-of-accounts', label: 'Chart of Accounts', icon: 'accounts', permissionsAny: ['chart_of_accounts.manage'] },
      { href: '/account-mapping', label: 'Account Mapping', icon: 'mapping', permissionsAny: ['account_mapping.manage'] },
      { href: '/master-data', label: 'Master Data', icon: 'database', permissionsAny: ['master_data.manage', 'taxonomy.manage'] },
      { href: '/roles-permissions', label: 'Users & Access', icon: 'shield', permissionsAny: ['roles.manage', 'users.manage'] },
      { href: '/integrations/beds24', label: 'Beds24', icon: 'link', permissionsAny: ['integrations.view'] },
      { href: '/system-settings', label: 'System Settings', icon: 'settings', permissionsAny: ['system_settings.manage', 'integrations.manage'] },
    ],
  },
];

export const legacyWorkspaceLinks = [
  { href: '/workspace/restaurant', label: 'Restaurant & F&B', app: 'POS Cloud' },
  { href: '/workspace/inventory', label: 'Inventory & Purchasing', app: 'Inventory & Procurement' },
  { href: '/workspace/payroll', label: 'People & Payroll', app: 'Staff & Payroll' },
];
