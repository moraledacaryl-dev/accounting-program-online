import { request } from './api';
import { idempotentMutation } from './cashflowApi';

function queryString(params = {}) {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === null || typeof value === 'undefined' || value === '') return;
    q.set(key, String(value));
  });
  const encoded = q.toString();
  return encoded ? `?${encoded}` : '';
}

export const fetchSupplierCredits = (params = {}) => request(`/supplier-credits/${queryString(params)}`.replace('/?', '?'));

export const applySupplierCredit = (creditId, payload) => (
  idempotentMutation(
    `/supplier-credits/${creditId}/apply`,
    `supplier-credit-apply-${creditId}`,
    payload,
  )
);

export const reverseSupplierCreditApplication = (applicationId, payload) => (
  idempotentMutation(
    `/supplier-credits/applications/${applicationId}/reverse`,
    `supplier-credit-reverse-${applicationId}`,
    payload,
  )
);
