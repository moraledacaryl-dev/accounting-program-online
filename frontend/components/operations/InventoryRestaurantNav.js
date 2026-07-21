'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const links = [
  { href: '/inventory-items', label: 'Inventory' },
  { href: '/stock-movements', label: 'Stock movements' },
  { href: '/inventory-reconciliation', label: 'Stock counts' },
  { href: '/suppliers', label: 'Suppliers' },
  { href: '/purchase-requests', label: 'Purchase requests' },
  { href: '/purchase-orders', label: 'Purchase orders' },
  { href: '/receiving', label: 'Receiving' },
  { href: '/restaurant-ops', label: 'Restaurant operations' },
  { href: '/menu-items', label: 'Menu & recipes' },
  { href: '/staff-meals', label: 'Staff meals' },
];

const prefixes = [
  '/inventory-items', '/stock-movements', '/inventory-reconciliation', '/suppliers',
  '/purchase-requests', '/purchase-orders', '/receiving', '/restaurant-ops',
  '/menu-items', '/menu-categories', '/staff-meals', '/setup-imports',
];

function activeFor(pathname, href) {
  if (href === '/menu-items') {
    return ['/menu-items', '/menu-categories'].some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function InventoryRestaurantNav() {
  const pathname = usePathname();
  if (!prefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`))) return null;

  return (
    <nav className="operations-context-nav" aria-label="Inventory, procurement, and restaurant sections">
      <div className="operations-context-nav__label">Inventory & operations</div>
      <div className="operations-context-nav__links">
        {links.map((item) => {
          const active = activeFor(pathname, item.href);
          return (
            <Link key={item.href} href={item.href} className={active ? 'operations-context-link is-active' : 'operations-context-link'} aria-current={active ? 'page' : undefined}>
              {item.label}
            </Link>
          );
        })}
      </div>
      <div className="operations-context-nav__actions" aria-label="Common inventory actions">
        <Link href="/purchase-requests" className="operations-action">New request</Link>
        <Link href="/receiving" className="operations-action operations-action--primary">Receive stock</Link>
      </div>
    </nav>
  );
}
