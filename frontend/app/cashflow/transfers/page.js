'use client';

import { useEffect, useState } from 'react';
import CashflowTabs from '../../../components/cashflow/CashflowTabs';
import TransferForm from '../../../components/cashflow/TransferForm';
import ConfirmActionModal from '../../../components/ConfirmActionModal';
import {
  approveTransfer,
  cancelTransfer,
  createTransfer,
  deleteTransfer,
  fetchFinancialAccounts,
  fetchTransfers,
  reverseTransfer,
  updateTransfer,
} from '../../../lib/cashflowApi';
import { useCurrentUser } from '../../../lib/useCurrentUser';
import { money, todayISO } from '../shared';

const EMPTY_FORM = {
  transfer_date: todayISO(),
  from_account_id: '',
  to_account_id: '',
  amount: '',
  reference_no: '',
  notes: '',
  auto_post_accounting: false,
};

const STATUS_LABELS = {
  draft: 'Draft',
  approved: 'Approved',
  cancelled: 'Cancelled',
  reversed: 'Reversed',
  posted: 'Posted',
};

export default function TransfersPage() {
  const { can } = useCurrentUser();
  const [accounts, setAccounts] = useState([]);
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [pendingAction, setPendingAction] = useState(null);

  async function load() {
    const [accountRows, transferRows] = await Promise.all([
      fetchFinancialAccounts({ only_active: true }),
      fetchTransfers({ limit: 300 }),
    ]);
    setAccounts(Array.isArray(accountRows) ? accountRows : []);
    setRows(Array.isArray(transferRows) ? transferRows : []);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || 'Failed to load transfers.'));
  }, []);

  async function submit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      const payload = {
        transfer_date: form.transfer_date,
        from_account_id: Number(form.from_account_id),
        to_account_id: Number(form.to_account_id),
        amount: Number(form.amount || 0),
        reference_no: form.reference_no || null,
        notes: form.notes || null,
        auto_post_accounting: !!form.auto_post_accounting,
      };
      if (editingId) {
        await updateTransfer(editingId, payload);
        setNotice('Transfer updated.');
      } else {
        await createTransfer(payload);
        setNotice('Transfer saved.');
      }
      setForm({ ...EMPTY_FORM, transfer_date: form.transfer_date });
      setEditingId(null);
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save transfer.');
    }
  }

  function startEdit(row) {
    setEditingId(row.id);
    setForm({
      transfer_date: row.transfer_date || todayISO(),
      from_account_id: row.from_account_id ? String(row.from_account_id) : '',
      to_account_id: row.to_account_id ? String(row.to_account_id) : '',
      amount: row.amount ?? '',
      reference_no: row.reference_no || '',
      notes: row.notes || '',
      auto_post_accounting: false,
    });
  }

  async function confirmPendingAction(reason) {
    const action = pendingAction;
    if (!action) return;
    setError('');
    setNotice('');
    try {
      await action.work(reason);
      setNotice(action.successMessage);
      await load();
    } catch (err) {
      setError(err.message || 'Action failed.');
      throw err;
    }
  }

  return (
    <div className="stack">
      <CashflowTabs />

      <section className="section">
        <h1>Transfers</h1>
        <p className="muted">Move money between drawers, safes, banks, petty cash, or e-wallets.</p>
        {editingId ? <p className="small muted">Editing transfer #{editingId}</p> : null}
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <section className="section">
        <TransferForm accounts={accounts} form={form} setForm={setForm} onSubmit={submit} />
        {editingId && (
          <button
            type="button"
            className="secondary"
            onClick={() => {
              setEditingId(null);
              setForm({ ...EMPTY_FORM, transfer_date: todayISO() });
            }}
          >
            Cancel Edit
          </button>
        )}
      </section>

      <section className="section">
        <h2>Recent Transfers</h2>
        <table className="table">
          <thead><tr><th>Date</th><th>From</th><th>To</th><th>Amount</th><th>Reference</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.transfer_date}</td>
                <td>{row.from_account_code} · {row.from_account_name}</td>
                <td>{row.to_account_code} · {row.to_account_name}</td>
                <td>P{money(row.amount)}</td>
                <td>{row.reference_no || '-'}</td>
                <td>{STATUS_LABELS[row.status] || row.status || '-'}</td>
                <td className="row wrap">
                  {can('cashflow.transfers') && (
                    <>
                      <button type="button" className="secondary" onClick={() => startEdit(row)}>Edit</button>
                      <details className="row-actions-more">
                        <summary>More</summary>
                        <button type="button" className="secondary" onClick={() => setPendingAction({ title: `Approve transfer #${row.id}?`, description: 'Confirm the source, destination, and amount before changing both balances.', confirmLabel: 'Approve transfer', tone: 'normal', work: () => approveTransfer(row.id, {}), successMessage: `Transfer #${row.id} approved.` })}>Approve</button>
                        <button type="button" className="danger" onClick={() => setPendingAction({ title: `Cancel transfer #${row.id}?`, description: 'Record why the transfer should be cancelled.', confirmLabel: 'Cancel transfer', reasonRequired: true, work: (reason) => cancelTransfer(row.id, { reason }), successMessage: `Transfer #${row.id} cancelled.` })}>Cancel</button>
                        <button type="button" className="danger" onClick={() => setPendingAction({ title: `Reverse transfer #${row.id}?`, description: 'This adjusts both balances and remains visible in the audit trail.', confirmLabel: 'Reverse transfer', reasonRequired: true, work: (reason) => reverseTransfer(row.id, { reason }), successMessage: `Transfer #${row.id} reversed.` })}>Reverse</button>
                        <button type="button" className="danger" onClick={() => setPendingAction({ title: `Delete draft transfer #${row.id}?`, description: 'Only unposted drafts can be deleted. Posted transfers must be reversed.', confirmLabel: 'Delete draft', work: () => deleteTransfer(row.id), successMessage: `Transfer #${row.id} deleted.` })}>Delete</button>
                      </details>
                    </>
                  )}
                </td>
              </tr>
            ))}
            {!rows.length && <tr><td colSpan="7" className="muted">No transfers yet.</td></tr>}
          </tbody>
        </table>
      </section>
      <ConfirmActionModal
        open={!!pendingAction}
        title={pendingAction?.title}
        description={pendingAction?.description}
        confirmLabel={pendingAction?.confirmLabel}
        tone={pendingAction?.tone || 'danger'}
        reasonRequired={!!pendingAction?.reasonRequired}
        onClose={() => setPendingAction(null)}
        onConfirm={confirmPendingAction}
      />
    </div>
  );
}
