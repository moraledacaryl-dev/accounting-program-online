// Only subdivisions of one sidebar destination belong in its local navigation.
export const navigationChildren = {
  '/bookings': [
    { href: '/bookings', label: 'Bookings' },
    { href: '/bookings/calendar', label: 'Calendar' },
  ],
  '/room-types': [
    { href: '/room-types', label: 'Room Types' },
    { href: '/rooms', label: 'Rooms' },
    { href: '/rate-plans', label: 'Rate Plans' },
    { href: '/room-package-rules', label: 'Package Rules' },
    { href: '/booking-channels', label: 'Booking Channels' },
  ],
  '/inventory-items': [
    { href: '/inventory-items', label: 'Items' },
    { href: '/stock-movements', label: 'Stock Movements' },
    { href: '/menu-items', label: 'Menu & Recipes' },
    { href: '/menu-categories', label: 'Menu Categories' },
    { href: '/staff-meals', label: 'Staff Meals' },
    { href: '/setup-imports', label: 'Setup Imports' },
  ],
  '/integrations/payroll': [
    { href: '/integrations/payroll', label: 'Payroll Review Queue' },
    { href: '/employees', label: 'Employee History' },
    { href: '/attendance', label: 'Attendance History' },
    { href: '/payroll-periods', label: 'Payroll Period History' },
  ],
  '/cashflow/settings': [
    { href: '/cashflow/settings', label: 'Cash Settings' },
    { href: '/cashflow/templates', label: 'Recurring Templates' },
  ],
};
