'use client';

import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { useCurrentUser } from '../../lib/useCurrentUser';

const AppShellContext = createContext(null);

export function AppShellProvider({ children }) {
  const currentUser = useCurrentUser();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const openMobileNav = useCallback(() => setMobileNavOpen(true), []);
  const closeMobileNav = useCallback(() => setMobileNavOpen(false), []);
  const toggleMobileNav = useCallback(() => setMobileNavOpen((value) => !value), []);

  const value = useMemo(() => ({
    ...currentUser,
    mobileNavOpen,
    openMobileNav,
    closeMobileNav,
    toggleMobileNav,
  }), [currentUser, mobileNavOpen, openMobileNav, closeMobileNav, toggleMobileNav]);

  return <AppShellContext.Provider value={value}>{children}</AppShellContext.Provider>;
}

export function useAppShell() {
  const value = useContext(AppShellContext);
  if (!value) throw new Error('useAppShell must be used inside AppShellProvider');
  return value;
}
