'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const links = [
  { href: '/bookings', label: 'Today & bookings' },
  { href: '/bookings/calendar', label: 'Calendar' },
  { href: '/guests', label: 'Guests' },
  { href: '/room-folios', label: 'Guest folios' },
  { href: '/events', label: 'Events' },
  { href: '/channel-payouts', label: 'Channel payouts' },
  { href: '/room-types', label: 'Rooms & rates' },
];

const hotelPrefixes = [
  '/bookings', '/guests', '/room-folios', '/events', '/channel-payouts',
  '/room-types', '/rooms', '/rate-plans', '/booking-channels', '/room-package-rules',
];

function activeFor(pathname, href) {
  if (href === '/bookings') return pathname === '/bookings' || /^\/bookings\/\d+/.test(pathname);
  if (href === '/room-types') return ['/room-types', '/rooms', '/rate-plans', '/booking-channels', '/room-package-rules'].some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function HotelOperationsNav() {
  const pathname = usePathname();
  if (!hotelPrefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`))) return null;

  return (
    <nav className="hotel-context-nav" aria-label="Hotel operations sections">
      <div className="hotel-context-nav__label">Hotel operations</div>
      <div className="hotel-context-nav__links">
        {links.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={activeFor(pathname, item.href) ? 'hotel-context-link is-active' : 'hotel-context-link'}
            aria-current={activeFor(pathname, item.href) ? 'page' : undefined}
          >
            {item.label}
          </Link>
        ))}
      </div>
    </nav>
  );
}
