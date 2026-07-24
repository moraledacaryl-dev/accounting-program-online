'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const links = [
  { href: '/room-types', label: 'Room types', group: 'rooms' },
  { href: '/rooms', label: 'Rooms', group: 'rooms' },
  { href: '/rate-plans', label: 'Rate plans', group: 'rooms' },
  { href: '/room-package-rules', label: 'Package rules', group: 'rooms' },
  { href: '/booking-channels', label: 'Booking channels', group: 'channels' },
  { href: '/chart-of-accounts', label: 'Chart of accounts', group: 'finance' },
  { href: '/account-mapping', label: 'Posting rules', group: 'finance' },
  { href: '/master-data', label: 'Master data', group: 'data' },
  { href: '/taxonomy-admin', label: 'Taxonomies', group: 'data' },
  { href: '/users', label: 'Users', group: 'access' },
  { href: '/roles-permissions', label: 'Roles & permissions', group: 'access' },
  { href: '/integrations/beds24', label: 'Beds24', group: 'system' },
  { href: '/system-settings', label: 'System settings', group: 'system' },
];

const prefixes = [
  '/room-types', '/rooms', '/room-setup', '/rate-plans', '/room-package-rules',
  '/booking-channels', '/channels', '/chart-of-accounts', '/account-mapping',
  '/master-data', '/taxonomy-admin', '/users', '/roles-permissions',
  '/integrations', '/system-settings',
];

function activeFor(pathname, item) {
  if (item.href === '/room-types') return pathname === '/room-types' || pathname.startsWith('/room-types/') || pathname === '/room-setup';
  if (item.href === '/booking-channels') return pathname === '/booking-channels' || pathname.startsWith('/booking-channels/') || pathname === '/channels';
  return pathname === item.href || pathname.startsWith(`${item.href}/`);
}

export default function SetupAdministrationNav() {
  const pathname = usePathname();
  if (!prefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`))) return null;

  return (
    <nav className="setup-context-nav" aria-label="Setup and administration sections">
      <div className="setup-context-nav__label">Setup & administration</div>
      <div className="setup-context-nav__links">
        {links.map((item) => {
          const active = activeFor(pathname, item);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={active ? 'setup-context-link is-active' : 'setup-context-link'}
              aria-current={active ? 'page' : undefined}
              data-group={item.group}
            >
              {item.label}
            </Link>
          );
        })}
      </div>
      <div className="setup-context-nav__actions" aria-label="Common setup actions">
        <Link href="/rooms" className="setup-action">Manage rooms</Link>
        <Link href="/system-settings" className="setup-action setup-action--primary">System settings</Link>
      </div>
    </nav>
  );
}
