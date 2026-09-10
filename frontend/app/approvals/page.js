'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import {
  approveRecord,
  fetchJournalEntries,
  fetchPayrollPeriods,
  fetchPurchaseOrders,
  fetchPurchaseRequests,
  getModuleRecords,
  lockJournalEntry,
  postPayrollPeriod,
  updatePayrollPeriod,
  updatePurchaseOrderStatus,
  updatePurchaseRequestStatus,
} from '../../lib/api';
import {
  approveMoneyTransaction,
  approveReconciliation,
  cancelMoneyTransaction,
  closeReconciliation,
  fetchMoneyTransactions,
  fetchReconciliations,
  reverseMoneyTransaction,
  reverseReconciliation,
} from '../../lib/cashflowApi';
import { useCurrentUser } from '../../lib/useCurrentUser';
import ConfirmActionModal from '../../components/ConfirmActionModal';

const RECORD_MODULES = [
  'rooms', 'restaurant', 'breakfast', 'cafe', 'bar', 'events', 'inventory', 'procurement',
  'internal', 'channel_ota', 'reconciliation', 'payroll', 'assets', 'utilities', 'finance', 'other_income',
];

const RECORD_READ_REQUIREMENTS = {
  rooms: ['bookings.view', 'guests.view', 'folios.view', 'room_setup.view'],
  restaurant: ['restaurant.view', 'menu.view'],
  breakfast: ['restaurant.view'],
  cafe: ['restaurant.view'],
  bar: ['restaurant.view'],
  events: ['events.view'],
  inventory: ['inventory.view'],
  procurement: ['inventory.view', 'suppliers.view', 'purchase_requests.view', 'purchase_orders.view', 'receiving.view'],
  internal: ['dashboard.view'],
  channel_ota: ['bookings.view'],
  reconciliation: ['cashflow.view'],
  payroll: ['payroll_periods.view'],
  assets: ['assets.view'],
  utilities: ['cashflow.view'],
  finance: ['cashflow.view', 'journals.view', 'reports.view'],
  other_income: ['cashflow.view'],
};

const RECORD_WRITE_REQUIREMENTS = {
  rooms: ['bookings.edit', 'folios.manage'],
  restaurant: ['menu.manage'], breakfast: ['menu.manage'], cafe: ['menu.manage'], bar: ['menu.manage'],
  events: ['bookings.edit'], inventory: ['inventory.manage'],
  procurement: ['purchase_requests.create', 'purchase_orders.create'],
  payroll: ['payroll_periods.manage'], assets: ['assets.manage'],
  channel_ota: ['cashflow.money_in'], reconciliation: ['cashflow.reconcile'],
  finance: ['journals.post'], utilities: ['cashflow.money_out'], other_income: ['cashflow.money_in'], internal: ['journals.post'],
};

const TABS = ['records', 'procurement', 'cashflow', 'payroll', 'journals', 'reconciliations'];
const TAB_LABELS = { records: 'Records', procurement: 'Procurement', cashflow: 'Money Transactions', payroll: 'Payroll', journals: 'Journal Entries', reconciliations: 'Reconciliations' };
const PENDING_RECORD_STATUSES = new Set(['draft', 'pending_review']);

function currency(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function moneyTxIsActionable(row) {
  const status = String(row.status || '').toLowerCase();
  return !['cancelled', 'reversed'].includes(status);
}

function reconIsActionable(row) {
  return !['reversed'].includes(String(row.status || '').toLowerCase());
}

export default function ApprovalsPage() {
  const { can, loaded } = useCurrentUser();
  const [tab, setTab] = useState('records');
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [pendingAction, setPendingAction] = useState(null);
  const [recordRows, setRecordRows] = useState([]);
  const [prRows, setPrRows] = useState([]);
  const [poRows, setPoRows] = useState([]);
  const [moneyRows, setMoneyRows] = useState([]);
  const [periodRows, setPeriodRows] = useState([]);
  const [journalRows, setJournalRows] = useState([]);
  const [reconRows, setReconRows] = useState([]);

  const readableRecordModules = useMemo(() => RECORD_MODULES.filter((slug) => (RECORD_READ_REQUIREMENTS[slug] || []).some((key) => can(key))), [can]);
  const visibleTabs = useMemo(() => TABS.filter((name) => {
    if (name === 'records') return readableRecordModules.length > 0;
    if (name === 'procurement') return can('purchase_requests.view') || can('purchase_orders.view');
    if (name === 'cashflow') return can('cashflow.view');
    if (name === 'payroll') return can('payroll_periods.view');
    if (name === 'journals') return can('journals.view');
    if (name === 'reconciliations') return can('cashflow.view');
    return false;
  }), [can, readableRecordModules]);

  useEffect(() => {
    if (!loaded || !visibleTabs.length) return;
    if (!visibleTabs.includes(tab)) setTab(visibleTabs[0]);
  }, [loaded, tab, visibleTabs]);

  async function load() {
    if (!loaded) return;
    setLoading(true);
    setLoadError('');
    try {
      const recordPromises = readableRecordModules.map((slug) => getModuleRecords(slug).then((rows) => ({ slug, rows })));
      const [recordBatches, prData, poData, moneyData, periodData, journalsData, reconData] = await Promise.all([
        Promise.all(recordPromises),
        can('purchase_requests.view') ? fetchPurchaseRequests({}) : Promise.resolve([]),
        can('purchase_orders.view') ? fetchPurchaseOrders({}) : Promise.resolve([]),
        can('cashflow.view') ? fetchMoneyTransactions({ limit: 400 }) : Promise.resolve([]),
        can('payroll_periods.view') ? fetchPayrollPeriods({ limit: 200 }) : Promise.resolve([]),
        can('journals.view') ? fetchJournalEntries() : Promise.resolve([]),
        can('cashflow.view') ? fetchReconciliations({ limit: 300 }) : Promise.resolve([]),
      ]);

      const mergedRecords = [];
      recordBatches.forEach(({ slug, rows }) => {
        for (const row of (Array.isArray(rows) ? rows : [])) {
          if (PENDING_RECORD_STATUSES.has(String(row.workflow_status || '').toLowerCase())) mergedRecords.push({ ...row, module_slug: row.module_slug || slug });
        }
      });
      setRecordRows(mergedRecords.sort((a, b) => Number(b.id || 0) - Number(a.id || 0)));
      setPrRows((Array.isArray(prData) ? prData : []).filter((row) => String(row.status || '').toLowerCase() === 'submitted'));
      setPoRows((Array.isArray(poData) ? poData : []).filter((row) => ['draft', 'issued'].includes(String(row.status || '').toLowerCase())));
      setMoneyRows((Array.isArray(moneyData) ? moneyData : []).filter((row) => ['draft', 'pending_approval', 'approved', 'posted'].includes(String(row.status || '').toLowerCase())));
      setPeriodRows((Array.isArray(periodData) ? periodData : []).filter((row) => ['draft', 'reviewed'].includes(String(row.status || '').toLowerCase())));
      setJournalRows((Array.isArray(journalsData) ? journalsData : []).filter((row) => String(row.status || '').toLowerCase() === 'draft' && !row.locked));
      setReconRows((Array.isArray(reconData) ? reconData : []).filter((row) => ['counted', 'reviewed', 'closed'].includes(String(row.status || '').toLowerCase())));
    } catch (err) {
      setLoadError(err.message || 'Failed to load approval queues.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!loaded) return;
    load().catch((err) => setLoadError(err.message || 'Failed to load approval queues.'));
  }, [loaded]);

  const counts = useMemo(() => ({ records: recordRows.length, procurement: prRows.length + poRows.length, cashflow: moneyRows.length, payroll: periodRows.length, journals: journalRows.length, reconciliations: reconRows.length }), [recordRows, prRows, poRows, moneyRows, periodRows, journalRows, reconRows]);
  const canApproveRecord = (row) => can('approvals.act') && (RECORD_WRITE_REQUIREMENTS[row.module_slug] || []).some((key) => can(key));
  const canActOnMoneyRow = (row) => row.direction === 'in' ? can('cashflow.money_in') : row.direction === 'out' ? can('cashflow.money_out') : false;

  async function runAction(work, successMessage) {
    setError(''); setNotice('');
    try { await work(); setNotice(successMessage); await load(); }
    catch (err) { setError(err.message || 'Action failed.'); }
  }

  async function confirmPendingAction(reason) {
    const action = pendingAction;
    if (!action) return;
    setError(''); setNotice('');
    try { await action.work(reason); setNotice(action.successMessage); await load(); }
    catch (err) { setError(err.message || 'Action failed.'); throw err; }
  }

  return (
    <div className="stack">
      <section className="section">
        <h1>Approvals</h1>
        <p className="muted">Grouped approval queues are limited to the work areas your account can actually read and act on.</p>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <section className="section">
        <div className="tabs" role="group" aria-label="Approval queues" style={{ marginTop: 0 }}>
          {visibleTabs.map((name) => (
            <button key={name} type="button" aria-pressed={tab === name} className={tab === name ? 'tab active' : 'tab'} onClick={() => setTab(name)} disabled={!!loadError}>{TAB_LABELS[name]} ({loadError ? '—' : (counts[name] || 0)})</button>
          ))}
        </div>
        {loading && <p className="small muted">Refreshing queues…</p>}
        {!loading && !loadError && !visibleTabs.length && <p className="muted">No approval queues are available for your current permissions.</p>}
      </section>

      {!loading && !!loadError && (
        <section className="section" role="alert" aria-live="polite">
          <h2>Approval queues unavailable</h2>
          <p className="error-text">{loadError}</p>
          <p className="muted">Current queue counts could not be verified, so Accounting will not present them as zero.</p>
          <div className="row wrap"><button type="button" onClick={() => load()}>Retry loading queues</button></div>
        </section>
      )}

      {!loadError && tab === 'records' && visibleTabs.includes('records') && (
        <section className="section"><h2>Records Queue</h2><table className="table"><thead><tr><th>ID</th><th>Module</th><th>Name</th><th>Status</th><th>Amount</th><th>Submitted</th><th></th></tr></thead><tbody>
          {recordRows.map((row) => <tr key={row.id}><td>{row.id}</td><td>{row.module_slug}</td><td>{row.name || row.item || '-'}</td><td>{row.workflow_status}</td><td>{currency(row.amount)}</td><td>{row.created_by || '-'}<br /><span className="small muted">{row.created_at || '-'}</span></td><td className="row wrap"><Link href={`/workspace/${row.module_slug}?tab=records`} className="button-link secondary-link">Open</Link>{canApproveRecord(row) && <><button type="button" className="secondary" onClick={() => runAction(() => approveRecord(row.id, true), `Record #${row.id} approved.`)}>Approve</button><button type="button" className="secondary" onClick={() => setPendingAction({ title: `Reject record #${row.id}?`, description: 'Record the reason so the encoder knows what needs correction.', confirmLabel: 'Reject record', reasonRequired: true, work: (reason) => approveRecord(row.id, false, { note: reason }), successMessage: `Record #${row.id} rejected.` })}>Reject</button></>}</td></tr>)}
          {!recordRows.length && <tr><td colSpan="7" className="muted">No record approvals pending.</td></tr>}
        </tbody></table></section>
      )}

      {!loadError && tab === 'procurement' && visibleTabs.includes('procurement') && (
        <div className="grid"><section className="section"><h2>Purchase Requests</h2><table className="table"><thead><tr><th>No</th><th>Date</th><th>Supplier</th><th>Status</th><th>Requested By</th><th></th></tr></thead><tbody>
          {prRows.map((row) => <tr key={row.id}><td>{row.request_no}</td><td>{row.request_date || '-'}</td><td>{row.supplier_name || '-'}</td><td>{row.status}</td><td>{row.requested_by || '-'}</td><td className="row wrap"><Link href="/purchase-requests" className="button-link secondary-link">Open</Link>{can('purchase_requests.approve') && <><button type="button" className="secondary" onClick={() => runAction(() => updatePurchaseRequestStatus(row.id, { status: 'approved' }), `PR ${row.request_no} approved.`)}>Approve</button><button type="button" className="secondary" onClick={() => runAction(() => updatePurchaseRequestStatus(row.id, { status: 'rejected' }), `PR ${row.request_no} rejected.`)}>Reject</button></>}</td></tr>)}
          {!prRows.length && <tr><td colSpan="6" className="muted">No PR approvals pending.</td></tr>}
        </tbody></table></section><section className="section"><h2>Purchase Orders</h2><table className="table"><thead><tr><th>No</th><th>Date</th><th>Supplier</th><th>Status</th><th>Issued By</th><th></th></tr></thead><tbody>
          {poRows.map((row) => <tr key={row.id}><td>{row.po_no}</td><td>{row.po_date || '-'}</td><td>{row.supplier_name || '-'}</td><td>{row.status}</td><td>{row.issued_by || '-'}</td><td className="row wrap"><Link href="/purchase-orders" className="button-link secondary-link">Open</Link>{can('purchase_orders.approve') && <><button type="button" className="secondary" onClick={() => runAction(() => updatePurchaseOrderStatus(row.id, { status: 'issued' }), `PO ${row.po_no} issued.`)}>Issue</button><button type="button" className="danger" onClick={() => setPendingAction({ title: `Cancel PO ${row.po_no}?`, description: 'This removes the purchase order from the active procurement workflow.', confirmLabel: 'Cancel purchase order', reasonRequired: true, work: (reason) => updatePurchaseOrderStatus(row.id, { status: 'cancelled', notes: reason }), successMessage: `PO ${row.po_no} cancelled.` })}>Cancel</button></>}</td></tr>)}
          {!poRows.length && <tr><td colSpan="6" className="muted">No PO approvals pending.</td></tr>}
        </tbody></table></section></div>
      )}

      {!loadError && tab === 'cashflow' && visibleTabs.includes('cashflow') && (
        <section className="section"><h2>Cashflow Transactions</h2><table className="table"><thead><tr><th>ID</th><th>Date</th><th>Direction</th><th>Account</th><th>Amount</th><th>Status</th><th>Created By</th><th></th></tr></thead><tbody>
          {moneyRows.map((row) => <tr key={row.id}><td>{row.id}</td><td>{row.transaction_date}</td><td>{row.direction}</td><td>{row.financial_account_code} · {row.financial_account_name}</td><td>{currency(row.amount)}</td><td>{row.status}</td><td>{row.created_by || '-'}</td><td className="row wrap"><Link href={row.direction === 'in' ? '/cashflow/money-in' : '/cashflow/money-out'} className="button-link secondary-link">Open</Link>{moneyTxIsActionable(row) && canActOnMoneyRow(row) && <><button type="button" className="secondary" onClick={() => runAction(() => approveMoneyTransaction(row.id, {}), `Money transaction #${row.id} approved.`)}>Approve</button><button type="button" className="danger" onClick={() => setPendingAction({ title: `Cancel money transaction #${row.id}?`, description: 'This changes the cashflow audit trail. Record why the transaction should be cancelled.', confirmLabel: 'Cancel transaction', reasonRequired: true, work: (reason) => cancelMoneyTransaction(row.id, { reason }), successMessage: `Money transaction #${row.id} cancelled.` })}>Cancel</button>{can('money.reverse') && <button type="button" className="danger" onClick={() => setPendingAction({ title: `Reverse money transaction #${row.id}?`, description: 'A reversal changes account balances and remains visible in the audit trail.', confirmLabel: 'Reverse transaction', reasonRequired: true, work: (reason) => reverseMoneyTransaction(row.id, { reason }), successMessage: `Money transaction #${row.id} reversed.` })}>Reverse</button>}</>}</td></tr>)}
          {!moneyRows.length && <tr><td colSpan="8" className="muted">No cashflow actions pending.</td></tr>}
        </tbody></table></section>
      )}

      {!loadError && tab === 'payroll' && visibleTabs.includes('payroll') && (
        <section className="section"><h2>Payroll Periods</h2><table className="table"><thead><tr><th>ID</th><th>Name</th><th>Period</th><th>Status</th><th>Net</th><th>Created By</th><th></th></tr></thead><tbody>
          {periodRows.map((row) => <tr key={row.id}><td>{row.id}</td><td>{row.name || `Payroll Period ${row.id}`}</td><td>{row.period_start || '-'} → {row.period_end || '-'}</td><td>{row.status}</td><td>{currency(row.net_total || 0)}</td><td>{row.created_by || '-'}</td><td className="row wrap"><Link href={`/payroll-periods/${row.id}`} className="button-link secondary-link">Open</Link>{can('approvals.act') && <button type="button" className="secondary" onClick={() => runAction(() => updatePayrollPeriod(row.id, { status: 'reviewed' }), `Payroll period #${row.id} reviewed.`)}>Review</button>}{can('payroll_periods.manage') && <button type="button" className="secondary" onClick={() => setPendingAction({ title: `Post payroll period #${row.id}?`, description: 'Confirm the payroll totals have been reviewed before posting.', confirmLabel: 'Post payroll', work: () => postPayrollPeriod(row.id, {}), successMessage: `Payroll period #${row.id} posted.` })}>Post</button>}</td></tr>)}
          {!periodRows.length && <tr><td colSpan="7" className="muted">No payroll approvals pending.</td></tr>}
        </tbody></table></section>
      )}

      {!loadError && tab === 'journals' && visibleTabs.includes('journals') && (
        <section className="section"><h2>Journal Entries</h2><table className="table"><thead><tr><th>ID</th><th>Date</th><th>Reference</th><th>Description</th><th>Status</th><th>Created By</th><th></th></tr></thead><tbody>
          {journalRows.map((row) => <tr key={row.id}><td>{row.id}</td><td>{row.entry_date || '-'}</td><td>{row.reference_no || '-'}</td><td>{row.description || '-'}</td><td>{row.status}</td><td>{row.created_by || '-'}</td><td><Link href="/journals" className="button-link secondary-link">Open</Link>{can('journals.post') && <button type="button" className="secondary" onClick={() => runAction(() => lockJournalEntry(row.id), `Journal ${row.reference_no || row.id} locked.`)}>Lock</button>}</td></tr>)}
          {!journalRows.length && <tr><td colSpan="7" className="muted">No journal approvals pending.</td></tr>}
        </tbody></table></section>
      )}

      {!loadError && tab === 'reconciliations' && visibleTabs.includes('reconciliations') && (
        <section className="section"><h2>Cash Reconciliations</h2><table className="table"><thead><tr><th>ID</th><th>Date</th><th>Account</th><th>Expected</th><th>Actual</th><th>Variance</th><th>Status</th><th>Counted By</th><th></th></tr></thead><tbody>
          {reconRows.map((row) => <tr key={row.id}><td>{row.id}</td><td>{row.reconciliation_date}</td><td>{row.financial_account_code} · {row.financial_account_name}</td><td>{currency(row.expected_closing || 0)}</td><td>{currency(row.actual_counted || 0)}</td><td>{currency(row.variance || 0)}</td><td>{row.status}</td><td>{row.counted_by || '-'}</td><td className="row wrap"><Link href="/cashflow/reconciliation" className="button-link secondary-link">Open</Link>{reconIsActionable(row) && can('cashflow.reconcile') && <><button type="button" className="secondary" onClick={() => runAction(() => approveReconciliation(row.id, {}), `Reconciliation #${row.id} reviewed.`)}>Review</button><button type="button" className="secondary" onClick={() => setPendingAction({ title: `Close reconciliation #${row.id}?`, description: 'Confirm the counted cash and variance have been reviewed.', confirmLabel: 'Close reconciliation', work: (reason) => closeReconciliation(row.id, { reason: reason || 'Closed from approvals queue' }), successMessage: `Reconciliation #${row.id} closed.` })}>Close</button><button type="button" className="danger" onClick={() => setPendingAction({ title: `Reverse reconciliation #${row.id}?`, description: 'Reversing a reconciliation reopens the cash audit trail. Record why this is necessary.', confirmLabel: 'Reverse reconciliation', reasonRequired: true, work: (reason) => reverseReconciliation(row.id, { reason }), successMessage: `Reconciliation #${row.id} reversed.` })}>Reverse</button></>}</td></tr>)}
          {!reconRows.length && <tr><td colSpan="9" className="muted">No reconciliation approvals pending.</td></tr>}
        </tbody></table></section>
      )}
      <ConfirmActionModal open={!!pendingAction} title={pendingAction?.title} description={pendingAction?.description} confirmLabel={pendingAction?.confirmLabel} tone={pendingAction?.tone || 'danger'} reasonRequired={!!pendingAction?.reasonRequired} onClose={() => setPendingAction(null)} onConfirm={confirmPendingAction} />
    </div>
  );
}
