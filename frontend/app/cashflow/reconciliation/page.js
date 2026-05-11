'use client';

import { Suspense, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import CashflowTabs from '../../../components/cashflow/CashflowTabs';
import ReconciliationTable from '../../../components/cashflow/ReconciliationTable';
import ReceivablesTable from '../../../components/cashflow/ReceivablesTable';
import PayablesTable from '../../../components/cashflow/PayablesTable';
import { fetchFinancialAccounts, fetchPayables, fetchReconciliations, fetchReceivables } from '../../../lib/cashflowApi';
import { fetchPayouts } from '../../../lib/api';
import { money } from '../shared';

const TABS = ['cash', 'bank', 'ota', 'receivables', 'payables'];
const TAB_LABELS = {
  cash: 'Cash',
  bank: 'Bank',
  ota: 'OTA',
  receivables: 'To Receive',
  payables: 'To Pay',
};

function ReconciliationContent() {
  const searchParams = useSearchParams();
  const [tab, setTab] = useState(searchParams.get('tab') || 'cash');
  const [accounts, setAccounts] = useState([]);
  const [reconRows, setReconRows] = useState([]);
  const [receivables, setReceivables] = useState([]);
  const [payables, setPayables] = useState([]);
  const [payouts, setPayouts] = useState([]);
  const [error, setError] = useState('');

  async function load() {
    const [accountRows, reconData, receivableRows, payableRows, payoutRows] = await Promise.all([
      fetchFinancialAccounts({ only_active: true }),
      fetchReconciliations({ limit: 400 }),
      fetchReceivables({ limit: 400 }),
      fetchPayables({ limit: 400 }),
      fetchPayouts(),
    ]);
    setAccounts(Array.isArray(accountRows) ? accountRows : []);
    setReconRows(Array.isArray(reconData) ? reconData : []);
    setReceivables(Array.isArray(receivableRows) ? receivableRows : []);
    setPayables(Array.isArray(payableRows) ? payableRows : []);
    setPayouts(Array.isArray(payoutRows) ? payoutRows : []);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || 'Failed to load periodic check data.'));
  }, []);

  useEffect(() => {
    const requested = searchParams.get('tab');
    if (requested && TABS.includes(requested)) setTab(requested);
  }, [searchParams]);

  const accountTypeById = useMemo(() => Object.fromEntries(accounts.map((a) => [a.id, a.account_type])), [accounts]);

  const cashRows = useMemo(() => reconRows.filter((r) => {
    const t = accountTypeById[r.financial_account_id];
    return t && t !== 'bank';
  }), [reconRows, accountTypeById]);

  const bankRows = useMemo(() => reconRows.filter((r) => accountTypeById[r.financial_account_id] === 'bank'), [reconRows, accountTypeById]);

  const openReceivables = useMemo(() => receivables.filter((r) => Number(r.balance_due || 0) > 0), [receivables]);
  const openPayables = useMemo(() => payables.filter((p) => Number(p.balance_due || 0) > 0), [payables]);

  return (
    <div className="stack">
      <CashflowTabs />

      <section className="section">
        <h1>Periodic Checks</h1>
        <p className="muted">Review cash, bank, OTA, payments to receive, and bills to pay when needed. Bank checks do not have to be daily.</p>
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <section className="section">
        <div className="tabs" style={{ marginTop: 0 }}>
          {TABS.map((name) => (
            <button key={name} type="button" className={tab === name ? 'tab active' : 'tab'} onClick={() => setTab(name)}>
              {TAB_LABELS[name] || name}
            </button>
          ))}
        </div>
      </section>

      {tab === 'cash' && (
        <section className="section">
          <h2>Cash Checks</h2>
          <ReconciliationTable rows={cashRows} />
        </section>
      )}

      {tab === 'bank' && (
        <section className="section">
          <h2>Bank Checks</h2>
          <ReconciliationTable rows={bankRows} />
        </section>
      )}

      {tab === 'ota' && (
        <section className="section">
          <h2>OTA Checks</h2>
          <table className="table">
            <thead><tr><th>Channel</th><th>Booking Ref</th><th>Expected</th><th>Actual</th><th>Variance</th><th>Status</th></tr></thead>
            <tbody>
              {payouts.map((row) => {
                const gross = Number(row.net_amount || 0);
                const actual = Number(row.actual_received_amount || row.net_amount || 0);
                const variance = actual - gross;
                return (
                  <tr key={row.id}>
                    <td>{row.channel}</td>
                    <td>{row.booking_ref || '-'}</td>
                    <td>P{money(gross)}</td>
                    <td>P{money(actual)}</td>
                    <td>P{money(variance)}</td>
                    <td>{row.status}</td>
                  </tr>
                );
              })}
              {!payouts.length && <tr><td colSpan="6" className="muted">No OTA payout rows.</td></tr>}
            </tbody>
          </table>
        </section>
      )}

      {tab === 'receivables' && (
        <section className="section">
          <h2>Payments to Follow Up</h2>
          <ReceivablesTable rows={openReceivables} />
        </section>
      )}

      {tab === 'payables' && (
        <section className="section">
          <h2>Bills to Follow Up</h2>
          <PayablesTable rows={openPayables} />
        </section>
      )}
    </div>
  );
}

export default function ReconciliationPage() {
  return (
    <Suspense fallback={<div className="stack"><CashflowTabs /></div>}>
      <ReconciliationContent />
    </Suspense>
  );
}
