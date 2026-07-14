'use client';
import LegacyExternalModuleNotice from '../../components/LegacyExternalModuleNotice';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import {
  createPayrollPeriod,
  fetchPayrollPeriods,
  importPayrollPeriodLines,
} from '../../lib/api';
import { shouldPreventEnterSubmit } from '../../lib/formBehavior';

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

const EMPTY_PERIOD = {
  name: '',
  period_start: '',
  period_end: '',
  release_date: '',
  status: 'draft',
  source_type: 'manual',
  notes: '',
  lines: [{ ...EMPTY_LINE }],
};

function php(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function toNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
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
    for (let j = 0; j < header.length; j += 1) {
      row[header[j]] = cells[j] ?? '';
    }
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

export default function PayrollPeriodsPage() {
  const [rows, setRows] = useState([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [form, setForm] = useState({ ...EMPTY_PERIOD });
  const [importForm, setImportForm] = useState({
    payroll_period_id: '',
    file_name: 'payroll-import.csv',
    notes: '',
    csv_text: '',
  });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function load() {
    const data = await fetchPayrollPeriods({ status: statusFilter || undefined });
    setRows(Array.isArray(data) ? data : []);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || 'Failed to load payroll periods.'));
  }, [statusFilter]);

  const totals = useMemo(() => {
    return rows.reduce((acc, row) => {
      acc.gross += Number(row.gross_total || 0);
      acc.net += Number(row.net_total || 0);
      acc.deductions += Number(row.deductions_total || 0);
      return acc;
    }, { gross: 0, net: 0, deductions: 0 });
  }, [rows]);

  function updateLine(index, patch) {
    setForm((prev) => ({
      ...prev,
      lines: prev.lines.map((line, i) => (i === index ? { ...line, ...patch } : line)),
    }));
  }

  function addLine() {
    setForm((prev) => ({ ...prev, lines: [...prev.lines, { ...EMPTY_LINE }] }));
  }

  function removeLine(index) {
    setForm((prev) => {
      const nextLines = prev.lines.filter((_, i) => i !== index);
      return {
        ...prev,
        lines: nextLines.length ? nextLines : [{ ...EMPTY_LINE }],
      };
    });
  }

  function isPeriodSubmittable() {
    return form.lines.some((line) => String(line.employee_name || '').trim());
  }

  function isImportSubmittable() {
    return String(importForm.csv_text || '').trim().length > 0;
  }

  async function submitPeriod(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      const payload = {
        name: form.name || null,
        period_start: form.period_start || null,
        period_end: form.period_end || null,
        release_date: form.release_date || null,
        status: form.status,
        source_type: form.source_type,
        notes: form.notes || null,
        lines: form.lines
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
          .filter((line) => line.employee_name),
      };
      if (!payload.lines.length) {
        setError('Add at least one employee payroll line.');
        return;
      }
      await createPayrollPeriod(payload);
      setNotice('Payroll period created.');
      setForm({ ...EMPTY_PERIOD });
      await load();
    } catch (err) {
      setError(err.message || 'Failed to create payroll period.');
    }
  }

  async function submitImport(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      const lines = parseImportCsv(importForm.csv_text);
      if (!lines.length) {
        setError('No payroll lines parsed from import text. Add CSV rows under the sample header.');
        return;
      }
      await importPayrollPeriodLines({
        payroll_period_id: importForm.payroll_period_id ? Number(importForm.payroll_period_id) : null,
        file_name: importForm.file_name || 'payroll-import.csv',
        status: 'imported',
        notes: importForm.notes || null,
        lines,
      });
      setNotice('Payroll import completed.');
      setImportForm((prev) => ({ ...prev, csv_text: '' }));
      await load();
    } catch (err) {
      setError(err.message || 'Failed to import payroll lines.');
    }
  }

  return (
    <div>
      <LegacyExternalModuleNotice appName="Staff & Payroll" />
      <div className="stack">
      <section className="section">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h1>Payroll Periods</h1>
            <p className="muted">Main payroll workflow: period input/import, posting, and reporting.</p>
          </div>
          <label style={{ minWidth: 200 }}>
            Status Filter
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All</option>
              <option value="draft">draft</option>
              <option value="reviewed">reviewed</option>
              <option value="posted">posted</option>
            </select>
          </label>
        </div>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <div className="card-grid">
        <section className="card stat-card"><div className="small muted">Periods</div><div className="kpi">{rows.length}</div></section>
        <section className="card stat-card"><div className="small muted">Gross Total</div><div className="kpi">{php(totals.gross)}</div></section>
        <section className="card stat-card"><div className="small muted">Net Total</div><div className="kpi">{php(totals.net)}</div></section>
        <section className="card stat-card"><div className="small muted">Deductions Total</div><div className="kpi">{php(totals.deductions)}</div></section>
      </div>

      <section className="section">
        <h2>Create Payroll Period</h2>
        <form onSubmit={submitPeriod} className="stack" onKeyDown={(event) => shouldPreventEnterSubmit(event, isPeriodSubmittable)}>
          <div className="form-grid">
            <label>Name<input value={form.name} onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))} placeholder="Payroll 1-15" /></label>
            <label>Period Start<input type="date" value={form.period_start} onChange={(e) => setForm((prev) => ({ ...prev, period_start: e.target.value }))} /></label>
            <label>Period End<input type="date" value={form.period_end} onChange={(e) => setForm((prev) => ({ ...prev, period_end: e.target.value }))} /></label>
            <label>Release Date<input type="date" value={form.release_date} onChange={(e) => setForm((prev) => ({ ...prev, release_date: e.target.value }))} /></label>
            <label>Status
              <select value={form.status} onChange={(e) => setForm((prev) => ({ ...prev, status: e.target.value }))}>
                <option value="draft">draft</option>
                <option value="reviewed">reviewed</option>
                <option value="posted">posted</option>
              </select>
            </label>
            <label>Source
              <select value={form.source_type} onChange={(e) => setForm((prev) => ({ ...prev, source_type: e.target.value }))}>
                <option value="manual">manual</option>
                <option value="import">import</option>
                <option value="external">external</option>
              </select>
            </label>
          </div>

          <div className="section" style={{ marginBottom: 0 }}>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <h3>Employee Lines</h3>
              <button type="button" className="secondary" onClick={addLine}>Add Line</button>
            </div>
            {form.lines.map((line, index) => (
              <div key={`line-${index}`} className="form-grid" style={{ marginTop: 10 }} data-enter-context="line-item">
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
          </div>

          <label>Notes<textarea value={form.notes} onChange={(e) => setForm((prev) => ({ ...prev, notes: e.target.value }))} /></label>
          <div className="row wrap">
            <button type="submit">Create Payroll Period</button>
            <button type="button" className="secondary" onClick={() => setForm({ ...EMPTY_PERIOD })}>Clear</button>
          </div>
        </form>
      </section>

      <section className="section">
        <h2>Import Payroll Lines (CSV Text)</h2>
        <p className="small muted">Header sample: employee_name,department,regular_amount,overtime_amount,holiday_amount,night_diff_amount,allowances,deductions,employer_contribution,gross_pay,net_pay,notes</p>
        <form onSubmit={submitImport} className="stack" onKeyDown={(event) => shouldPreventEnterSubmit(event, isImportSubmittable)}>
          <div className="form-grid">
            <label>Target Period (optional)
              <select value={importForm.payroll_period_id} onChange={(e) => setImportForm((prev) => ({ ...prev, payroll_period_id: e.target.value }))}>
                <option value="">Create new period automatically</option>
                {rows.map((row) => <option key={row.id} value={row.id}>{row.name || `Period ${row.id}`}</option>)}
              </select>
            </label>
            <label>File Name<input value={importForm.file_name} onChange={(e) => setImportForm((prev) => ({ ...prev, file_name: e.target.value }))} /></label>
          </div>
          <label>Import Notes<textarea value={importForm.notes} onChange={(e) => setImportForm((prev) => ({ ...prev, notes: e.target.value }))} /></label>
          <label>CSV Content<textarea value={importForm.csv_text} onChange={(e) => setImportForm((prev) => ({ ...prev, csv_text: e.target.value }))} /></label>
          <button type="submit">Import Payroll Lines</button>
        </form>
      </section>

      <section className="section">
        <h2>Payroll Period List</h2>
        <table className="table">
          <thead><tr><th>Name</th><th>Period</th><th>Status</th><th>Lines</th><th>Gross</th><th>Net</th><th></th></tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.name || `Payroll Period ${row.id}`}</td>
                <td>{row.period_start || '-'} → {row.period_end || '-'}</td>
                <td>{row.status}</td>
                <td>{row.line_count || 0}</td>
                <td>{php(row.gross_total || 0)}</td>
                <td>{php(row.net_total || 0)}</td>
                <td><Link className="button-link secondary-link" href={`/payroll-periods/${row.id}`}>Open</Link></td>
              </tr>
            ))}
            {!rows.length && <tr><td colSpan="7" className="muted">No payroll periods yet.</td></tr>}
          </tbody>
        </table>
      </section>
      </div>
    </div>
  );
}