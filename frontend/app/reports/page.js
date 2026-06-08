'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  createSettlement,
  fetchAgingReport,
  fetchFinancialStatements,
  fetchManagementCsv,
  fetchManagementReport,
  fetchSettlements,
} from '../../lib/api';
import { shouldPreventEnterSubmit } from '../../lib/formBehavior';

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function monthStartISO() {
  const d = new Date();
  d.setDate(1);
  return d.toISOString().slice(0, 10);
}

function currency(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
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
      <table className="table dense-table">
        <thead><tr><th>Account</th><th>Type</th><th>{amountLabel}</th></tr></thead>
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
    setError('');
    setNotice('');
    try {
      await createSettlement({
        record_id: Number(settlementForm.record_id),
        settlement_date: settlementForm.settlement_date || null,
        amount: Number(settlementForm.amount || 0),
        payment_method: settlementForm.payment_method || null,
        reference_no: settlementForm.reference_no || null,
        notes: settlementForm.notes || null,
      });
      setSettlementForm((prev) => ({
        ...prev,
        amount: '',
        reference_no: '',
        notes: '',
      }));
      await load();
      setNotice('Settlement saved.');
    } catch (e2) {
      setError(e2.message || 'Failed to save settlement.');
    }
  }

  function isSettlementSubmittable() {
    return !!(Number(settlementForm.record_id || 0) > 0 && Number(settlementForm.amount || 0) > 0);
  }

  return (
    <div>
      <section className="section">
        <h1>Reports & Reconciliation</h1>
        <p className="muted">Consolidated management view, AR/AP aging, and settlement tracking.</p>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
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
        <div className="row wrap" style={{ marginTop: 10 }}>
          <button onClick={reloadFromFilters}>Refresh</button>
          <button className="secondary" onClick={exportCsv}>Export Management CSV</button>
        </div>
        <div className="tabs">
          {[
            ['overview', 'Overview'],
            ['statements', 'Financial Statements'],
            ['operations', 'Rooms, F&B & Inventory'],
            ['finance', 'AR, AP & Settlements'],
            ['payroll', 'Payroll & BIR'],
          ].map(([value, label]) => <button key={value} type="button" className={activeView === value ? 'tab active' : 'tab'} onClick={() => setActiveView(value)}>{label}</button>)}
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
        <table className="table dense-table" style={{ marginTop: 10 }}>
          <thead><tr><th>Check</th><th>Count</th><th>Status</th><th>Action</th></tr></thead>
          <tbody>
            {(report?.close_readiness?.checks || []).map((row) => (
              <tr key={row.key}>
                <td>{row.label}</td>
                <td>{number(row.value)}</td>
                <td><span className={`badge ${row.passed ? 'success' : row.severity === 'critical' ? 'danger' : row.severity === 'warning' ? 'warn' : 'info'}`}>{row.passed ? 'OK' : row.severity}</span></td>
                <td>{row.action}</td>
              </tr>
            ))}
            {!report?.close_readiness?.checks?.length && <tr><td colSpan="4" className="muted">No close-readiness checks loaded.</td></tr>}
          </tbody>
        </table>
      </section>

      <section className="section">
        <h2>Management KPIs</h2>
        <div className="row wrap">
          <span className="badge">Income {currency(report?.kpis?.income_total)}</span>
          <span className="badge">Expense {currency(report?.kpis?.expense_total)}</span>
          <span className="badge">Net {currency(report?.kpis?.net_income)}</span>
          <span className="badge">Sales Net {currency(report?.kpis?.sales_net_total)}</span>
          <span className="badge">Inventory Value {currency(report?.kpis?.inventory_value)}</span>
          <span className="badge">AR Outstanding {currency(report?.kpis?.ar_outstanding)}</span>
          <span className="badge">AP Outstanding {currency(report?.kpis?.ap_outstanding)}</span>
        </div>
      </section>

      <section className="section">
        <h2>Exceptions</h2>
        <table className="table dense-table">
          <thead><tr><th>Metric</th><th>Value</th></tr></thead>
          <tbody>
            {Object.entries(report?.exceptions || {}).map(([k, v]) => (
              <tr key={k}>
                <td>{k}</td>
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
          <p className="muted">Generated from posted journal entries, with cashflow transactions and operational subledgers shown as supporting schedules.</p>
          <div className="row wrap">
            <span className="badge">Period {statements?.period?.start_date || 'all'} to {statements?.period?.end_date || 'latest'}</span>
            <span className="badge">As of {statements?.period?.as_of_date || '-'}</span>
            <span className="badge">TB Balanced {String(!!statements?.trial_balance?.totals?.is_balanced)}</span>
            <span className="badge">BS Check {currency(statements?.balance_sheet?.totals?.balance_check)}</span>
          </div>
        </section>

        <div className="grid">
          <section className="section">
            <h2>Profit & Loss</h2>
            <div className="row wrap">
              <span className="badge">Revenue {currency(statements?.profit_and_loss?.totals?.revenue)}</span>
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
            <h2>Cash Flow</h2>
            <div className="row wrap">
              <span className="badge">Cash In {currency(statements?.cash_flow?.totals?.cash_in)}</span>
              <span className="badge">Cash Out {currency(statements?.cash_flow?.totals?.cash_out)}</span>
              <span className="badge">Net Cash Flow {currency(statements?.cash_flow?.totals?.net_cash_flow)}</span>
              <span className="badge">Transfers {currency(statements?.cash_flow?.transfers?.gross_transfer_amount)}</span>
            </div>
            <table className="table dense-table" style={{ marginTop: 10 }}>
              <thead><tr><th>Activity</th><th>Category</th><th>In</th><th>Out</th><th>Net</th></tr></thead>
              <tbody>
                {(statements?.cash_flow?.operating_activities || []).map((row) => (
                  <tr key={`cf-${row.activity}-${row.category}`}>
                    <td>{row.activity}</td>
                    <td>{row.category}</td>
                    <td>{currency(row.cash_in)}</td>
                    <td>{currency(row.cash_out)}</td>
                    <td>{currency(row.net)}</td>
                  </tr>
                ))}
                {!statements?.cash_flow?.operating_activities?.length && <tr><td colSpan="5" className="muted">No posted cash transactions in this period.</td></tr>}
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
          <h2>Add Settlement</h2>
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
            <button type="submit">Save Settlement</button>
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
    </div>
  );
}
