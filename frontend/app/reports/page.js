'use client';
import Link from 'next/link';
import { businessDateISO } from '../../lib/businessDate';
import { useAppShell } from '../../components/app-shell/AppShellContext';

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  createSettlement,
  fetchAgingReport,
  fetchFinancialStatements,
  fetchManagementCsv,
  fetchManagementReport,
  fetchSettlements,
  fetchJournalLinkageReview,
  fetchJournalLinkageReviewCsv,
  fetchJournalLinkageHistory,
  submitJournalLinkageEvidence,
} from '../../lib/api';
import { shouldPreventEnterSubmit } from '../../lib/formBehavior';

function todayISO() {
  return businessDateISO();
}

function monthStartISO() {
  return `${businessDateISO().slice(0, 7)}-01`;
}

const closeRoutes = { draft_records: '/approvals', unreconciled_cashflow_accounts: '/cashflow/reconciliation', unposted_payroll_periods: '/payroll-periods', ar_over_30_days: '/cashflow/receivables', ap_over_30_days: '/cashflow/payables', low_stock_items: '/inventory-items' };
const exceptionLabels = { draft_records: 'Draft or pending records', unreconciled_cashflow_accounts: 'Unreconciled cash and bank accounts', unposted_payroll_periods: 'Unposted payroll periods', ar_over_30_days: 'Receivables over 30 days', ap_over_30_days: 'Payables over 30 days', low_stock_items: 'Low stock items' };

function currency(value) {
  return Number(value || 0).toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
}

function number(value) {
  return Number(value || 0).toLocaleString();
}

function readinessTone(status) {
  if (status === 'ready') return 'success';
  if (status === 'blocked') return 'danger';
  return 'warn';
}

function StatementTable({ title, rows = [], amountLabel = 'Balance' }) {
  return (
    <section className="section">
      <h2>{title}</h2>
      <table className="table dense-table" aria-label={`${title} financial statement`}>
        <thead><tr><th scope="col">Account</th><th scope="col">Type</th><th scope="col">{amountLabel}</th></tr></thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${title}-${row.account_code}-${row.account_name}`}>
              <td>{row.account_code || '-'} · {row.account_name || '-'}</td>
              <td>{row.family || row.account_type || '-'}</td>
              <td>{currency(row.balance)}</td>
            </tr>
          ))}
          {!rows.length && <tr><td colSpan="3" className="muted">No statement lines for this period.</td></tr>}
        </tbody>
      </table>
    </section>
  );
}

export default function ReportsPage() {
  const { user } = useAppShell();
  const canReviewJournalLinks = user?.role === 'owner' || user?.role === 'admin';
  const [activeView, setActiveView] = useState('overview');
  const [filters, setFilters] = useState({
    start_date: monthStartISO(),
    end_date: todayISO(),
    as_of_date: todayISO(),
  });
  const [report, setReport] = useState(null);
  const [statements, setStatements] = useState(null);
  const [aging, setAging] = useState(null);
  const [settlements, setSettlements] = useState([]);
  const [savingSettlement, setSavingSettlement] = useState(false);
  const [journalReview, setJournalReview] = useState(null);
  const [journalReviewPage, setJournalReviewPage] = useState(1);
  const [journalReviewSource, setJournalReviewSource] = useState('');
  const [journalReviewQueue, setJournalReviewQueue] = useState('unreviewed');
  const [journalReviewYear, setJournalReviewYear] = useState('');
  const [journalReviewLoading, setJournalReviewLoading] = useState(false);
  const [journalReviewExporting, setJournalReviewExporting] = useState(false);
  const [journalReviewExportError, setJournalReviewExportError] = useState('');
  const [journalReviewError, setJournalReviewError] = useState('');
  const [journalReviewRefresh, setJournalReviewRefresh] = useState(0);
  const [selectedJournalTx, setSelectedJournalTx] = useState(null);
  const [journalReviewHistory, setJournalReviewHistory] = useState([]);
  const [journalReviewDecision, setJournalReviewDecision] = useState('needs_evidence');
  const [journalReviewEvidenceRef, setJournalReviewEvidenceRef] = useState('');
  const [journalReviewNotes, setJournalReviewNotes] = useState('');
  const [journalReviewCandidateId, setJournalReviewCandidateId] = useState('');
  const [journalReviewSaving, setJournalReviewSaving] = useState(false);
  const [journalEvidenceFeedback, setJournalEvidenceFeedback] = useState('');
  const [journalEvidenceSaved, setJournalEvidenceSaved] = useState(false);
  const journalEvidenceSubmissionKey = useRef(null);
  const submissionInFlight = useRef(false);
  const lastSettlementSubmission = useRef(null);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const [settlementForm, setSettlementForm] = useState({
    record_id: '',
    settlement_date: todayISO(),
    amount: '',
    payment_method: 'cash',
    reference_no: '',
    notes: '',
  });

  async function load() {
    const [reportData, statementData, agingData, settlementRows] = await Promise.all([
      fetchManagementReport({
        startDate: filters.start_date || '',
        endDate: filters.end_date || '',
      }),
      fetchFinancialStatements({
        startDate: filters.start_date || '',
        endDate: filters.end_date || '',
        asOfDate: filters.as_of_date || '',
      }),
      fetchAgingReport(filters.as_of_date || ''),
      fetchSettlements({ limit: 200 }),
    ]);
    setReport(reportData || null);
    setStatements(statementData || null);
    setAging(agingData || null);
    setSettlements(Array.isArray(settlementRows) ? settlementRows : []);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || 'Failed to load reports.'));
  }, []);

  useEffect(() => {
    if (!canReviewJournalLinks || activeView !== 'journal-review') return;
    let cancelled = false;
    setJournalReviewLoading(true);
    setJournalReviewError('');
    fetchJournalLinkageReview({
      year: journalReviewYear,
      source: journalReviewSource,
      queue: journalReviewQueue,
      page: journalReviewPage,
      limit: 25,
    }).then((result) => {
      if (!cancelled) setJournalReview(result);
    }).catch((failure) => {
      if (!cancelled) {
        setJournalReview(null);
        setJournalReviewError(failure?.message || 'Unable to load journal exception review.');
      }
    }).finally(() => {
      if (!cancelled) setJournalReviewLoading(false);
    });
    return () => { cancelled = true; };
  }, [activeView, canReviewJournalLinks, journalReviewYear, journalReviewSource, journalReviewQueue, journalReviewPage, journalReviewRefresh]);

  async function openJournalEvidence(row) {
    journalEvidenceSubmissionKey.current = null;
    setJournalEvidenceSaved(false);
    setSelectedJournalTx(row);
    setJournalReviewDecision('needs_evidence');
    setJournalReviewEvidenceRef('');
    setJournalReviewNotes('');
    setJournalReviewCandidateId('');
    setJournalEvidenceFeedback('');
    try {
      const history = await fetchJournalLinkageHistory(row.id);
      setJournalReviewHistory(history.items || []);
    } catch (failure) {
      setJournalReviewHistory([]);
      setJournalEvidenceFeedback(failure?.message || 'Could not load review history.');
    }
  }

  async function saveJournalEvidence(event) {
    event.preventDefault();
    if (!selectedJournalTx || journalReviewSaving) return;
    setJournalReviewSaving(true);
    setJournalEvidenceFeedback('');
    try {
      // Reuse the same key after network ambiguity; never double-record a review.
      if (!journalEvidenceSubmissionKey.current) {
        journalEvidenceSubmissionKey.current = window.crypto.randomUUID();
      }
      const evidence = await submitJournalLinkageEvidence(selectedJournalTx.id, {
        decision: journalReviewDecision,
        supporting_reference: journalReviewEvidenceRef.trim() || null,
        notes: journalReviewNotes.trim(),
        suggested_journal_entry_id:
          journalReviewDecision === 'journal_candidate_identified' ? Number(journalReviewCandidateId) || null : null,
        expected_latest_review_id: selectedJournalTx.latest_review?.id || null,
        idempotency_key: journalEvidenceSubmissionKey.current,
      });
      journalEvidenceSubmissionKey.current = null;
      setJournalEvidenceSaved(true);
      setSelectedJournalTx((old) => ({ ...old, latest_review: evidence, review_status: 'evidence_recorded' }));
      setJournalReviewHistory((old) => old.some((item) => item.id === evidence.id) ? old : [evidence, ...old]);
      setJournalReviewRefresh((n) => n + 1);
      setJournalEvidenceFeedback('Evidence recorded. No accounting journal or cash balance was modified.');
    } catch (failure) {
      setJournalEvidenceFeedback(failure?.message || 'Unable to save evidence. You may retry safely.');
    } finally {
      setJournalReviewSaving(false);
    }
  }

  async function exportJournalReviewWorklist() {
    if (journalReviewExporting || !journalReview?.count) return;
    setJournalReviewExporting(true);
    setJournalReviewExportError('');
    try {
      const csv = await fetchJournalLinkageReviewCsv({
        year: journalReviewYear,
        source: journalReviewSource,
        queue: journalReviewQueue,
      });
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `journal-review-private-${journalReviewYear || 'all'}-${journalReviewQueue}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (failure) {
      setJournalReviewExportError(failure?.message || 'Could not export the private review worklist.');
    } finally {
      setJournalReviewExporting(false);
    }
  }

  function updateJournalEvidence(field, value) {
    journalEvidenceSubmissionKey.current = null;
    setJournalEvidenceSaved(false);
    if (field === 'decision') setJournalReviewDecision(value);
    else if (field === 'reference') setJournalReviewEvidenceRef(value);
    else if (field === 'notes') setJournalReviewNotes(value);
    else if (field === 'candidate') setJournalReviewCandidateId(value);
  }

  const settlementOptions = useMemo(() => {
    const receivables = aging?.receivables?.items || [];
    const payables = aging?.payables?.items || [];
    const all = [...receivables, ...payables];
    return all.sort((a, b) => Number(b.outstanding_amount || 0) - Number(a.outstanding_amount || 0));
  }, [aging]);

  async function reloadFromFilters() {
    setError('');
    setNotice('');
    try {
      await load();
      setNotice('Reports refreshed.');
    } catch (e) {
      setError(e.message || 'Failed to refresh reports.');
    }
  }

  async function exportCsv() {
    setError('');
    try {
      const csv = await fetchManagementCsv({
        startDate: filters.start_date || '',
        endDate: filters.end_date || '',
      });
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `management-report-${filters.start_date || 'all'}-${filters.end_date || 'latest'}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e.message || 'Failed to export CSV.');
    }
  }

  async function submitSettlement(e) {
    e.preventDefault();
    if (submissionInFlight.current) return;
    submissionInFlight.current = true;
    setSavingSettlement(true);
    setError('');
    setNotice('');
    const payload = {
      record_id: Number(settlementForm.record_id),
      settlement_date: settlementForm.settlement_date || null,
      amount: Number(settlementForm.amount || 0),
      payment_method: settlementForm.payment_method || null,
      reference_no: settlementForm.reference_no || null,
      notes: settlementForm.notes || null,
    };
    const fingerprint = JSON.stringify(payload);
    const previous = lastSettlementSubmission.current;
    const idempotencyKey = previous?.fingerprint === fingerprint
      ? previous.key
      : crypto.randomUUID();
    lastSettlementSubmission.current = { fingerprint, key: idempotencyKey };
    try {
      const result = await createSettlement(payload, { idempotencyKey });
      lastSettlementSubmission.current = null;
      setSettlementForm((prev) => ({
        ...prev,
        amount: '',
        reference_no: '',
        notes: '',
      }));
      setNotice(result?.replayed ? 'Previous settlement request confirmed; no duplicate recorded.' : 'Settlement evidence saved. Cash and journal posting must be verified separately.');
      await load();
    } catch (e2) {
      setError(e2.message || 'Failed to save settlement. Retrying with the same details will use the same request key.');
    } finally {
      submissionInFlight.current = false;
      setSavingSettlement(false);
    }
  }

  function isSettlementSubmittable() {
    return !savingSettlement && !!(Number(settlementForm.record_id || 0) > 0 && Number(settlementForm.amount || 0) > 0);
  }

  return (
    <div>
      <section className="section">
        <h1>Reports & Reconciliation</h1>
        <p className="muted">Financial statements, aging, and close readiness. All amounts are in PHP.</p>
        {!!notice && <p className="success-text" role="status" aria-live="polite">{notice}</p>}
        {!!error && <p className="error-text" role="alert">{error}</p>}
        <div className="form-grid">
          <label>
            Period Start
            <input type="date" value={filters.start_date} onChange={(e) => setFilters((f) => ({ ...f, start_date: e.target.value }))} />
          </label>
          <label>
            Period End
            <input type="date" value={filters.end_date} onChange={(e) => setFilters((f) => ({ ...f, end_date: e.target.value }))} />
          </label>
          <label>
            Aging As Of
            <input type="date" value={filters.as_of_date} onChange={(e) => setFilters((f) => ({ ...f, as_of_date: e.target.value }))} />
          </label>
        </div>
        <div className="row wrap report-actions" style={{ marginTop: 10 }}>
          <button onClick={reloadFromFilters}>Refresh</button>
          <button className="secondary" onClick={exportCsv}>Export CSV</button>
        </div>
        <div className="tabs" role="group" aria-label="Report views">
          {[
            ['overview', 'Overview'],
            ['statements', 'Financial Statements'],
            ['operations', 'Rooms, F&B & Inventory'],
            ['finance', 'AR, AP & Settlements'],
            ['payroll', 'Payroll & BIR'],
            ...(canReviewJournalLinks ? [['journal-review', 'Journal Review']] : []),
          ].map(([value, label]) => <button key={value} type="button" aria-pressed={activeView === value} className={activeView === value ? 'tab active' : 'tab'} onClick={() => setActiveView(value)}>{label}</button>)}
        </div>
      </section>

      <div hidden={activeView !== 'overview'}>
      <section className="section">
        <h2>Close Readiness</h2>
        <div className="row wrap">
          <span className={`badge ${readinessTone(report?.close_readiness?.status)}`}>Status {report?.close_readiness?.status || 'checking'}</span>
          <span className="badge">Score {number(report?.close_readiness?.score)} / 100</span>
          <span className={`badge ${report?.close_readiness?.can_close ? 'success' : 'danger'}`}>{report?.close_readiness?.can_close ? 'Close allowed' : 'Close blocked'}</span>
        </div>
        <p className="muted">{report?.close_readiness?.summary || 'Refresh the report to calculate close readiness.'}</p>
        <table className="table dense-table" aria-label="Close readiness checks" style={{ marginTop: 10 }}>
          <thead><tr><th scope="col">Check</th><th scope="col">Count</th><th scope="col">Status</th><th scope="col">Action</th></tr></thead>
          <tbody>
            {(report?.close_readiness?.checks || []).map((row) => (
              <tr key={row.key}>
                <td>{row.label}</td>
                <td>{number(row.value)}</td>
                <td><span className={`badge ${row.passed ? 'success' : row.severity === 'critical' ? 'danger' : row.severity === 'warning' ? 'warn' : 'info'}`}>{row.passed ? 'OK' : row.severity}</span></td>
                <td>{!row.passed && closeRoutes[row.key] ? <Link href={closeRoutes[row.key]}>{row.action}</Link> : row.action}</td>
              </tr>
            ))}
            {!report?.close_readiness?.checks?.length && <tr><td colSpan="4" className="muted">No close-readiness checks loaded.</td></tr>}
          </tbody>
        </table>
      </section>

      <section className="section">
        <h2>Management KPIs</h2>
        <div className="report-kpi-grid">
          {[
            ['Income', report?.kpis?.income_total],
            ['Expenses', report?.kpis?.expense_total],
            ['Net Income', report?.kpis?.net_income],
            ['Net Sales', report?.kpis?.sales_net_total],
            ['Inventory', report?.kpis?.inventory_value],
            ['Receivables', report?.kpis?.ar_outstanding],
            ['Payables', report?.kpis?.ap_outstanding],
          ].map(([label, value]) => (
            <div className="report-kpi" key={label}>
              <span className="report-kpi__label">{label}</span>
              <strong className="report-kpi__value" title={`PHP ${currency(value)}`}>₱{currency(value)}</strong>
            </div>
          ))}
        </div>
      </section>

      <section className="section">
        <h2>Exceptions</h2>
        <table className="table dense-table">
          <thead><tr><th>Metric</th><th>Value</th></tr></thead>
          <tbody>
            {Object.entries(report?.exceptions || {}).map(([k, v]) => (
              <tr key={k}>
                <td>{exceptionLabels[k] || k.replaceAll('_', ' ')}</td>
                <td>{v}</td>
              </tr>
            ))}
            {!report?.exceptions && <tr><td colSpan="2" className="muted">No exception data.</td></tr>}
          </tbody>
        </table>
      </section>

      <section className="section">
        <h2>Module Breakdown</h2>
        <table className="table dense-table">
          <thead><tr><th>Module</th><th>Income</th><th>Expense</th><th>Asset</th><th>Liability</th><th>Net Income</th></tr></thead>
          <tbody>
            {(report?.module_breakdown || []).map((row) => (
              <tr key={row.module_slug}>
                <td>{row.module_slug}</td>
                <td>{currency(row.income)}</td>
                <td>{currency(row.expense)}</td>
                <td>{currency(row.asset)}</td>
                <td>{currency(row.liability)}</td>
                <td>{currency(row.net_income)}</td>
              </tr>
            ))}
            {!report?.module_breakdown?.length && <tr><td colSpan="6" className="muted">No module data.</td></tr>}
          </tbody>
        </table>
      </section>
      </div>

      <div hidden={activeView !== 'statements'}>
        <section className="section">
          <h2>Formal Financial Statements</h2>
          {!statements?.trial_balance?.lines?.length && <p className="setup-notice">No posted journal data is available as of this date. Zero totals do not establish that your accounting setup or opening balances are complete.</p>}
          <p className="muted">Generated from posted journal entries, with cashflow transactions and operational subledgers shown as supporting schedules.</p>
          <div className="row wrap">
            <span className="badge">Period {statements?.period?.start_date || 'all'} to {statements?.period?.end_date || 'latest'}</span>
            <span className="badge">As of {statements?.period?.as_of_date || '-'}</span>
            <span className="badge">Trial balance: {!statements?.trial_balance?.lines?.length ? 'No posted data' : statements?.trial_balance?.totals?.is_balanced ? 'Balanced' : 'Needs review'}</span>
            <span className="badge">Balance sheet difference: ₱{currency(statements?.balance_sheet?.totals?.balance_check)}</span>
          </div>
        </section>

        <div className="grid">
          <section className="section">
            <h2>Profit & Loss</h2>
            {!statements?.profit_and_loss?.cost_of_sales_identified && <p className="muted">No COGS accounts detected in this period. Gross profit may be overstated until cost-of-sales accounts are correctly classified and posted.</p>}
            <div className="row wrap">
              <span className="badge">Revenue {currency(statements?.profit_and_loss?.totals?.revenue)}</span>
              <span className="badge">COGS {currency(statements?.profit_and_loss?.totals?.cost_of_sales)}</span>
              <span className="badge">Gross Profit {currency(statements?.profit_and_loss?.totals?.gross_profit)}</span>
              <span className="badge">Expenses {currency(statements?.profit_and_loss?.totals?.expenses)}</span>
              <span className="badge">Net Income {currency(statements?.profit_and_loss?.totals?.net_income)}</span>
            </div>
            <table className="table dense-table" style={{ marginTop: 10 }}>
              <thead><tr><th>Account</th><th>Type</th><th>Amount</th></tr></thead>
              <tbody>
                {[...(statements?.profit_and_loss?.revenue || []), ...(statements?.profit_and_loss?.expenses || [])].map((row) => (
                  <tr key={`pl-${row.account_code}-${row.account_name}`}>
                    <td>{row.account_code} · {row.account_name}</td>
                    <td>{row.family}</td>
                    <td>{currency(row.balance)}</td>
                  </tr>
                ))}
                {!statements?.profit_and_loss && <tr><td colSpan="3" className="muted">No Profit & Loss data loaded.</td></tr>}
              </tbody>
            </table>
          </section>

          <section className="section">
            <h2>Cash Movements (Management)</h2>
            <p className="muted">Transaction-based cash movements are not a formal statement of cash flows. Unclassified items require accountant review.</p>
            {statements?.cash_flow?.classification_status === "requires_review" && <p className="setup-notice">{statements?.cash_flow?.classification_counts?.unclassified || 0} transaction(s) need cash-flow classification.</p>}
            <div className="row wrap">
              <span className="badge">Cash In {currency(statements?.cash_flow?.totals?.cash_in)}</span>
              <span className="badge">Cash Out {currency(statements?.cash_flow?.totals?.cash_out)}</span>
              <span className="badge">Net Cash Flow {currency(statements?.cash_flow?.totals?.net_cash_flow)}</span>
              <span className="badge">Transfers {currency(statements?.cash_flow?.transfers?.gross_transfer_amount)}</span>
            </div>
            <table className="table dense-table" style={{ marginTop: 10 }}>
              <thead><tr><th>Activity</th><th>Category</th><th>In</th><th>Out</th><th>Net</th></tr></thead>
              <tbody>
                {[
                  ['Operating', statements?.cash_flow?.operating_activities || []],
                  ['Investing', statements?.cash_flow?.investing_activities || []],
                  ['Financing', statements?.cash_flow?.financing_activities || []],
                  ['Needs review', statements?.cash_flow?.unclassified_activities || []],
                ].flatMap(([section, rows]) => rows.map((row) => (
                  <tr key={`cf-${section}-${row.activity}-${row.category}`}>
                    <td>{section} · {row.activity}</td>
                    <td>{row.category}</td>
                    <td>{currency(row.cash_in)}</td>
                    <td>{currency(row.cash_out)}</td>
                    <td>{currency(row.net)}</td>
                  </tr>
                )))}
                {!statements?.cash_flow?.totals?.cash_in && !statements?.cash_flow?.totals?.cash_out && <tr><td colSpan="5" className="muted">No posted cash transactions in this period.</td></tr>}
              </tbody>
            </table>
          </section>
        </div>

        <div className="grid">
          <StatementTable title="Balance Sheet Assets" rows={statements?.balance_sheet?.assets || []} />
          <StatementTable title="Balance Sheet Liabilities" rows={statements?.balance_sheet?.liabilities || []} />
        </div>
        <div className="grid">
          <StatementTable title="Balance Sheet Equity" rows={statements?.balance_sheet?.equity || []} />
          <section className="section">
            <h2>Balance Sheet Totals</h2>
            <table className="table dense-table">
              <tbody>
                <tr><td>Assets</td><td>{currency(statements?.balance_sheet?.totals?.assets)}</td></tr>
                <tr><td>Liabilities</td><td>{currency(statements?.balance_sheet?.totals?.liabilities)}</td></tr>
                <tr><td>Equity</td><td>{currency(statements?.balance_sheet?.totals?.equity)}</td></tr>
                <tr><td>Liabilities + Equity</td><td>{currency(statements?.balance_sheet?.totals?.liabilities_and_equity)}</td></tr>
                <tr><td>Balance Check</td><td>{currency(statements?.balance_sheet?.totals?.balance_check)}</td></tr>
              </tbody>
            </table>
          </section>
        </div>

        <section className="section">
          <h2>Trial Balance</h2>
          <div className="row wrap">
            <span className="badge">Debit {currency(statements?.trial_balance?.totals?.debit)}</span>
            <span className="badge">Credit {currency(statements?.trial_balance?.totals?.credit)}</span>
            <span className="badge">Variance {currency(statements?.trial_balance?.totals?.variance)}</span>
          </div>
          <table className="table dense-table" style={{ marginTop: 10 }}>
            <thead><tr><th>Account</th><th>Debit</th><th>Credit</th><th>Balance</th></tr></thead>
            <tbody>
              {(statements?.trial_balance?.lines || []).map((row) => (
                <tr key={`tb-${row.account_code}-${row.account_name}`}>
                  <td>{row.account_code || '-'} · {row.account_name || '-'}</td>
                  <td>{currency(row.debit)}</td>
                  <td>{currency(row.credit)}</td>
                  <td>{currency(row.balance)}</td>
                </tr>
              ))}
              {!statements?.trial_balance?.lines?.length && <tr><td colSpan="4" className="muted">No journal lines as of this date.</td></tr>}
            </tbody>
          </table>
        </section>

        <section className="section">
          <h2>Operational Supplement</h2>
          <div className="row wrap">
            <span className="badge">Cash Position {currency(statements?.operational_supplement?.cash_position?.total)}</span>
            <span className="badge">AR Balance {currency(statements?.operational_supplement?.receivables?.balance_due)}</span>
            <span className="badge">AP Balance {currency(statements?.operational_supplement?.payables?.balance_due)}</span>
            <span className="badge">Inventory {currency(statements?.operational_supplement?.inventory?.valuation)}</span>
            <span className="badge">Assets NBV {currency(statements?.operational_supplement?.assets?.net_book_value)}</span>
          </div>
          <p className="muted">{(statements?.notes || []).join(' ')}</p>
        </section>
      </div>

      <div hidden={activeView !== 'operations'}>
      <div className="grid">
        <section className="section">
          <h2>Rooms Snapshot</h2>
          <div className="row wrap">
            <span className="badge">Arrivals {number(report?.rooms?.arrivals)}</span>
            <span className="badge">Departures {number(report?.rooms?.departures)}</span>
            <span className="badge">In-house {number(report?.rooms?.in_house)}</span>
            <span className="badge">Cancelled {number(report?.rooms?.cancelled)}</span>
            <span className="badge">No-show {number(report?.rooms?.no_show)}</span>
          </div>
          <table className="table dense-table" style={{ marginTop: 10 }}>
            <thead><tr><th>Room Type</th><th>Gross Revenue</th></tr></thead>
            <tbody>
              {(report?.rooms?.revenue_by_room_type || []).slice(0, 12).map((row) => (
                <tr key={row.room_type}>
                  <td>{row.room_type}</td>
                  <td>{currency(row.gross_revenue)}</td>
                </tr>
              ))}
              {!report?.rooms?.revenue_by_room_type?.length && <tr><td colSpan="2" className="muted">No room revenue data.</td></tr>}
            </tbody>
          </table>
        </section>

        <section className="section">
          <h2>Channel Performance</h2>
          <table className="table dense-table">
            <thead><tr><th>Channel</th><th>Bookings</th><th>Gross Revenue</th></tr></thead>
            <tbody>
              {(report?.rooms?.revenue_by_channel || []).slice(0, 12).map((row) => (
                <tr key={row.channel}>
                  <td>{row.channel}</td>
                  <td>{number(row.bookings)}</td>
                  <td>{currency(row.gross_revenue)}</td>
                </tr>
              ))}
              {!report?.rooms?.revenue_by_channel?.length && <tr><td colSpan="3" className="muted">No channel booking data.</td></tr>}
            </tbody>
          </table>
          <table className="table dense-table" style={{ marginTop: 10 }}>
            <thead><tr><th>Channel</th><th>Net Payout</th><th>Paid</th><th>Variance</th></tr></thead>
            <tbody>
              {(report?.channels?.payouts || []).slice(0, 12).map((row) => (
                <tr key={`payout-${row.channel}`}>
                  <td>{row.channel}</td>
                  <td>{currency(row.net_amount)}</td>
                  <td>{currency(row.paid_net_amount)}</td>
                  <td>{currency(row.variance)}</td>
                </tr>
              ))}
              {!report?.channels?.payouts?.length && <tr><td colSpan="4" className="muted">No payout variance data.</td></tr>}
            </tbody>
          </table>
        </section>
      </div>

      <div className="grid">
        <section className="section">
          <h2>Restaurant & F&B</h2>
          <div className="row wrap">
            <span className="badge">Staff Meals {number(report?.fnb?.staff_meals?.count)}</span>
            <span className="badge">Staff Meal Cost {currency(report?.fnb?.staff_meals?.cost_total)}</span>
            <span className="badge">Waste/Spillage Cost {currency(report?.fnb?.waste_movements?.cost_total)}</span>
          </div>
          <table className="table dense-table" style={{ marginTop: 10 }}>
            <thead><tr><th>Outlet</th><th>Sales</th></tr></thead>
            <tbody>
              {(report?.fnb?.sales_by_outlet || []).map((row) => (
                <tr key={row.outlet}>
                  <td>{row.outlet}</td>
                  <td>{currency(row.sales)}</td>
                </tr>
              ))}
              {!report?.fnb?.sales_by_outlet?.length && <tr><td colSpan="2" className="muted">No outlet sales data.</td></tr>}
            </tbody>
          </table>
          <table className="table dense-table" style={{ marginTop: 10 }}>
            <thead><tr><th>Menu Item</th><th>Qty</th><th>Net Sales</th></tr></thead>
            <tbody>
              {(report?.fnb?.sales_by_item || []).slice(0, 15).map((row) => (
                <tr key={row.item_name}>
                  <td>{row.item_name}</td>
                  <td>{number(row.quantity)}</td>
                  <td>{currency(row.net_sales)}</td>
                </tr>
              ))}
              {!report?.fnb?.sales_by_item?.length && <tr><td colSpan="3" className="muted">No menu sales data.</td></tr>}
            </tbody>
          </table>
        </section>

        <section className="section">
          <h2>Inventory & Purchasing</h2>
          <div className="row wrap">
            <span className="badge">Stock Items {number(report?.inventory?.stock_on_hand_count)}</span>
            <span className="badge">Valuation {currency(report?.inventory?.valuation)}</span>
            <span className="badge">Open PR {number(report?.procurement?.open_pr_count)}</span>
            <span className="badge">Open PO {number(report?.procurement?.open_po_count)}</span>
            <span className="badge">PO Partially Received {number(report?.procurement?.partially_received_po_count)}</span>
          </div>
          <table className="table dense-table" style={{ marginTop: 10 }}>
            <thead><tr><th>Item</th><th>On Hand</th><th>Reorder</th></tr></thead>
            <tbody>
              {(report?.inventory?.low_stock_items || []).slice(0, 15).map((row) => (
                <tr key={row.item_id}>
                  <td>{row.item_name}</td>
                  <td>{number(row.quantity_on_hand)} {row.unit || ''}</td>
                  <td>{number(row.reorder_level)} {row.unit || ''}</td>
                </tr>
              ))}
              {!report?.inventory?.low_stock_items?.length && <tr><td colSpan="3" className="muted">No low stock items.</td></tr>}
            </tbody>
          </table>
          <table className="table dense-table" style={{ marginTop: 10 }}>
            <thead><tr><th>Supplier</th><th>Purchase Total</th></tr></thead>
            <tbody>
              {(report?.procurement?.supplier_purchase_totals || []).slice(0, 15).map((row) => (
                <tr key={row.supplier_name}>
                  <td>{row.supplier_name}</td>
                  <td>{currency(row.total_amount)}</td>
                </tr>
              ))}
              {!report?.procurement?.supplier_purchase_totals?.length && <tr><td colSpan="2" className="muted">No supplier totals in this period.</td></tr>}
            </tbody>
          </table>
        </section>
      </div>
      </div>

      <div hidden={activeView !== 'payroll'}>
      <div className="grid">
        <section className="section">
          <h2>Payroll & Labor</h2>
          <div className="row wrap">
            <span className="badge">Attendance Rows {number(report?.payroll_labor?.attendance_summary?.rows)}</span>
            <span className="badge">Absent {number(report?.payroll_labor?.attendance_summary?.absent_count)}</span>
            <span className="badge">Overtime Hours {number(report?.payroll_labor?.attendance_summary?.overtime_hours)}</span>
            <span className="badge">Night Diff Hours {number(report?.payroll_labor?.attendance_summary?.night_diff_hours)}</span>
          </div>
          <table className="table dense-table" style={{ marginTop: 10 }}>
            <thead><tr><th>Department</th><th>Gross Pay</th><th>Net Pay</th></tr></thead>
            <tbody>
              {(report?.payroll_labor?.payroll_by_department || []).map((row) => (
                <tr key={row.department}>
                  <td>{row.department}</td>
                  <td>{currency(row.gross_pay)}</td>
                  <td>{currency(row.net_pay)}</td>
                </tr>
              ))}
              {!report?.payroll_labor?.payroll_by_department?.length && <tr><td colSpan="3" className="muted">No payroll by department data in period.</td></tr>}
            </tbody>
          </table>
        </section>

        <section className="section">
          <h2>BIR Locks</h2>
          <table className="table dense-table">
            <thead><tr><th>Period</th><th>Locked</th><th>By</th><th>Notes</th><th>Updated</th></tr></thead>
            <tbody>
              {(report?.compliance?.bir_locks || []).slice(0, 20).map((row, index) => (
                <tr key={`${row.period_key}-${index}`}>
                  <td>{row.period_key}</td>
                  <td>{String(!!row.is_locked)}</td>
                  <td>{row.locked_by || '-'}</td>
                  <td>{row.notes || '-'}</td>
                  <td>{row.updated_at || '-'}</td>
                </tr>
              ))}
              {!report?.compliance?.bir_locks?.length && <tr><td colSpan="5" className="muted">No BIR lock history.</td></tr>}
            </tbody>
          </table>
        </section>
      </div>
      </div>

      <div hidden={activeView !== 'finance'}>
      <div className="grid">
        <section className="section">
          <h2>AR Aging</h2>
          <div className="row wrap">
            <span className="badge">Total {currency(aging?.receivables?.total_outstanding)}</span>
            <span className="badge">0-30 {currency(aging?.receivables?.bucket_totals?.['0-30'])}</span>
            <span className="badge">31-60 {currency(aging?.receivables?.bucket_totals?.['31-60'])}</span>
            <span className="badge">61-90 {currency(aging?.receivables?.bucket_totals?.['61-90'])}</span>
            <span className="badge">91+ {currency(aging?.receivables?.bucket_totals?.['91+'])}</span>
          </div>
          <table className="table dense-table" style={{ marginTop: 10 }}>
            <thead><tr><th>Record</th><th>Counterparty</th><th>Outstanding</th><th>Age</th><th>Bucket</th></tr></thead>
            <tbody>
              {(aging?.receivables?.items || []).slice(0, 20).map((row) => (
                <tr key={`ar-${row.record_id}`}>
                  <td>{row.record_id} · {row.name || '-'}</td>
                  <td>{row.counterparty || '-'}</td>
                  <td>{currency(row.outstanding_amount)}</td>
                  <td>{row.age_days}</td>
                  <td>{row.bucket}</td>
                </tr>
              ))}
              {!aging?.receivables?.items?.length && <tr><td colSpan="5" className="muted">No receivables outstanding.</td></tr>}
            </tbody>
          </table>
        </section>

        <section className="section">
          <h2>AP Aging</h2>
          <div className="row wrap">
            <span className="badge">Total {currency(aging?.payables?.total_outstanding)}</span>
            <span className="badge">0-30 {currency(aging?.payables?.bucket_totals?.['0-30'])}</span>
            <span className="badge">31-60 {currency(aging?.payables?.bucket_totals?.['31-60'])}</span>
            <span className="badge">61-90 {currency(aging?.payables?.bucket_totals?.['61-90'])}</span>
            <span className="badge">91+ {currency(aging?.payables?.bucket_totals?.['91+'])}</span>
          </div>
          <table className="table dense-table" style={{ marginTop: 10 }}>
            <thead><tr><th>Record</th><th>Counterparty</th><th>Outstanding</th><th>Age</th><th>Bucket</th></tr></thead>
            <tbody>
              {(aging?.payables?.items || []).slice(0, 20).map((row) => (
                <tr key={`ap-${row.record_id}`}>
                  <td>{row.record_id} · {row.name || '-'}</td>
                  <td>{row.counterparty || '-'}</td>
                  <td>{currency(row.outstanding_amount)}</td>
                  <td>{row.age_days}</td>
                  <td>{row.bucket}</td>
                </tr>
              ))}
              {!aging?.payables?.items?.length && <tr><td colSpan="5" className="muted">No payables outstanding.</td></tr>}
            </tbody>
          </table>
        </section>
      </div>

      <div className="grid">
        <section className="section">
          <h2>Add Settlement Evidence</h2>
          <p className="muted">This adjusts an approved credit record's settlement history only. It does not transfer cash or generate a journal; verify the payment separately in the money ledger.</p>
          <form onSubmit={submitSettlement} onKeyDown={(event) => shouldPreventEnterSubmit(event, isSettlementSubmittable)}>
            <div className="form-grid">
              <label>
                Record
                <select value={settlementForm.record_id} onChange={(e) => setSettlementForm((f) => ({ ...f, record_id: e.target.value }))}>
                  <option value="">Select outstanding record</option>
                  {settlementOptions.map((row) => (
                    <option key={row.record_id} value={row.record_id}>
                      {row.record_id} · {row.name || '-'} · {row.counterparty || '-'} · {currency(row.outstanding_amount)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Settlement Date
                <input type="date" value={settlementForm.settlement_date} onChange={(e) => setSettlementForm((f) => ({ ...f, settlement_date: e.target.value }))} />
              </label>
              <label>
                Amount
                <input type="number" min="0.01" step="0.01" value={settlementForm.amount} onChange={(e) => setSettlementForm((f) => ({ ...f, amount: e.target.value }))} />
              </label>
              <label>
                Payment Method
                <input value={settlementForm.payment_method} onChange={(e) => setSettlementForm((f) => ({ ...f, payment_method: e.target.value }))} />
              </label>
              <label>
                Reference
                <input value={settlementForm.reference_no} onChange={(e) => setSettlementForm((f) => ({ ...f, reference_no: e.target.value }))} />
              </label>
            </div>
            <label>
              Notes
              <textarea value={settlementForm.notes} onChange={(e) => setSettlementForm((f) => ({ ...f, notes: e.target.value }))} />
            </label>
            <button type="submit" disabled={!isSettlementSubmittable()}>{savingSettlement ? 'Saving…' : 'Save Settlement Evidence'}</button>
          </form>
        </section>

        <section className="section">
          <h2>Recent Settlements</h2>
          <table className="table dense-table">
            <thead><tr><th>Date</th><th>Record</th><th>Amount</th><th>Payment</th><th>Ref</th></tr></thead>
            <tbody>
              {settlements.map((row) => (
                <tr key={row.id}>
                  <td>{row.settlement_date}</td>
                  <td>{row.record_id} · {row.record_name || '-'}</td>
                  <td>{currency(row.amount)}</td>
                  <td>{row.payment_method || '-'}</td>
                  <td>{row.reference_no || '-'}</td>
                </tr>
              ))}
              {!settlements.length && <tr><td colSpan="5" className="muted">No settlements yet.</td></tr>}
            </tbody>
          </table>
        </section>
      </div>
      </div>

      {canReviewJournalLinks && (
        <div hidden={activeView !== 'journal-review'}>
          <section className="section journal-review-section">
            <h2>Journal Linkage Review</h2>
            <p className="muted">
              Owner/admin-only evidence review of posted cash movements with no direct journal link.
              A missing link does not establish missing revenue or justify posting a new journal.
              Transaction values are read-only; review decisions are saved in a separate evidence history
              without altering cashflow or general-ledger postings.
            </p>
            <div className="form-grid journal-review-filters">
              <label>
                Transaction Year
                <select value={journalReviewYear} onChange={(event) => { setJournalReviewYear(event.target.value); setJournalReviewSource(''); setJournalReviewPage(1); }}>
                  <option value="">All years</option>
                  {['2024', '2025', '2026', '2027'].map((year) => <option key={year} value={year}>{year}</option>)}
                </select>
              </label>
              <label>
                External Source
                <select value={journalReviewSource} onChange={(event) => { setJournalReviewSource(event.target.value); setJournalReviewPage(1); }}>
                  <option value="">All sources</option>
                  {(journalReview?.source_counts || []).map((entry) => (
                    <option key={entry.source} value={entry.source}>{entry.source} ({number(entry.count)})</option>
                  ))}
                </select>
              </label>
              <label>
                Review Queue
                <select value={journalReviewQueue} onChange={(event) => {
                  setJournalReviewQueue(event.target.value);
                  setJournalReviewPage(1);
                  setSelectedJournalTx(null);
                }}>
                  <option value="unreviewed">Awaiting first review</option>
                  <option value="reviewed">Evidence already recorded</option>
                  <option value="all">All missing journal links</option>
                </select>
              </label>
            </div>
            <div className="journal-review-progress" aria-label="Journal review progress">
              <div className="journal-review-progress-metrics">
                <div><span>Missing journal links</span><strong>{number(journalReview?.review_summary?.missing_journal_links ?? journalReview?.count)}</strong></div>
                <div><span>Awaiting first review</span><strong>{number(journalReview?.review_summary?.never_reviewed ?? journalReview?.count)}</strong></div>
                <div><span>Evidence recorded</span><strong>{number(journalReview?.review_summary?.evidence_recorded ?? 0)}</strong></div>
              </div>
              <div className="journal-review-progress-track" role="progressbar" aria-label="Evidence review coverage"
                aria-valuemin={0} aria-valuemax={journalReview?.review_summary?.missing_journal_links ?? journalReview?.scope_count ?? 0}
                aria-valuenow={journalReview?.review_summary?.evidence_recorded || 0}>
                <div className="journal-review-progress-fill" style={{
                  width: `${journalReview?.review_summary?.missing_journal_links ? Math.min(100, 100 * (journalReview?.review_summary?.evidence_recorded || 0) / journalReview.review_summary.missing_journal_links) : 0}%`,
                }} />
              </div>
              <p className="muted">Evidence recorded is not the same as a journal link verified, reconciled or posted.</p>
            </div>
            <div className="row wrap journal-review-summary">
              <span className="badge">Showing {number(journalReview?.count)} records in this queue</span>
              <span className="badge">Page {journalReviewPage} of {journalReview?.total_pages || 1}</span>
              <button type="button" className="secondary"
                onClick={exportJournalReviewWorklist}
                disabled={journalReviewLoading || journalReviewExporting || !journalReview?.count}>
                {journalReviewExporting ? 'Exporting private CSV…' : 'Export private CSV'}
              </button>
              {journalReviewLoading && <span role="status" className="muted">Loading review…</span>}
            </div>
            {!!journalReviewError && <p role="alert" className="error-text">{journalReviewError}</p>}
            {!!journalReviewExportError && <p role="alert" className="error-text">{journalReviewExportError}</p>}
            <p className="muted">Private download includes all rows in the selected queue and filters, not only this page. Store it securely; no ledger posting or matching is performed.</p>
            <p className="muted">
              Match each item against its external receipt, source cashbook, folio, and existing ledger
              before approving any correction. No automatic matching or posting is performed.
            </p>
            <div className="journal-review-table-scroll" tabIndex={0} role="region" aria-label="Journal linkage exception records">
              <table className="table dense-table journal-review-table" aria-label="Unverified journal linkage records">
                <thead><tr>
                  <th scope="col">Transaction</th><th scope="col">Date</th><th scope="col">Account ID</th>
                  <th scope="col">Source</th><th scope="col">External Event</th><th scope="col">Payment Ref</th>
                  <th scope="col">Amount (PHP)</th><th scope="col">Review</th>
                </tr></thead>
                <tbody>
                  {(journalReview?.items || []).map((entry) => (
                    <tr key={entry.id}>
                      <td>{entry.id}</td><td>{entry.transaction_date || '—'}</td>
                      <td>{entry.financial_account_id}</td><td>{entry.external_source || '—'}</td>
                      <td>{entry.external_id || '—'}</td><td>{entry.reference_no || '—'}</td>
                      <td className="numeric">{currency(entry.amount)}</td>
                      <td>
                        <button type="button" className="secondary" onClick={() => openJournalEvidence(entry)}>
                          {entry.latest_review ? 'Review again' : 'Record evidence'}
                        </button>
                        <span className="muted journal-review-row-status">
                          {entry.latest_review ? 'Evidence recorded · no ledger action' : 'Unverified'}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {!journalReviewLoading && !(journalReview?.items || []).length && (
                    <tr><td colSpan="8" className="muted">No matching records in this queue. Change the review queue, year, or source.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
            {selectedJournalTx && (
              <section className="journal-evidence-panel" aria-label="Record journal evidence">
                <div className="row wrap journal-evidence-head">
                  <h3>Evidence for transaction #{selectedJournalTx.id}</h3>
                  <button type="button" className="secondary" onClick={() => setSelectedJournalTx(null)}>Close</button>
                </div>
                <p className="muted">
                  Classifications are preliminary. A suggested journal is not an accounting link or posting.
                  Financial figures remain unchanged.
                </p>
                <form onSubmit={saveJournalEvidence} className="journal-evidence-form">
                  <label>Review classification
                    <select value={journalReviewDecision} onChange={(e) => updateJournalEvidence('decision', e.target.value)}>
                      <option value="needs_evidence">Needs more source evidence</option>
                      <option value="cashflow_only_documented">Cashflow-only treatment documented</option>
                      <option value="journal_candidate_identified">Possible existing posted journal identified</option>
                      <option value="requires_accounting_review">Further accounting review required</option>
                    </select>
                  </label>
                  <label>Evidence reference
                    <input value={journalReviewEvidenceRef} maxLength={255}
                      placeholder="Cashbook page, receipt number, folio or controlled file reference"
                      onChange={(e) => updateJournalEvidence('reference', e.target.value)}
                      required={journalReviewDecision !== 'needs_evidence'}/>
                  </label>
                  {journalReviewDecision === 'journal_candidate_identified' && (
                    <label>Existing posted journal ID (candidate only)
                      <input type="number" min="1" value={journalReviewCandidateId} required
                        onChange={(e) => updateJournalEvidence('candidate', e.target.value)} />
                    </label>
                  )}
                  <label>Review rationale (at least 10 characters)
                    <textarea value={journalReviewNotes} minLength={10} maxLength={2000} required rows={3}
                      onChange={(e) => updateJournalEvidence('notes', e.target.value)}
                      placeholder="Explain the evidence and why this classification is appropriate." />
                  </label>
                  <button type="submit" disabled={journalReviewSaving || journalEvidenceSaved || journalReviewNotes.trim().length < 10 ||
                    (journalReviewDecision !== 'needs_evidence' && !journalReviewEvidenceRef.trim()) ||
                    (journalReviewDecision === 'journal_candidate_identified' && !(Number(journalReviewCandidateId) > 0))}>
                    {journalReviewSaving ? 'Saving…' : journalEvidenceSaved ? 'Saved — edit to add another review' : 'Save review evidence'}
                  </button>
                </form>
                {!!journalEvidenceFeedback && <p role="status" aria-live="polite">{journalEvidenceFeedback}</p>}
                <h4>Review history (newest first)</h4>
                <div className="journal-evidence-history">
                  {journalReviewHistory.map((entry) => (
                    <div className="journal-evidence-history-item" key={entry.id}>
                      <strong>{entry.decision.replaceAll('_', ' ')}</strong>
                      <span className="muted">{entry.reviewed_by} · {entry.reviewed_at || 'time unavailable'}</span>
                      <p>{entry.supporting_reference || 'Evidence pending'} — {entry.notes}</p>
                    </div>
                  ))}
                  {!journalReviewHistory.length && <p className="muted">No recorded review evidence yet.</p>}
                </div>
              </section>
            )}
            <div className="row wrap journal-review-pagination">
              <button type="button" className="secondary" disabled={journalReviewLoading || journalReviewPage <= 1}
                onClick={() => setJournalReviewPage((page) => Math.max(1, page - 1))}>Previous</button>
              <button type="button" className="secondary" disabled={journalReviewLoading || journalReviewPage >= (journalReview?.total_pages || 1)}
                onClick={() => setJournalReviewPage((page) => page + 1)}>Next</button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
