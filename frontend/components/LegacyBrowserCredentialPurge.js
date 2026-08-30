'use client';

import { useLayoutEffect } from 'react';

const LEGACY_BROWSER_TOKEN_KEY = 'erp_token';

export default function LegacyBrowserCredentialPurge() {
  useLayoutEffect(() => {
    try {
      window.localStorage.removeItem(LEGACY_BROWSER_TOKEN_KEY);
    } catch {
      // Storage may be unavailable under hardened browser privacy settings.
    }
  }, []);

  return null;
}
