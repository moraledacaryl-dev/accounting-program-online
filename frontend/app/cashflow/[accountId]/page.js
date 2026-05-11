'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import CashflowTabs from '../../../components/cashflow/CashflowTabs';
import AccountLedgerTable from '../../../components/cashflow/AccountLedgerTable';
import { fetchAccountLedger } from '../../../lib/cashflowApi';
import { money } from '../shared';

export default function AccountLedgerPage() {
  const params = useParams();
  const accountId = params?.accountId;
  const [ledger, setLedger] = useState(null);
  const [form, setForm] = useState({ start_date: '', end_date: '', include_reconciliations: true });
  const [error, setError] = useState('');

  async function load() {
    if (!accountId) return;
    setError('');
    try {
      const data = await fetchAccountLedger(accountId, {
        start_date: form.start_date,
        end_date: form.end_date,
        include_reconciliations: form.include_reconciliations,
        limit: 1000,
      });
      setLedger(data);
    } catch (e) {
      setError(e.message || 'Failed to load account history.');
    }
  }

  useEffect(() => {
    load().catch(console.error);
  }, [accountId]);

  return (
    <div className="stack">
      <CashflowTabs />

      <section className="section">
        <h1>Account History</h1>
        <p className="muted">Detailed running history for one drawer, bank, safe, petty cash, or e-wallet account.</p>
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <section className="section">
        <div className="form-grid">
          <label>
            Start Date
            <input type="date" value={form.start_date} onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))} />
          </label>
          <label>
            End Date
            <input type="date" value={form.end_date} onChange={(e) => setForm((f) => ({ ...f, end_date: e.target.value }))} />
          </label>
          <label>
            Include Counts / Checks
            <select value={String(form.include_reconciliations)} onChange={(e) => setForm((f) => ({ ...f, include_reconciliations: e.target.value === 'true' }))}>
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          </label>
        </div>
        <div className="row wrap">
          <button onClick={() => load().catch(console.error)}>Refresh History</button>
          <button className="secondary" onClick={() => {
            setForm({ start_date: '', end_date: '', include_reconciliations: true });
            setTimeout(() => load().catch(console.error), 0);
          }}>Reset Filters</button>
        </div>
      </section>

      {ledger && (
        <>
          <section className="section">
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <div>
                <h2>{ledger.account?.code} · {ledger.account?.name}</h2>
                <p className="small muted">Type: {ledger.account?.account_type} / {ledger.account?.subtype || '-'}</p>
              </div>
              <div className="row wrap">
                <span className="badge">Opening P{money(ledger.opening_balance)}</span>
                <span className="badge">Closing P{money(ledger.closing_balance)}</span>
              </div>
            </div>
          </section>

          <section className="section">
            <AccountLedgerTable rows={ledger.rows || []} />
          </section>
        </>
      )}
    </div>
  );
}
