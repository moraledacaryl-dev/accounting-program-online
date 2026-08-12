'use client';

import { useEffect, useState } from 'react';
import {
  approvePayrollIntegrationReceipt,
  fetchPayrollIntegrationReceipt,
  fetchPayrollIntegrationReceipts,
  postPayrollIntegrationReceipt,
  rejectPayrollIntegrationReceipt,
} from '../../../lib/api';
import { useConfirmAction } from '../../../components/ConfirmActionProvider';

const tabs = ['For Review', 'Ready to Post', 'Posted', 'Rejected', 'Errors', 'Already Applied'];

function money(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function PayrollIntegrationReviewPage() {
  const confirmAction = useConfirmAction();
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
        const confirmed = await confirmAction({
          title: 'Post this reviewed payroll import?',
          description: 'Posting applies the reviewed payroll receipt to Accounting. Continue only after the journal preview and source payload have been checked.',
          confirmLabel: 'Post payroll',
          tone: 'normal',
        });
        if (!confirmed) return;
        await postPayrollIntegrationReceipt(row.id);
      }
      if (kind === 'reject') {
        const reason = await confirmAction({
          title: 'Reject this payroll import?',
          description: 'Enter the rejection reason so the source record has an actionable audit trail.',
          confirmLabel: 'Reject import',
          tone: 'danger',
          reasonRequired: true,
        });
        if (!reason || reason === true) return;
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
    <div className="stack payroll-integration-page">
      <section className="section payroll-integration-header">
        <div className="payroll-integration-header__copy">
          <div className="eyebrow">Staff & Payroll intake</div>
          <h1>Payroll Review Queue</h1>
          <p className="muted">Review imported payroll events, verify the journal preview, then approve and post only the records that are ready for Accounting.</p>
        </div>
        <div className="payroll-integration-header__actions">
          <span className="badge">{rows.length} in {status.toLowerCase()}</span>
          <button className="secondary" type="button" onClick={() => load()}>Refresh</button>
        </div>
      </section>

      {error ? <div className="error-text">{error}</div> : null}

      <section className="section payroll-integration-workspace">
        <div className="payroll-integration-tabs" role="tablist" aria-label="Payroll review status">
          {tabs.map((tab) => (
            <button
              key={tab}
              type="button"
              role="tab"
              aria-selected={status === tab}
              className={`payroll-integration-tab ${status === tab ? 'active' : ''}`}
              onClick={() => setStatus(tab)}
            >
              {tab}
            </button>
          ))}
        </div>

        <div className="table-wrap payroll-integration-table-wrap">
          <table className="table payroll-integration-table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Event</th>
                <th>External ID</th>
                <th className="numeric">Amount</th>
                <th>Status</th>
                <th>Journal preview</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const preview = (row.outcome?.journal_preview || []).slice(0, 3);
                return (
                  <tr key={row.id}>
                    <td><strong>{row.external_source || '-'}</strong></td>
                    <td>{row.event_type || '-'}</td>
                    <td className="payroll-external-id">{row.external_id || '-'}</td>
                    <td className="numeric payroll-amount">PHP {money(row.amount)}</td>
                    <td><span className="badge">{row.status}</span></td>
                    <td className="payroll-preview-cell">
                      <div className="payroll-preview-lines">
                        {preview.length ? preview.map((line, idx) => (
                          <div key={idx} className="payroll-preview-line">
                            <span>{line.debit_account} → {line.credit_account}</span>
                            <strong>PHP {money(line.amount)}</strong>
                          </div>
                        )) : <span className="small muted">No journal preview supplied.</span>}
                      </div>
                      <details className="payroll-payload" open={openPayloadId === row.id} onToggle={(event) => togglePayload(event, row)}>
                        <summary>Source payload</summary>
                        <pre>{JSON.stringify(payloads[row.id] || {}, null, 2)}</pre>
                      </details>
                    </td>
                    <td>
                      <div className="toolbar tight payroll-row-actions">
                        {row.status === 'For Review' ? <button className="small secondary" type="button" onClick={() => act('approve', row)}>Approve</button> : null}
                        {['For Review', 'Ready to Post'].includes(row.status) ? <button className="small" type="button" onClick={() => act('post', row)}>Post</button> : null}
                        {!['Posted', 'Rejected'].includes(row.status) ? <button className="small danger" type="button" onClick={() => act('reject', row)}>Reject</button> : null}
                      </div>
                    </td>
                  </tr>
                );
              })}
              {!rows.length ? <tr><td colSpan="7" className="empty">No receipts in this queue.</td></tr> : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
