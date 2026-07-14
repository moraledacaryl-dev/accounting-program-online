'use client';

import { createContext, useContext, useMemo, useState } from 'react';
import { useCurrentUser } from '../../lib/useCurrentUser';

const AppShellContext = createContext(null);

export function AppShellProvider({ children }) {
  const currentUser = useCurrentUser();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const value = useMemo(() => ({
    ...currentUser,
    mobileNavOpen,
    openMobileNav: () => setMobileNavOpen(true),
    closeMobileNav: () => setMobileNavOpen(false),
    toggleMobileNav: () => setMobileNavOpen((value) => !value),
  }), [currentUser, mobileNavOpen]);

  return <AppShellContext.Provider value={value}>{children}</AppShellContext.Provider>;
}

export function useAppShell() {
  const value = useContext(AppShellContext);
  if (!value) throw new Error('useAppShell must be used inside AppShellProvider');
  return value;
}
