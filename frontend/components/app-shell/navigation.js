export const navigationGroups = [
  {
    id: 'main',
    label: 'Daily Work',
    items: [
      { href: '/dashboard', label: 'Dashboard', icon: 'dashboard', permissionsAny: ['dashboard.view'] },
      { href: '/start-of-day', label: 'Start of Day', icon: 'sun', permissionsAny: ['dashboard.view', 'cashflow.view'] },
      { href: '/review-inbox', label: 'Review Inbox', icon: 'review', permissionsAny: ['approvals.view', 'integrations.view'] },
      { href: '/approvals', label: 'Approvals', icon: 'shield', permissionsAny: ['approvals.view'] },
      { href: '/staff-guide', label: 'Staff Guide', icon: 'book', permissionsAny: [] },
    ],
  },
  {
    id: 'hotel',
    label: 'Hotel Operations',
    items: [
      { href: '/bookings', label: 'Bookings', icon: 'calendar', permissionsAny: ['bookings.view'] },
      { href: '/guests', label: 'Guests', icon: 'users', permissionsAny: ['guests.view'] },
      { href: '/room-folios', label: 'Guest Folios', icon: 'receipt', permissionsAny: ['folios.view'] },
      { href: '/events', label: 'Events', icon: 'event', permissionsAny: ['bookings.view', 'cashflow.view'] },
      { href: '/channel-payouts', label: 'Channel Payouts', icon: 'payout', permissionsAny: ['bookings.view', 'cashflow.view', 'reports.view'] },
    ],
  },
  {
    id: 'finance',
    label: 'Finance & Accounting',
    items: [
      { href: '/cashflow', label: 'Cash & Treasury', icon: 'wallet', permissionsAny: ['cashflow.view'] },
      { href: '/cashflow/payables', label: 'Payables', icon: 'payable', permissionsAny: ['cashflow.view'] },
      { href: '/cashflow/receivables', label: 'Receivables', icon: 'receivable', permissionsAny: ['cashflow.view'] },
      { href: '/journals', label: 'Journals', icon: 'journal', permissionsAny: ['journals.view'] },
      { href: '/bir', label: 'Tax & Period Close', icon: 'file', permissionsAny: ['bir.view'] },
      { href: '/assets', label: 'Fixed Assets', icon: 'asset', permissionsAny: ['assets.view'] },
      { href: '/reports', label: 'Reports', icon: 'chart', permissionsAny: ['reports.view'] },
      { href: '/attachments', label: 'Files & Evidence', icon: 'paperclip', permissionsAny: ['reports.view', 'cashflow.view', 'bookings.view', 'assets.view', 'bir.view'] },
    ],
  },
  {
    id: 'setup',
    label: 'Setup & Administration',
    items: [
      { href: '/room-types', label: 'Rooms & Rates', icon: 'hotel', permissionsAny: ['room_setup.view'] },
      { href: '/chart-of-accounts', label: 'Chart of Accounts', icon: 'accounts', permissionsAny: ['chart_of_accounts.manage'] },
      { href: '/account-mapping', label: 'Posting Rules', icon: 'mapping', permissionsAny: ['account_mapping.manage'] },
      { href: '/master-data', label: 'Master Data', icon: 'database', permissionsAny: ['master_data.manage', 'taxonomy.manage'] },
      { href: '/roles-permissions', label: 'Users & Access', icon: 'shield', permissionsAny: ['roles.manage', 'users.manage'] },
      { href: '/integrations/beds24', label: 'Beds24 Integration', icon: 'link', permissionsAny: ['integrations.view'] },
      { href: '/system-settings', label: 'System Settings', icon: 'settings', permissionsAny: ['system_settings.manage', 'integrations.manage'] },
    ],
  },
];

export const legacyWorkspaceLinks = [
  { href: '/restaurant-ops', label: 'Restaurant Operations', app: 'POS Cloud' },
  { href: '/inventory-items', label: 'Inventory & Purchasing', app: 'Inventory & Procurement' },
  { href: '/payroll-periods', label: 'People & Payroll', app: 'Staff & Payroll' },
];
