'use client';
import LegacyExternalModuleNotice from '../../components/LegacyExternalModuleNotice';

import { useEffect, useMemo, useState } from 'react';
import {
  createAttendance,
  deleteAttendance,
  fetchAttendance,
  fetchEmployees,
  fetchPayrollPeriods,
  importAttendance,
  updateAttendance,
} from '../../lib/api';
import { shouldPreventEnterSubmit } from '../../lib/formBehavior';
import { useConfirmAction } from '../../components/ConfirmActionProvider';

const EMPTY_FORM = {
  employee_id: '',
  work_date: '',
  time_in: '08:00',
  time_out: '17:00',
  late_minutes: '0',
  undertime_minutes: '0',
  overtime_hours: '0',
  night_diff_hours: '0',
  day_type: 'regular_day',
  is_absent: false,
  leave_type: '',
  notes: '',
};

function asNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function toPayload(form) {
  return {
    employee_id: Number(form.employee_id),
    work_date: form.work_date,
    time_in: form.is_absent ? null : (form.time_in || null),
    time_out: form.is_absent ? null : (form.time_out || null),
    late_minutes: asNumber(form.late_minutes, 0),
    undertime_minutes: asNumber(form.undertime_minutes, 0),
    overtime_hours: asNumber(form.overtime_hours, 0),
    night_diff_hours: asNumber(form.night_diff_hours, 0),
    day_type: form.day_type,
    is_absent: !!form.is_absent,
    leave_type: form.leave_type || null,
    notes: form.notes || null,
  };
}

function parseBulkCsv(text) {
  const lines = String(text || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (!lines.length) return [];

  const hasHeader = lines[0].toLowerCase().includes('employee_id');
  const rows = hasHeader ? lines.slice(1) : lines;

  return rows.map((line, idx) => {
    const cols = line.split(',').map((cell) => cell.trim());
    if (cols.length < 2) {
      throw new Error(`Invalid CSV row at line ${hasHeader ? idx + 2 : idx + 1}.`);
    }
    return {
      employee_id: Number(cols[0]),
      work_date: cols[1] || '',
      time_in: cols[2] || null,
      time_out: cols[3] || null,
      late_minutes: asNumber(cols[4], 0),
      undertime_minutes: asNumber(cols[5], 0),
      overtime_hours: asNumber(cols[6], 0),
      night_diff_hours: asNumber(cols[7], 0),
      day_type: cols[8] || 'regular_day',
      is_absent: String(cols[9] || '').toLowerCase() === 'true',
      leave_type: cols[10] || null,
      notes: cols[11] || null,
    };
  });
}

export default function AttendancePage() {
  const confirmAction = useConfirmAction();
  const [employees, setEmployees] = useState([]);
  const [periods, setPeriods] = useState([]);
  const [rows, setRows] = useState([]);

  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [bulkText, setBulkText] = useState('');

  const [employeeFilter, setEmployeeFilter] = useState('');
  const [periodFilter, setPeriodFilter] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const employeeMap = useMemo(
    () => Object.fromEntries(employees.map((row) => [row.id, row.full_name])),
    [employees],
  );

  async function load() {
    const [employeeResult, periodResult, attendanceResult] = await Promise.allSettled([
      fetchEmployees(),
      fetchPayrollPeriods({ limit: 100 }),
      fetchAttendance({
        employee_id: employeeFilter || undefined,
        payroll_period_id: periodFilter || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      }),
    ]);
    if (employeeResult.status === 'fulfilled') setEmployees(Array.isArray(employeeResult.value) ? employeeResult.value : []);
    else setEmployees([]);
    if (periodResult.status === 'fulfilled') setPeriods(Array.isArray(periodResult.value) ? periodResult.value : []);
    else setPeriods([]);
    if (attendanceResult.status === 'fulfilled') setRows(Array.isArray(attendanceResult.value) ? attendanceResult.value : []);
    else throw attendanceResult.reason;
  }

  useEffect(() => {
    load().catch((err) => setError(err.message || 'Failed to load attendance.'));
  }, [employeeFilter, periodFilter, startDate, endDate]);

  function resetForm() {
    setEditingId(null);
    setForm({ ...EMPTY_FORM, work_date: form.work_date || '' });
  }

  function editRow(row) {
    setEditingId(row.id);
    setForm({
      employee_id: String(row.employee_id || ''),
      work_date: row.work_date || '',
      time_in: row.time_in || '08:00',
      time_out: row.time_out || '17:00',
      late_minutes: String(row.late_minutes ?? '0'),
      undertime_minutes: String(row.undertime_minutes ?? '0'),
      overtime_hours: String(row.overtime_hours ?? '0'),
      night_diff_hours: String(row.night_diff_hours ?? '0'),
      day_type: row.day_type || 'regular_day',
      is_absent: !!row.is_absent,
      leave_type: row.leave_type || '',
      notes: row.notes || '',
    });
  }

  function isSubmittable() {
    return !!(Number(form.employee_id || 0) > 0 && form.work_date);
  }

  async function submit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    if (!isSubmittable()) {
      setError('Employee and work date are required.');
      return;
    }
    try {
      const payload = toPayload(form);
      if (editingId) {
        await updateAttendance(editingId, payload);
        setNotice('Attendance updated.');
      } else {
        await createAttendance(payload);
        setNotice('Attendance saved.');
      }
      resetForm();
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save attendance.');
    }
  }

  async function saveBulk() {
    setError('');
    setNotice('');
    try {
      const entries = parseBulkCsv(bulkText);
      if (!entries.length) {
        setError('Add CSV rows first.');
        return;
      }
      if (entries.some((row) => !Number.isFinite(Number(row.employee_id)) || !row.work_date)) {
        setError('Bulk import rows require employee_id and work_date.');
        return;
      }
      await importAttendance(entries);
      setNotice(`Imported ${entries.length} attendance rows.`);
      setBulkText('');
      await load();
    } catch (err) {
      setError(err.message || 'Failed to import attendance.');
    }
  }

  async function remove(id) {
    if (!await confirmAction({ title: 'Delete this attendance entry?', description: 'This can change payroll calculations for the affected employee.' })) return;
    setError('');
    setNotice('');
    try {
      await deleteAttendance(id);
      setNotice('Attendance entry deleted.');
      if (editingId === id) resetForm();
      await load();
    } catch (err) {
      setError(err.message || 'Failed to delete attendance entry.');
    }
  }

  return (
    <div>
      <LegacyExternalModuleNotice appName="Staff & Payroll" />
      <div className="stack">
      <section className="section">
        <h1>Attendance</h1>
        <p className="muted">Attendance input with employee/date filters and payroll-period-aware review.</p>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <section className="section">
        <div className="row wrap" style={{ justifyContent: 'space-between' }}>
          <h2>Filters</h2>
          <button type="button" className="secondary" onClick={() => { setEmployeeFilter(''); setPeriodFilter(''); setStartDate(''); setEndDate(''); }}>
            Clear Filters
          </button>
        </div>
        <div className="form-grid">
          <label>
            Employee
            <select value={employeeFilter} onChange={(e) => setEmployeeFilter(e.target.value)}>
              <option value="">All</option>
              {employees.map((emp) => (
                <option key={emp.id} value={emp.id}>{emp.full_name}</option>
              ))}
            </select>
          </label>
          <label>
            Payroll Period
            <select value={periodFilter} onChange={(e) => setPeriodFilter(e.target.value)}>
              <option value="">All</option>
              {periods.map((period) => (
                <option key={period.id} value={period.id}>
                  {period.name || `Period #${period.id}`} ({period.period_start} to {period.period_end})
                </option>
              ))}
            </select>
          </label>
          <label>
            Start Date
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          </label>
          <label>
            End Date
            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
          </label>
        </div>
      </section>

      <section className="section">
        <h2>{editingId ? `Edit Attendance #${editingId}` : 'Add Attendance'}</h2>
        <form onSubmit={submit} onKeyDown={(event) => shouldPreventEnterSubmit(event, isSubmittable)}>
          <div className="form-grid">
            <label>
              Employee
              <select required value={form.employee_id} onChange={(e) => setForm((f) => ({ ...f, employee_id: e.target.value }))}>
                <option value="">Select employee</option>
                {employees.map((emp) => (
                  <option key={emp.id} value={emp.id}>{emp.full_name}</option>
                ))}
              </select>
            </label>
            <label>
              Work Date
              <input required type="date" value={form.work_date} onChange={(e) => setForm((f) => ({ ...f, work_date: e.target.value }))} />
            </label>
            <label>
              Day Type
              <select value={form.day_type} onChange={(e) => setForm((f) => ({ ...f, day_type: e.target.value }))}>
                <option value="regular_day">regular_day</option>
                <option value="rest_day">rest_day</option>
                <option value="holiday">holiday</option>
              </select>
            </label>

            <label>
              Is Absent
              <select value={String(form.is_absent)} onChange={(e) => setForm((f) => ({ ...f, is_absent: e.target.value === 'true' }))}>
                <option value="false">false</option>
                <option value="true">true</option>
              </select>
            </label>
            <label>
              Time In
              <input type="time" value={form.time_in} onChange={(e) => setForm((f) => ({ ...f, time_in: e.target.value }))} disabled={form.is_absent} />
            </label>
            <label>
              Time Out
              <input type="time" value={form.time_out} onChange={(e) => setForm((f) => ({ ...f, time_out: e.target.value }))} disabled={form.is_absent} />
            </label>

            <label>
              Late (mins)
              <input type="number" min="0" step="1" value={form.late_minutes} onChange={(e) => setForm((f) => ({ ...f, late_minutes: e.target.value }))} />
            </label>
            <label>
              Undertime (mins)
              <input type="number" min="0" step="1" value={form.undertime_minutes} onChange={(e) => setForm((f) => ({ ...f, undertime_minutes: e.target.value }))} />
            </label>
            <label>
              OT Hours
              <input type="number" min="0" step="0.01" value={form.overtime_hours} onChange={(e) => setForm((f) => ({ ...f, overtime_hours: e.target.value }))} />
            </label>

            <label>
              Night Diff Hours
              <input type="number" min="0" step="0.01" value={form.night_diff_hours} onChange={(e) => setForm((f) => ({ ...f, night_diff_hours: e.target.value }))} />
            </label>
            <label>
              Leave Type
              <input value={form.leave_type} onChange={(e) => setForm((f) => ({ ...f, leave_type: e.target.value }))} placeholder="Optional" />
            </label>
          </div>
          <label>
            Notes
            <textarea value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} />
          </label>
          <div className="row wrap">
            <button type="submit">{editingId ? 'Update Attendance' : 'Save Attendance'}</button>
            {editingId && <button type="button" className="secondary" onClick={resetForm}>Cancel</button>}
          </div>
        </form>
      </section>

      <section className="section">
        <h2>Bulk Import (CSV)</h2>
        <p className="small muted">Format: employee_id,work_date,time_in,time_out,late_minutes,undertime_minutes,overtime_hours,night_diff_hours,day_type,is_absent,leave_type,notes</p>
        <textarea
          rows={6}
          value={bulkText}
          onChange={(e) => setBulkText(e.target.value)}
          placeholder="employee_id,work_date,time_in,time_out,late_minutes,undertime_minutes,overtime_hours,night_diff_hours,day_type,is_absent,leave_type,notes"
        />
        <div className="row wrap" style={{ marginTop: 10 }}>
          <button type="button" onClick={saveBulk}>Import Rows</button>
        </div>
      </section>

      <section className="section">
        <h2>Entries</h2>
        <table className="table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Employee</th>
              <th>Day Type</th>
              <th>In</th>
              <th>Out</th>
              <th>Late</th>
              <th>UT</th>
              <th>OT</th>
              <th>ND</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.work_date}</td>
                <td>{employeeMap[row.employee_id] || `#${row.employee_id}`}</td>
                <td>{row.day_type}</td>
                <td>{row.time_in || '-'}</td>
                <td>{row.time_out || '-'}</td>
                <td>{row.late_minutes}</td>
                <td>{row.undertime_minutes}</td>
                <td>{row.overtime_hours}</td>
                <td>{row.night_diff_hours}</td>
                <td className="row wrap">
                  <button className="secondary" type="button" onClick={() => editRow(row)}>Edit</button>
                  <button className="secondary" type="button" onClick={() => remove(row.id)}>Delete</button>
                </td>
              </tr>
            ))}
            {!rows.length && (
              <tr>
                <td colSpan="10" className="muted">No attendance entries yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
      </div>
    </div>
  );
}