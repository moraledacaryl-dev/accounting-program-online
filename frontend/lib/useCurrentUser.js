'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { me } from './api';
import { canAccess } from './permissions';

const CurrentUserContext = createContext({
  user: null,
  loaded: false,
  can: () => false,
  refresh: async () => null,
});

export function CurrentUserProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loaded, setLoaded] = useState(false);

  const loadUser = useCallback(async () => {
    setLoaded(false);
    try {
      const row = await me();
      setUser(row || null);
      return row || null;
    } catch {
      setUser(null);
      return null;
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  const api = useMemo(() => ({
    user,
    loaded,
    can: (key) => canAccess(user, key),
    refresh: loadUser,
  }), [user, loaded, loadUser]);

  return <CurrentUserContext.Provider value={api}>{children}</CurrentUserContext.Provider>;
}

export function useCurrentUser() {
  return useContext(CurrentUserContext);
}
