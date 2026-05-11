'use client';

import { useEffect, useMemo, useState } from 'react';
import { me } from './api';
import { canAccess } from './permissions';

export function useCurrentUser() {
  const [user, setUser] = useState(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let active = true;
    me()
      .then((row) => {
        if (!active) return;
        setUser(row || null);
      })
      .catch(() => {
        if (!active) return;
        setUser(null);
      })
      .finally(() => {
        if (!active) return;
        setLoaded(true);
      });
    return () => {
      active = false;
    };
  }, []);

  const api = useMemo(() => ({
    user,
    loaded,
    can: (key) => canAccess(user, key),
  }), [user, loaded]);

  return api;
}

