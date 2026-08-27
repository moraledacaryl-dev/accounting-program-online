import { request } from './api';

const memoryMutationKeys = new Map();

function queryString(params = {}) {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === null || typeof value === 'undefined' || value === '') return;
    q.set(key, String(value));
  });
  const encoded = q.toString();
  return encoded ? `?${encoded}` : '';
}

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.keys(value).sort().map((key) => [key, canonicalize(value[key])]),
    );
  }
  return value;
}

function stablePayload(payload) {
  return JSON.stringify(canonicalize(payload));
}

function fingerprint(value) {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16).padStart(8, '0');
}

function randomMutationKey(scope) {
  const uuid = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${scope}:${uuid}`;
}

function mutationAttempt(scope, payload) {
  const canonical = stablePayload(payload);
  const storageKey = `hidden-oasis:idempotency:${scope}:${fingerprint(canonical)}`;

  if (typeof sessionStorage !== 'undefined') {
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey) || 'null');
      if (saved?.canonical === canonical && saved?.key) {
        return { key: saved.key, storageKey, canonical };
      }
      const key = randomMutationKey(scope);
      sessionStorage.setItem(storageKey, JSON.stringify({ key, canonical }));
      return { key, storageKey, canonical };
    } catch {
      // Fall back to process memory if storage is unavailable or corrupt.
    }
  }

  const saved = memoryMutationKeys.get(storageKey);
  if (saved?.canonical === canonical && saved?.key) return { ...saved, storageKey };
  const attempt = { key: randomMutationKey(scope), canonical };
  memoryMutationKeys.set(storageKey, attempt);
  return { ...attempt, storageKey };
}

function clearMutationAttempt(attempt) {
  memoryMutationKeys.delete(attempt.storageKey);
  if (typeof sessionStorage !== 'undefined') {
    try { sessionStorage.removeItem(attempt.storageKey); } catch { /* best effort */ }
  }
}

async function idempotentMutation(path, scope, payload) {
  const attempt = mutationAttempt(scope, payload);
  try {
    const result = await request(path, {
      method: 'POST',
      headers: { 'Idempotency-Key': attempt.key },
      body: JSON.stringify(payload),
    });
    clearMutationAttempt(attempt);
    return result;
  } catch (error) {
    // Keep the exact key so an ambiguous/network retry cannot duplicate money.
    throw error;
  }
}

export const fetchCashflowSummary = ({ date = '' } = {}) => request(`/cashflow/summary${queryString({ date })}`);

export const fetchMoneyTransactions = (params = {}) => request(`/cashflow/transactions${queryString(params)}`);
export const fetchMoneyTransaction = (id) => request(`/cashflow/transactions/${id}`);
export const createMoneyTransaction = (payload) => request('/cashflow/transactions', { method: 'POST', body: JSON.stringify(payload) });
export const updateMoneyTransaction = (id, payload) => request(`/cashflow/transactions/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
export const deleteMoneyTransaction = (id) => request(`/cashflow/transactions/${id}`, { method: 'DELETE' });
export const approveMoneyTransaction = (id, payload = {}) => request(`/cashflow/transactions/${id}/approve`, { method: 'POST', body: JSON.stringify(payload) });
export const cancelMoneyTransaction = (id, payload = {}) => request(`/cashflow/transactions/${id}/cancel`, { method: 'POST', body: JSON.stringify(payload) });
export const reverseMoneyTransaction = (id, payload = {}) => request(`/cashflow/transactions/${id}/reverse`, { method: 'POST', body: JSON.stringify(payload) });

export const fetchFinancialAccounts = (params = {}) => request(`/financial-accounts/${queryString(params)}`.replace('/?', '?'));
export const createFinancialAccount = (payload) => request('/financial-accounts/', { method: 'POST', body: JSON.stringify(payload) });
export const updateFinancialAccount = (id, payload) => request(`/financial-accounts/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
export const bootstrapFinancialAccounts = () => request('/financial-accounts/bootstrap-defaults', { method: 'POST' });

export const fetchTransfers = (params = {}) => request(`/transfers/${queryString(params)}`.replace('/?', '?'));
export const createTransfer = (payload) => request('/transfers/', { method: 'POST', body: JSON.stringify(payload) });
export const updateTransfer = (id, payload) => request(`/transfers/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
export const deleteTransfer = (id) => request(`/transfers/${id}`, { method: 'DELETE' });
export const approveTransfer = (id, payload = {}) => request(`/transfers/${id}/approve`, { method: 'POST', body: JSON.stringify(payload) });
export const cancelTransfer = (id, payload = {}) => request(`/transfers/${id}/cancel`, { method: 'POST', body: JSON.stringify(payload) });
export const reverseTransfer = (id, payload = {}) => request(`/transfers/${id}/reverse`, { method: 'POST', body: JSON.stringify(payload) });

export const fetchReconciliations = (params = {}) => request(`/reconciliations/${queryString(params)}`.replace('/?', '?'));
export const createReconciliation = (payload) => request('/reconciliations/', { method: 'POST', body: JSON.stringify(payload) });
export const updateReconciliation = (id, payload) => request(`/reconciliations/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
export const approveReconciliation = (id, payload = {}) => request(`/reconciliations/${id}/approve`, { method: 'POST', body: JSON.stringify(payload) });
export const closeReconciliation = (id, payload = {}) => request(`/reconciliations/${id}/close`, { method: 'POST', body: JSON.stringify(payload) });
export const reverseReconciliation = (id, payload = {}) => request(`/reconciliations/${id}/reverse`, { method: 'POST', body: JSON.stringify(payload) });

export const fetchReceivables = (params = {}) => request(`/receivables/${queryString(params)}`.replace('/?', '?'));
export const createReceivable = (payload) => request('/receivables/', { method: 'POST', body: JSON.stringify(payload) });
export const updateReceivable = (id, payload) => request(`/receivables/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
export const collectReceivable = (id, payload) => request(`/receivables/${id}/collect`, { method: 'POST', body: JSON.stringify(payload) });
export const reverseReceivableCollection = (id, transactionId, payload = {}) => request(`/receivables/${id}/collections/${transactionId}/reverse`, { method: 'POST', body: JSON.stringify(payload) });
export const reopenReceivable = (id, payload = {}) => request(`/receivables/${id}/reopen`, { method: 'POST', body: JSON.stringify(payload) });
export const writeOffReceivable = (id, payload = {}) => request(`/receivables/${id}/write-off`, { method: 'POST', body: JSON.stringify(payload) });

export const fetchPayables = (params = {}) => request(`/payables/${queryString(params)}`.replace('/?', '?'));
export const createPayable = (payload) => idempotentMutation('/payables/', 'payable-create', payload);
export const updatePayable = (id, payload) => request(`/payables/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
export const payPayable = (id, payload) => idempotentMutation(`/payables/${id}/pay`, `payable-payment-${id}`, payload);
export const reversePayablePayment = (id, transactionId, payload = {}) => request(`/payables/${id}/payments/${transactionId}/reverse`, { method: 'POST', body: JSON.stringify(payload) });
export const reopenPayable = (id, payload = {}) => request(`/payables/${id}/reopen`, { method: 'POST', body: JSON.stringify(payload) });
export const writeOffPayable = (id, payload = {}) => request(`/payables/${id}/write-off`, { method: 'POST', body: JSON.stringify(payload) });

export const fetchCashflowTemplates = ({ active_only = false } = {}) => request(`/cashflow-templates/${queryString({ active_only })}`.replace('/?', '?'));
export const createCashflowTemplate = (payload) => request('/cashflow-templates/', { method: 'POST', body: JSON.stringify(payload) });
export const updateCashflowTemplate = (id, payload) => request(`/cashflow-templates/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
export const deleteCashflowTemplate = (id) => request(`/cashflow-templates/${id}`, { method: 'DELETE' });
export const launchCashflowTemplate = (payload) => request('/cashflow-templates/launch', { method: 'POST', body: JSON.stringify(payload) });

export const fetchAccountLedger = (accountId, params = {}) => request(`/cashflow/accounts/${accountId}/ledger${queryString(params)}`);
export const fetchNextCodePreview = (entity, draft = '') => request(`/system-settings/next-code?entity=${encodeURIComponent(entity)}${draft ? `&draft=${encodeURIComponent(draft)}` : ''}`);