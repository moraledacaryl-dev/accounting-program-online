'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import CashflowTabs from '../../components/cashflow/CashflowTabs';
import CashflowSummaryCards from '../../components/cashflow/CashflowSummaryCards';
import QuickEntryButtons from '../../components/cashflow/QuickEntryButtons';
import PaymentMethodBadge from '../../components/cashflow/PaymentMethodBadge';
import CashVarianceBadge from '../../components/cashflow/CashVarianceBadge';
import { fetchCashflowSummary } from '../../lib/cashflowApi';
import { money, todayISO } from './shared';

const RECEIVABLE_TYPE_LABELS = {
  guest_balance: 'Guest',
  ota_receivable: 'OTA',
  event_balance: 'Event',
  corporate_receivable: 'Company / group',
};

const PAYABLE_TYPE_LABELS = {
  supplier_bill: 'Supplier',
  utility_bill: 'Utility',
  payroll_liability: 'Payroll / gov',
  tax_liability: 'Tax',
  service_provider_bill: 'Service provider',
};

export default function CashflowLandingPage() {
  const [date, setDate] = useState(todayISO());
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState('');

  async function load(targetDate = date) {
    setError('');
    try {
      setSummary(await fetchCashflowSummary({ date: targetDate }));
    } catch (e) {
      setError(e.message || 'Failed to load cashflow summary.');
    }
  }

  useEffect(() => {
    load().catch(console.error);
  }, []);

  return (
    <div className="stack">
      <CashflowTabs />

      <section className="section">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h1>Cashflow</h1>
            <p className="muted">Money received, money spent, transfers, open balances, and periodic checks from one workspace.</p>
          </div>
          <div className="row wrap">
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            <button className="secondary" onClick={() => load(date).catch(console.error)}>Refresh</button>
          </div>
        </div>
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <CashflowSummaryCards cards={summary?.summary_cards || {}} />

      <section className="section">
        <h2>Quick Entry</h2>
        <QuickEntryButtons />
      </section>

      <div className="grid">
        <section className="section">
          <h2>Recent Transactions</h2>
          <table className="table dense-table">
            <thead><tr><th>Date</th><th>Flow</th><th>Account</th><th>Reason</th><th>Amount</th><th>Method</th></tr></thead>
            <tbody>
              {(summary?.recent_transactions || []).slice(0, 20).map((row) => (
                <tr key={row.id}>
                  <td>{row.transaction_date}</td>
                  <td>{row.direction === 'in' ? 'In' : row.direction === 'out' ? 'Out' : row.direction}</td>
                  <td>{row.financial_account_code} · {row.financial_account_name}</td>
                  <td>{row.category || '-'} / {row.subcategory || '-'}</td>
                  <td>P{money(row.amount)}</td>
                  <td><PaymentMethodBadge method={row.payment_method} /></td>
                </tr>
              ))}
              {!(summary?.recent_transactions || []).length && <tr><td colSpan="6" className="muted">No transactions yet.</td></tr>}
            </tbody>
          </table>
        </section>

        <section className="section">
          <h2>Accounts to Check</h2>
          <table className="table dense-table">
            <thead><tr><th>Code</th><th>Name</th><th>Type</th><th>Balance</th><th></th></tr></thead>
            <tbody>
              {(summary?.accounts_requiring_reconciliation || []).slice(0, 20).map((row) => (
                <tr key={row.id}>
                  <td>{row.code}</td>
                  <td>{row.name}</td>
                  <td>{row.account_type}</td>
                  <td>P{money(row.current_balance)}</td>
                  <td><Link className="button-link secondary-link" href={`/cashflow/daily-cash?account_id=${row.id}`}>Count Now</Link></td>
                </tr>
              ))}
              {!(summary?.accounts_requiring_reconciliation || []).length && <tr><td colSpan="5" className="muted">No accounts need checking for the selected date.</td></tr>}
            </tbody>
          </table>
        </section>
      </div>

      <div className="grid">
        <section className="section">
          <h2>Payments to Follow Up</h2>
          <table className="table dense-table">
            <thead><tr><th>Type</th><th>Counterparty</th><th>Due</th><th>Balance</th></tr></thead>
            <tbody>
              {(summary?.overdue_receivables || []).slice(0, 20).map((row) => (
                <tr key={row.id}>
                  <td>{RECEIVABLE_TYPE_LABELS[row.receivable_type] || row.receivable_type || '-'}</td>
                  <td>{row.counterparty_name}</td>
                  <td>{row.due_date || '-'}</td>
                  <td>P{money(row.balance_due)}</td>
                </tr>
              ))}
              {!(summary?.overdue_receivables || []).length && <tr><td colSpan="4" className="muted">No overdue payments to receive.</td></tr>}
            </tbody>
          </table>
        </section>

        <section className="section">
          <h2>Bills to Follow Up</h2>
          <table className="table dense-table">
            <thead><tr><th>Type</th><th>Supplier</th><th>Due</th><th>Balance</th></tr></thead>
            <tbody>
              {(summary?.overdue_payables || []).slice(0, 20).map((row) => (
                <tr key={row.id}>
                  <td>{PAYABLE_TYPE_LABELS[row.payable_type] || row.payable_type || '-'}</td>
                  <td>{row.supplier_name}</td>
                  <td>{row.due_date || '-'}</td>
                  <td>P{money(row.balance_due)}</td>
                </tr>
              ))}
              {!(summary?.overdue_payables || []).length && <tr><td colSpan="4" className="muted">No overdue bills.</td></tr>}
            </tbody>
          </table>
        </section>
      </div>

      <section className="section">
        <h2>Recent Count Differences</h2>
        <table className="table dense-table">
          <thead><tr><th>Date</th><th>Account</th><th>Shift</th><th>Difference</th><th>Status</th></tr></thead>
          <tbody>
            {(summary?.recent_variances || []).slice(0, 20).map((row) => (
              <tr key={row.id}>
                <td>{row.reconciliation_date}</td>
                <td>{row.financial_account_code} · {row.financial_account_name}</td>
                <td>{row.shift_name || 'day'}</td>
                <td><CashVarianceBadge variance={row.variance} /></td>
                <td>{row.status}</td>
              </tr>
            ))}
            {!(summary?.recent_variances || []).length && <tr><td colSpan="5" className="muted">No count differences.</td></tr>}
          </tbody>
        </table>
      </section>

      <section className="section">
        <h2>Posting Issues for Manager</h2>
        <table className="table dense-table">
          <thead><tr><th>Date</th><th>ID</th><th>Flow</th><th>Account</th><th>Amount</th></tr></thead>
          <tbody>
            {(summary?.journal_posting_failures || []).slice(0, 20).map((row) => (
              <tr key={row.id}>
                <td>{row.transaction_date}</td>
                <td>{row.id}</td>
                <td>{row.direction === 'in' ? 'In' : row.direction === 'out' ? 'Out' : row.direction}</td>
                <td>{row.financial_account_code}</td>
                <td>P{money(row.amount)}</td>
              </tr>
            ))}
            {!(summary?.journal_posting_failures || []).length && <tr><td colSpan="5" className="muted">No posting issues for the selected date.</td></tr>}
          </tbody>
        </table>
      </section>
    </div>
  );
}
