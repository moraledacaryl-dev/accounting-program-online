'use client';

import { useEffect, useState } from 'react';
import Drawer from '../../components/ui/Drawer';
import {
  acceptIntegrationReviewItem,
  fetchIntegrationReviewItems,
  fetchIntegrationReviewSummary,
  rejectIntegrationReviewItem,
  retryIntegrationReviewItem,
} from '../../lib/api';
import { fetchFinancialAccounts } from '../../lib/cashflowApi';

const effectLabels = {
  cash_in: 'Cash In',
  cash_out: 'Cash Out',
  settlement: 'Settlement',
  journal_only: 'Journal Only',
  receivable: 'Receivable',
  payable: 'Payable',
  folio_charge: 'Folio Charge',
  reference_only: 'Reference',
};

function formatMoney(item) {
  return Number(item.amount || 0).toLocaleString(undefined, {
    style: 'currency',
    currency: item.currency || 'PHP',
  });
}

function sourceInitials(value) {
  return String(value || '?').slice(0, 3);
}

export default function ReviewInboxPage() {
  const [items, setItems] = useState([]);
  const [summary, setSummary] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [filters, setFilters] = useState({ status: 'ready_for_review', source_app: '', financial_effect: '', q: '' });

  async function load() {
    setError('');
    try {
      const [rows, resultSummary, financialAccounts] = await Promise.all([
        fetchIntegrationReviewItems(filters),
        fetchIntegrationReviewSummary(),
        fetchFinancialAccounts(),
      ]);
      setItems(Array.isArray(rows) ? rows : []);
      setSummary(resultSummary);
      setAccounts(Array.isArray(financialAccounts) ? financialAccounts : []);
    } catch (err) {
      setError(err.message || 'Failed to load Review Inbox.');
    }
  }

  useEffect(() => {
    load();
  }, []);

  const counts = summary?.by_status || {};

  async function accept(item) {
    setBusy(true);
    try {
      await acceptIntegrationReviewItem(item.id, {
        account_id: item.proposed_account_id || accounts[0]?.id || null,
        category: 'Connected App',
      });
      setSelected(null);
      await load();
    } catch (err) {
      setError(err.message || 'Acceptance failed.');
    } finally {
      setBusy(false);
    }
  }

  async function reject(item) {
    setBusy(true);
    try {
      await rejectIntegrationReviewItem(item.id, { reason: 'Rejected during Accounting review' });
      setSelected(null);
      await load();
    } catch (err) {
      setError(err.message || 'Rejection failed.');
    } finally {
      setBusy(false);
    }
  }

  async function retry(item) {
    setBusy(true);
    try {
      await retryIntegrationReviewItem(item.id, {});
      setSelected(null);
      await load();
    } catch (err) {
      setError(err.message || 'Retry failed.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack review-inbox-page">
      <section className="section page-header review-inbox-hero">
        <div>
          <div className="eyebrow">Connected-app financial intake</div>
          <h1>Review Inbox</h1>
          <p className="muted">
            Review each external financial event once. Cash items enter Cash & Treasury; non-cash items become journals,
            payables, receivables, folio links, or accounting references.
          </p>
        </div>
        <button type="button" onClick={load}>Refresh inbox</button>
      </section>

      <section className="metric-grid">
        <div className="metric-card"><span>Needs review</span><strong>{summary?.needs_review || 0}</strong></div>
        <div className="metric-card"><span>Accepted</span><strong>{counts.accepted || 0}</strong></div>
        <div className="metric-card"><span>Failed validation</span><strong>{counts.validation_failed || 0}</strong></div>
        <div className="metric-card"><span>Rejected</span><strong>{counts.rejected || 0}</strong></div>
      </section>

      <section className="section">
        <div className="section-title-row">
          <div>
            <h2>Financial intake queue</h2>
            <p className="small muted">Filter by source, accounting effect, or processing status.</p>
          </div>
        </div>

        <div className="review-inbox-toolbar">
          <select aria-label="Status" value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value })}>
            <option value="">All statuses</option>
            <option value="ready_for_review">Needs review</option>
            <option value="accepted">Accepted</option>
            <option value="validation_failed">Failed validation</option>
            <option value="rejected">Rejected</option>
          </select>
          <select aria-label="Source application" value={filters.source_app} onChange={(event) => setFilters({ ...filters, source_app: event.target.value })}>
            <option value="">All apps</option>
            <option value="pos">POS</option>
            <option value="inventory">Inventory</option>
            <option value="staff">Staff & Payroll</option>
            <option value="beds24">Beds24</option>
            <option value="operations">Operations</option>
          </select>
          <select aria-label="Financial effect" value={filters.financial_effect} onChange={(event) => setFilters({ ...filters, financial_effect: event.target.value })}>
            <option value="">All effects</option>
            {Object.entries(effectLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select>
          <input aria-label="Search review items" placeholder="Search source ID or payload" value={filters.q} onChange={(event) => setFilters({ ...filters, q: event.target.value })} />
          <button type="button" onClick={load}>Apply filters</button>
        </div>

        {error ? <p className="error-text">{error}</p> : null}

        <div className="table-wrap">
          <table className="table review-inbox-table">
            <thead>
              <tr><th>Received</th><th>Source</th><th>Financial effect</th><th>Amount</th><th>Suggested result</th><th>Status</th><th>Action</th></tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>{item.created_at?.slice(0, 16).replace('T', ' ') || '-'}</td>
                  <td>
                    <div className="review-source">
                      <span className="review-source__mark">{sourceInitials(item.source_app)}</span>
                      <span><strong>{item.source_app}</strong><span className="small muted" style={{ display: 'block' }}>{item.source_event_id}</span></span>
                    </div>
                  </td>
                  <td><span className="badge">{effectLabels[item.financial_effect] || item.financial_effect}</span></td>
                  <td className="review-amount">{formatMoney(item)}</td>
                  <td>{item.proposed_account_name || (item.accepted_journal_entry_id && 'Journal') || (item.accepted_receivable_id && 'Receivable') || (item.accepted_payable_id && 'Payable') || 'Review required'}</td>
                  <td><span className={`review-status review-status--${item.status}`}>{String(item.status || '').replaceAll('_', ' ')}</span></td>
                  <td><button type="button" className="secondary" onClick={() => setSelected(item)}>Review</button></td>
                </tr>
              ))}
              {!items.length ? <tr><td colSpan="7" className="muted">No items match the filters.</td></tr> : null}
            </tbody>
          </table>
        </div>
      </section>

      <Drawer
        open={!!selected}
        onClose={() => setSelected(null)}
        title={selected?.source_event_id || 'Review item'}
        description={selected ? `Review the ${selected.source_app} event before it enters accounting.` : ''}
        size="large"
        footer={selected ? (
          <div className="row wrap">
            {selected.status === 'ready_for_review' ? (
              <>
                <button type="button" disabled={busy} onClick={() => accept(selected)}>{busy ? 'Processing…' : 'Accept into accounting'}</button>
                <button type="button" className="danger" disabled={busy} onClick={() => reject(selected)}>Reject</button>
              </>
            ) : null}
            {['validation_failed', 'rejected'].includes(selected.status) ? <button type="button" disabled={busy} onClick={() => retry(selected)}>Retry processing</button> : null}
          </div>
        ) : null}
      >
        {selected ? (
          <div className="stack">
            <div className="review-detail-summary">
              <div>
                <strong>{effectLabels[selected.financial_effect] || selected.financial_effect}</strong>
                <span className="small muted">Entity: {selected.source_entity_type} {selected.source_entity_id || ''}</span>
              </div>
              <div className="review-detail-amount">{formatMoney(selected)}</div>
            </div>

            <div className="review-routing-card">
              <strong>Acceptance result</strong>
              <p className="small muted">
                Cash and settlement events create one Money Transaction. Journal-only events create a journal entry.
                Receivable and payable events create an open balance. Folio and reference effects retain their source link.
              </p>
              {['cash_in', 'cash_out', 'settlement'].includes(selected.financial_effect) ? (
                <label>
                  Financial account
                  <select value={selected.proposed_account_id || ''} onChange={(event) => setSelected({ ...selected, proposed_account_id: Number(event.target.value) })}>
                    <option value="">Select account</option>
                    {accounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
                  </select>
                </label>
              ) : null}
            </div>

            <div>
              <strong>Source payload</strong>
              <pre className="review-payload">{JSON.stringify(selected.payload || {}, null, 2)}</pre>
            </div>
          </div>
        ) : null}
      </Drawer>
    </div>
  );
}
