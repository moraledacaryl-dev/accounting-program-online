'use client';

import { createContext, useCallback, useContext, useRef, useState } from 'react';
import ConfirmActionModal from './ConfirmActionModal';

const ConfirmActionContext = createContext(null);

export function useConfirmAction() {
  const confirmAction = useContext(ConfirmActionContext);
  if (!confirmAction) throw new Error('useConfirmAction must be used within ConfirmActionProvider.');
  return confirmAction;
}

export default function ConfirmActionProvider({ children }) {
  const resolverRef = useRef(null);
  const [options, setOptions] = useState(null);

  const settle = useCallback((result) => {
    const resolve = resolverRef.current;
    resolverRef.current = null;
    setOptions(null);
    resolve?.(result);
  }, []);

  const confirmAction = useCallback((nextOptions = {}) => new Promise((resolve) => {
    resolverRef.current?.(false);
    resolverRef.current = resolve;
    setOptions({
      title: nextOptions.title || 'Continue with this action?',
      description: nextOptions.description || '',
      confirmLabel: nextOptions.confirmLabel || 'Continue',
      tone: nextOptions.tone || 'danger',
      reasonRequired: !!nextOptions.reasonRequired,
    });
  }), []);

  return (
    <ConfirmActionContext.Provider value={confirmAction}>
      {children}
      <ConfirmActionModal
        open={!!options}
        title={options?.title}
        description={options?.description}
        confirmLabel={options?.confirmLabel}
        tone={options?.tone}
        reasonRequired={options?.reasonRequired}
        onClose={() => settle(false)}
        onConfirm={(reason) => settle(reason || true)}
      />
    </ConfirmActionContext.Provider>
  );
}
