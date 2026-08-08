'use client';

import { createContext, useCallback, useContext, useRef, useState } from 'react';
import InputActionModal from './InputActionModal';

const InputActionContext = createContext(null);

export function useInputAction() {
  const inputAction = useContext(InputActionContext);
  if (!inputAction) throw new Error('useInputAction must be used within InputActionProvider.');
  return inputAction;
}

export default function InputActionProvider({ children }) {
  const resolverRef = useRef(null);
  const [options, setOptions] = useState(null);

  const settle = useCallback((result) => {
    const resolve = resolverRef.current;
    resolverRef.current = null;
    setOptions(null);
    resolve?.(result);
  }, []);

  const inputAction = useCallback((nextOptions = {}) => new Promise((resolve) => {
    resolverRef.current?.(null);
    resolverRef.current = resolve;
    setOptions({
      title: nextOptions.title || 'Enter a value',
      description: nextOptions.description || '',
      fieldLabel: nextOptions.fieldLabel || 'Value',
      defaultValue: nextOptions.defaultValue || '',
      inputType: nextOptions.inputType || 'textarea',
      required: nextOptions.required !== false,
      confirmLabel: nextOptions.confirmLabel || 'Continue',
      tone: nextOptions.tone || 'neutral',
    });
  }), []);

  return (
    <InputActionContext.Provider value={inputAction}>
      {children}
      <InputActionModal
        open={!!options}
        title={options?.title}
        description={options?.description}
        fieldLabel={options?.fieldLabel}
        defaultValue={options?.defaultValue}
        inputType={options?.inputType}
        required={options?.required}
        confirmLabel={options?.confirmLabel}
        tone={options?.tone}
        onClose={() => settle(null)}
        onConfirm={(value) => settle(value)}
      />
    </InputActionContext.Provider>
  );
}
