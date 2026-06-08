'use client';

import { useEffect, useState } from 'react';
import {
  approvePayrollIntegrationReceipt,
  fetchPayrollIntegrationReceipt,
  fetchPayrollIntegrationReceipts,
  postPayrollIntegrationReceipt,
  rejectPayrollIntegrationReceipt,
} from '../../../lib/api';

const tabs = ['For Review', 'Ready to Post', 'Posted', 'Rejected', 'Errors', 'Already Applied'];

function money(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function PayrollIntegrationReviewPage() {
  const [status, setStatus] = useState('For Review');
  const [rows, setRows] = useState([]);
  const [openPayloadId, setOpenPayloadId] = useState(null);
  const [payloads, setPayloads] = useState({});
  const [error, setError] = useState('');

  async function load(nextStatus = status) {
    setError('');
    try {
      setRows(await fetchPayrollIntegrationReceipts(nextStatus));
    } catch (err) {
      setError(err.message || 'Could not load payroll receipts.');
    }
  }

  useEffect(() => { load(status); }, [status]);

  async function act(kind, row) {
    setError('');
    try {
      if (kind === 'approve') await approvePayrollIntegrationReceipt(row.id);
      if (kind === 'post') {
        if (!window.confirm('Post this reviewed payroll import?')) return;
        await postPayrollIntegrationReceipt(row.id);
      }
      if (kind === 'reject') {
        const reason = window.prompt('Rejection reason');
        if (!reason) return;
        await rejectPayrollIntegrationReceipt(row.id, reason);
      }
      await load();
    } catch (err) {
      setError(err.message || 'Action failed.');
    }
  }

  async function togglePayload(event, row) {
    const isOpen = event.currentTarget.open;
    setOpenPayloadId(isOpen ? row.id : null);
    if (isOpen && !payloads[row.id]) {
      try {
        const detail = await fetchPayrollIntegrationReceipt(row.id);
        setPayloads((prev) => ({ ...prev, [row.id]: detail.payload || detail.outcome || {} }));
      } catch (err) {
        setError(err.message || 'Could not load raw payload.');
      }
    }
  }

  return (
    <main>
      <section className="section">
        <div>
          <h1>Payroll Review Queue</h1>
          <p className="muted">Imported Staff/Payroll records stay review-first until Accounting approves and posts them.</p>
        </div>
        <button className="btn secondary" onClick={() => load()}>Refresh</button>
      </section>
      {error ? <div className="error-text">{error}</div> : null}
      <div className="tabs">
        {tabs.map((tab) => (
          <button key={tab} className={`tab ${status === tab ? 'active' : ''}`} onClick={() => setStatus(tab)}>{tab}</button>
        ))}
      </div>
      <div className="table-wrap section">
        <table className="table">
          <thead>
            <tr>
              <th>Source</th>
              <th>Event</th>
              <th>External ID</th>
              <th>Amount</th>
              <th>Status</th>
              <th>Preview</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.external_source}</td>
                <td>{row.event_type}</td>
                <td>{row.external_id}</td>
                <td>PHP {money(row.amount)}</td>
                <td><span className="badge">{row.status}</span></td>
                <td>
                  {(row.outcome?.journal_preview || []).slice(0, 4).map((line, idx) => (
                    <div key={idx} className="muted">{line.debit_account} / {line.credit_account}: PHP {money(line.amount)}</div>
                  ))}
                  <details open={openPayloadId === row.id} onToggle={(event) => togglePayload(event, row)}>
                    <summary>Raw payload</summary>
                    <pre>{JSON.stringify(payloads[row.id] || {}, null, 2)}</pre>
                  </details>
                </td>
                <td>
                  <div className="toolbar tight">
                    {row.status === 'For Review' ? <button className="btn small" onClick={() => act('approve', row)}>Approve</button> : null}
                    {['For Review', 'Ready to Post'].includes(row.status) ? <button className="btn small" onClick={() => act('post', row)}>Post</button> : null}
                    {!['Posted', 'Rejected'].includes(row.status) ? <button className="btn small secondary" onClick={() => act('reject', row)}>Reject</button> : null}
                  </div>
                </td>
              </tr>
            ))}
            {!rows.length ? <tr><td colSpan="7" className="empty">No receipts in this tab.</td></tr> : null}
          </tbody>
        </table>
      </div>
    </main>
  );
}
