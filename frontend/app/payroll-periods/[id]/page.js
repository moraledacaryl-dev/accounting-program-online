'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import {
  deletePayrollPeriod,
  fetchPayrollPeriod,
  importPayrollPeriodLines,
  postPayrollPeriod,
  updatePayrollPeriod,
} from '../../../lib/api';
import { useConfirmAction } from '../../../components/ConfirmActionProvider';

const EMPTY_LINE = {
  employee_id: '',
  employee_name: '',
  department: '',
  regular_hours: '0',
  overtime_hours: '0',
  regular_holiday_hours: '0',
  special_holiday_hours: '0',
  night_diff_hours: '0',
  regular_amount: '0',
  overtime_amount: '0',
  holiday_amount: '0',
  night_diff_amount: '0',
  allowances: '0',
  deductions: '0',
  employer_contribution: '0',
  gross_pay: '0',
  net_pay: '0',
  notes: '',
};

function toNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function php(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function parseImportCsv(text) {
  const rows = String(text || '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
  if (!rows.length) return [];
  const header = rows[0].split(',').map((col) => col.trim().toLowerCase());
  const out = [];
  for (let i = 1; i < rows.length; i += 1) {
    const cells = rows[i].split(',').map((c) => c.trim());
    const row = {};
    for (let j = 0; j < header.length; j += 1) row[header[j]] = cells[j] ?? '';
    if (!row.employee_name) continue;
    out.push({
      employee_id: row.employee_id ? Number(row.employee_id) : null,
      employee_name: row.employee_name,
      department: row.department || null,
      regular_hours: toNumber(row.regular_hours, 0),
      overtime_hours: toNumber(row.overtime_hours, 0),
      regular_holiday_hours: toNumber(row.regular_holiday_hours, 0),
      special_holiday_hours: toNumber(row.special_holiday_hours, 0),
      night_diff_hours: toNumber(row.night_diff_hours, 0),
      regular_amount: toNumber(row.regular_amount, 0),
      overtime_amount: toNumber(row.overtime_amount, 0),
      holiday_amount: toNumber(row.holiday_amount, 0),
      night_diff_amount: toNumber(row.night_diff_amount, 0),
      allowances: toNumber(row.allowances, 0),
      deductions: toNumber(row.deductions, 0),
      employer_contribution: toNumber(row.employer_contribution, 0),
      gross_pay: toNumber(row.gross_pay, 0),
      net_pay: toNumber(row.net_pay, 0),
      notes: row.notes || null,
    });
  }
  return out;
}

export default function PayrollPeriodDetailPage({ params }) {
  const confirmAction = useConfirmAction();
  const periodId = Number(params.id);
  const [activeTab, setActiveTab] = useState('summary');
  const [period, setPeriod] = useState(null);
  const [metaForm, setMetaForm] = useState({
    name: '',
    period_start: '',
    period_end: '',
    release_date: '',
    status: 'draft',
    source_type: 'manual',
    notes: '',
  });
  const [lines, setLines] = useState([{ ...EMPTY_LINE }]);
  const [importText, setImportText] = useState('');
  const [postDate, setPostDate] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function load() {
    const row = await fetchPayrollPeriod(periodId);
    setPeriod(row || null);
    setMetaForm({
      name: row?.name || '',
      period_start: row?.period_start || '',
      period_end: row?.period_end || '',
      release_date: row?.release_date || '',
      status: row?.status || 'draft',
      source_type: row?.source_type || 'manual',
      notes: row?.notes || '',
    });
    const lineRows = (row?.lines || []).map((line) => ({
      employee_id: line.employee_id ? String(line.employee_id) : '',
      employee_name: line.employee_name || '',
      department: line.department || '',
      regular_hours: String(line.regular_hours ?? '0'),
      overtime_hours: String(line.overtime_hours ?? '0'),
      regular_holiday_hours: String(line.regular_holiday_hours ?? '0'),
      special_holiday_hours: String(line.special_holiday_hours ?? '0'),
      night_diff_hours: String(line.night_diff_hours ?? '0'),
      regular_amount: String(line.regular_amount ?? '0'),
      overtime_amount: String(line.overtime_amount ?? '0'),
      holiday_amount: String(line.holiday_amount ?? '0'),
      night_diff_amount: String(line.night_diff_amount ?? '0'),
      allowances: String(line.allowances ?? '0'),
      deductions: String(line.deductions ?? '0'),
      employer_contribution: String(line.employer_contribution ?? '0'),
      gross_pay: String(line.gross_pay ?? '0'),
      net_pay: String(line.net_pay ?? '0'),
      notes: line.notes || '',
    }));
    setLines(lineRows.length ? lineRows : [{ ...EMPTY_LINE }]);
  }

  useEffect(() => {
    if (!periodId) return;
    load().catch((e) => setError(e.message || 'Failed to load payroll period.'));
  }, [periodId]);

  const totals = useMemo(() => {
    return {
      gross: Number(period?.gross_total || 0),
      net: Number(period?.net_total || 0),
      deductions: Number(period?.deductions_total || 0),
      employer: Number(period?.employer_contribution_total || 0),
    };
  }, [period]);

  function updateLine(index, patch) {
    setLines((prev) => prev.map((line, i) => (i === index ? { ...line, ...patch } : line)));
  }

  function addLine() {
    setLines((prev) => [...prev, { ...EMPTY_LINE }]);
  }

  function removeLine(index) {
    setLines((prev) => {
      const next = prev.filter((_, i) => i !== index);
      return next.length ? next : [{ ...EMPTY_LINE }];
    });
  }

  async function saveMeta() {
    setError('');
    setNotice('');
    try {
      await updatePayrollPeriod(periodId, {
        name: metaForm.name || null,
        period_start: metaForm.period_start || null,
        period_end: metaForm.period_end || null,
        release_date: metaForm.release_date || null,
        status: metaForm.status,
        source_type: metaForm.source_type,
        notes: metaForm.notes || null,
      });
      setNotice('Payroll period info updated.');
      await load();
    } catch (err) {
      setError(err.message || 'Failed to update payroll period.');
    }
  }

  async function saveLines() {
    setError('');
    setNotice('');
    try {
      const payloadLines = lines
        .map((line) => ({
          employee_id: line.employee_id ? Number(line.employee_id) : null,
          employee_name: line.employee_name || null,
          department: line.department || null,
          regular_hours: toNumber(line.regular_hours, 0),
          overtime_hours: toNumber(line.overtime_hours, 0),
          regular_holiday_hours: toNumber(line.regular_holiday_hours, 0),
          special_holiday_hours: toNumber(line.special_holiday_hours, 0),
          night_diff_hours: toNumber(line.night_diff_hours, 0),
          regular_amount: toNumber(line.regular_amount, 0),
          overtime_amount: toNumber(line.overtime_amount, 0),
          holiday_amount: toNumber(line.holiday_amount, 0),
          night_diff_amount: toNumber(line.night_diff_amount, 0),
          allowances: toNumber(line.allowances, 0),
          deductions: toNumber(line.deductions, 0),
          employer_contribution: toNumber(line.employer_contribution, 0),
          gross_pay: toNumber(line.gross_pay, 0),
          net_pay: toNumber(line.net_pay, 0),
          notes: line.notes || null,
        }))
        .filter((line) => line.employee_name);

      if (!payloadLines.length) {
        setError('Add at least one employee line.');
        return;
      }

      await updatePayrollPeriod(periodId, { lines: payloadLines });
      setNotice('Payroll period lines saved.');
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save payroll lines.');
    }
  }

  async function runImport() {
    setError('');
    setNotice('');
    try {
      const parsed = parseImportCsv(importText);
      if (!parsed.length) {
        setError('No import rows parsed. Check CSV text and header.');
        return;
      }
      await importPayrollPeriodLines({
        payroll_period_id: periodId,
        file_name: `payroll-period-${periodId}-import.csv`,
        status: 'imported',
        notes: 'Imported from payroll period detail page',
        lines: parsed,
      });
      setNotice('Import completed for this payroll period.');
      setImportText('');
      await load();
    } catch (err) {
      setError(err.message || 'Failed to import payroll lines.');
    }
  }

  async function runPost() {
    setError('');
    setNotice('');
    try {
      const res = await postPayrollPeriod(periodId, { post_date: postDate || null });
      setNotice(`Payroll period posted to journal ${res?.journal?.reference_no || ''}.`);
      await load();
    } catch (err) {
      setError(err.message || 'Failed to post payroll period.');
    }
  }

  async function removePeriod() {
    if (!await confirmAction({ title: `Delete payroll period ${period?.name || periodId}?`, description: 'Only draft payroll periods entered in error should be removed. Posted periods should remain for audit review.' })) return;
    setError('');
    try {
      await deletePayrollPeriod(periodId);
      if (typeof window !== 'undefined') window.location.href = '/payroll-periods';
    } catch (err) {
      setError(err.message || 'Failed to delete payroll period.');
    }
  }

  if (error && !period) {
    return (
      <section className="section">
        <h1>Payroll Period</h1>
        <p className="error-text">{error}</p>
        <Link className="button-link secondary-link" href="/payroll-periods">Back</Link>
      </section>
    );
  }

  if (!period) {
    return (
      <section className="section">
        <h1>Payroll Period</h1>
        <p className="muted">Loading payroll period…</p>
      </section>
    );
  }

  return (
    <div className="stack">
      <section className="section">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h1>{period.name || `Payroll Period ${period.id}`}</h1>
            <p className="muted">Period {period.period_start || '-'} → {period.period_end || '-'} · Status {period.status}</p>
          </div>
          <div className="row wrap">
            <Link className="button-link secondary-link" href="/payroll-periods">Back</Link>
            <button type="button" className="secondary" onClick={removePeriod}>Delete Period</button>
          </div>
        </div>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}

        <div className="tabs">
          <button type="button" className={activeTab === 'summary' ? 'tab active' : 'tab'} onClick={() => setActiveTab('summary')}>Summary</button>
          <button type="button" className={activeTab === 'input' ? 'tab active' : 'tab'} onClick={() => setActiveTab('input')}>Employee Input</button>
          <button type="button" className={activeTab === 'import' ? 'tab active' : 'tab'} onClick={() => setActiveTab('import')}>Import</button>
          <button type="button" className={activeTab === 'posting' ? 'tab active' : 'tab'} onClick={() => setActiveTab('posting')}>Posting</button>
          <button type="button" className={activeTab === 'reports' ? 'tab active' : 'tab'} onClick={() => setActiveTab('reports')}>Reports</button>
        </div>
      </section>

      {activeTab === 'summary' && (
        <>
          <div className="card-grid">
            <section className="card stat-card"><div className="small muted">Line Count</div><div className="kpi">{period.line_count || 0}</div></section>
            <section className="card stat-card"><div className="small muted">Gross</div><div className="kpi">{php(totals.gross)}</div></section>
            <section className="card stat-card"><div className="small muted">Net</div><div className="kpi">{php(totals.net)}</div></section>
            <section className="card stat-card"><div className="small muted">Deductions</div><div className="kpi">{php(totals.deductions)}</div></section>
          </div>

          <section className="section">
            <h2>Period Info</h2>
            <div className="form-grid">
              <label>Name<input value={metaForm.name} onChange={(e) => setMetaForm((prev) => ({ ...prev, name: e.target.value }))} /></label>
              <label>Period Start<input type="date" value={metaForm.period_start} onChange={(e) => setMetaForm((prev) => ({ ...prev, period_start: e.target.value }))} /></label>
              <label>Period End<input type="date" value={metaForm.period_end} onChange={(e) => setMetaForm((prev) => ({ ...prev, period_end: e.target.value }))} /></label>
              <label>Release Date<input type="date" value={metaForm.release_date} onChange={(e) => setMetaForm((prev) => ({ ...prev, release_date: e.target.value }))} /></label>
              <label>Status
                <select value={metaForm.status} onChange={(e) => setMetaForm((prev) => ({ ...prev, status: e.target.value }))}>
                  <option value="draft">draft</option>
                  <option value="reviewed">reviewed</option>
                  <option value="posted">posted</option>
                </select>
              </label>
              <label>Source
                <select value={metaForm.source_type} onChange={(e) => setMetaForm((prev) => ({ ...prev, source_type: e.target.value }))}>
                  <option value="manual">manual</option>
                  <option value="import">import</option>
                  <option value="external">external</option>
                </select>
              </label>
            </div>
            <label>Notes<textarea value={metaForm.notes} onChange={(e) => setMetaForm((prev) => ({ ...prev, notes: e.target.value }))} /></label>
            <button type="button" onClick={saveMeta}>Save Period Info</button>
          </section>
        </>
      )}

      {activeTab === 'input' && (
        <section className="section">
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <h2>Employee Input</h2>
            <button type="button" className="secondary" onClick={addLine}>Add Line</button>
          </div>
          {lines.map((line, index) => (
            <div key={`line-${index}`} className="form-grid" style={{ marginTop: 10 }}>
              <label>Employee Name<input value={line.employee_name} onChange={(e) => updateLine(index, { employee_name: e.target.value })} /></label>
              <label>Department<input value={line.department} onChange={(e) => updateLine(index, { department: e.target.value })} /></label>
              <label>Regular Amount<input type="number" step="0.01" value={line.regular_amount} onChange={(e) => updateLine(index, { regular_amount: e.target.value })} /></label>
              <label>OT Amount<input type="number" step="0.01" value={line.overtime_amount} onChange={(e) => updateLine(index, { overtime_amount: e.target.value })} /></label>
              <label>Holiday Amount<input type="number" step="0.01" value={line.holiday_amount} onChange={(e) => updateLine(index, { holiday_amount: e.target.value })} /></label>
              <label>Night Diff<input type="number" step="0.01" value={line.night_diff_amount} onChange={(e) => updateLine(index, { night_diff_amount: e.target.value })} /></label>
              <label>Allowances<input type="number" step="0.01" value={line.allowances} onChange={(e) => updateLine(index, { allowances: e.target.value })} /></label>
              <label>Deductions<input type="number" step="0.01" value={line.deductions} onChange={(e) => updateLine(index, { deductions: e.target.value })} /></label>
              <label>Employer Contribution<input type="number" step="0.01" value={line.employer_contribution} onChange={(e) => updateLine(index, { employer_contribution: e.target.value })} /></label>
              <label>Gross Pay<input type="number" step="0.01" value={line.gross_pay} onChange={(e) => updateLine(index, { gross_pay: e.target.value })} /></label>
              <label>Net Pay<input type="number" step="0.01" value={line.net_pay} onChange={(e) => updateLine(index, { net_pay: e.target.value })} /></label>
              <div className="row" style={{ alignItems: 'end' }}>
                <button type="button" className="secondary" onClick={() => removeLine(index)}>Remove</button>
              </div>
            </div>
          ))}
          <div className="row wrap" style={{ marginTop: 10 }}>
            <button type="button" onClick={saveLines}>Save Employee Input</button>
          </div>
        </section>
      )}

      {activeTab === 'import' && (
        <section className="section">
          <h2>Import</h2>
          <p className="small muted">Header: employee_name,department,regular_amount,overtime_amount,holiday_amount,night_diff_amount,allowances,deductions,employer_contribution,gross_pay,net_pay,notes</p>
          <label>CSV Content<textarea value={importText} onChange={(e) => setImportText(e.target.value)} /></label>
          <button type="button" onClick={runImport}>Import to This Period</button>

          <h3 style={{ marginTop: 16 }}>Import Batches</h3>
          <table className="table">
            <thead><tr><th>File</th><th>Rows</th><th>Status</th><th>By</th><th>Date</th></tr></thead>
            <tbody>
              {(period.imports || []).map((row) => (
                <tr key={row.id}>
                  <td>{row.file_name}</td>
                  <td>{row.row_count || 0}</td>
                  <td>{row.status}</td>
                  <td>{row.imported_by || '-'}</td>
                  <td>{row.created_at ? String(row.created_at).slice(0, 10) : '-'}</td>
                </tr>
              ))}
              {!(period.imports || []).length && <tr><td colSpan="5" className="muted">No imports yet.</td></tr>}
            </tbody>
          </table>
        </section>
      )}

      {activeTab === 'posting' && (
        <section className="section">
          <h2>Posting</h2>
          <div className="form-grid">
            <label>Post Date (optional)
              <input type="date" value={postDate} onChange={(e) => setPostDate(e.target.value)} />
            </label>
            <label>Generated Journal Entry ID
              <input value={period.generated_journal_entry_id || ''} readOnly />
            </label>
          </div>
          <div className="row wrap">
            <button type="button" onClick={runPost}>Post Payroll to Journal</button>
          </div>
          <p className="small muted">Posted periods should be treated as final unless reopened by accounting control policy.</p>
        </section>
      )}

      {activeTab === 'reports' && (
        <section className="section">
          <h2>Reports</h2>
          <table className="table">
            <thead><tr><th>Employee</th><th>Department</th><th>Gross</th><th>Deductions</th><th>Net</th><th>Employer Contribution</th></tr></thead>
            <tbody>
              {(period.lines || []).map((line) => (
                <tr key={line.id}>
                  <td>{line.employee_name}</td>
                  <td>{line.department || '-'}</td>
                  <td>{php(line.gross_pay || 0)}</td>
                  <td>{php(line.deductions || 0)}</td>
                  <td>{php(line.net_pay || 0)}</td>
                  <td>{php(line.employer_contribution || 0)}</td>
                </tr>
              ))}
              {!(period.lines || []).length && <tr><td colSpan="6" className="muted">No payroll lines yet.</td></tr>}
            </tbody>
            <tfoot>
              <tr>
                <th colSpan="2">Totals</th>
                <th>{php(totals.gross)}</th>
                <th>{php(totals.deductions)}</th>
                <th>{php(totals.net)}</th>
                <th>{php(totals.employer)}</th>
              </tr>
            </tfoot>
          </table>
        </section>
      )}
    </div>
  );
}
