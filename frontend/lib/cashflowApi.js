import { request } from './api';

function queryString(params = {}) {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === null || typeof value === 'undefined' || value === '') return;
    q.set(key, String(value));
  });
  const encoded = q.toString();
  return encoded ? `?${encoded}` : '';
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
export const createPayable = (payload) => request('/payables/', { method: 'POST', body: JSON.stringify(payload) });
export const updatePayable = (id, payload) => request(`/payables/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
export const payPayable = (id, payload) => request(`/payables/${id}/pay`, { method: 'POST', body: JSON.stringify(payload) });
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
