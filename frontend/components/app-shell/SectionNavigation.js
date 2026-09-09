'use client';

import Link from 'next/link';
import { usePathname, useSearchParams } from 'next/navigation';
import { activeNavigationItem } from '../../lib/navigationState';
import { navigationChildren } from '../../lib/navigationChildren';
import { pathHasAccess } from '../../lib/routeAccess';
import { canAccess } from '../../lib/permissions';
import { navigationGroups } from './navigation';
import { useAppShell } from './AppShellContext';

export default function SectionNavigation() {
  const pathname = usePathname();
  const search = useSearchParams();
  const { user } = useAppShell();
  const location = activeNavigationItem(pathname, search.toString(), navigationGroups);
  if (!location) return null;
  const allowed = href => pathHasAccess(href, permission => canAccess(user, permission));
  const children = (navigationChildren[location.href] || []).filter(item => allowed(item.href));
  // Cash workspace already has one local tab row; templates need its return link.
  const showChildren = children.length > 1 && pathname !== '/cashflow';
  return (
    <div className="context-nav-stack section-navigation" data-context-section={location.groupId}>
      <nav className="location-trail" aria-label="Page location">
        <span>{location.groupLabel}</span><span aria-hidden="true">/</span>
        {location.page.href !== location.href
          ? <>{allowed(location.href) ? <Link href={location.href}>{location.label}</Link> : <span>{location.label}</span>}<span aria-hidden="true">/</span><span aria-current="page">{location.page.label}</span></>
          : <span aria-current="page">{location.label}</span>}
      </nav>
      {showChildren && <nav className="section-navigation__links" aria-label={`${location.label} pages`}>
        {children.map(item => <Link key={item.href} href={item.href} aria-current={item.href === location.page.href ? 'page' : undefined}>{item.label}</Link>)}
      </nav>}
    </div>
  );
}
