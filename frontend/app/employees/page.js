'use client';

import { useEffect, useMemo, useState } from 'react';
import LegacyExternalModuleNotice from '../../components/LegacyExternalModuleNotice';
import Drawer from '../../components/ui/Drawer';
import { useConfirmAction } from '../../components/ConfirmActionProvider';
import {
  createAttendance,
  createEmployee,
  deleteAttendance,
  deleteEmployee,
  fetchAttendance,
  fetchEmployees,
  updateEmployee,
} from '../../lib/api';

const EMPTY_EMPLOYEE = {
  full_name: '', department: '', job_title: '', compensation_type: 'Monthly', rate: '', daily_rate: '', hourly_rate: '',
};
const EMPTY_ATTENDANCE = {
  employee_id: '', work_date: '', time_in: '08:00', time_out: '17:00', overtime_hours: '0', night_diff_hours: '0', day_type: 'regular_day',
};

export default function EmployeesPage() {
  const confirmAction = useConfirmAction();
  const [employees, setEmployees] = useState([]);
  const [attendance, setAttendance] = useState([]);
  const [form, setForm] = useState(EMPTY_EMPLOYEE);
  const [initialForm, setInitialForm] = useState(EMPTY_EMPLOYEE);
  const [attForm, setAttForm] = useState(EMPTY_ATTENDANCE);
  const [editingId, setEditingId] = useState(null);
  const [employeeDrawerOpen, setEmployeeDrawerOpen] = useState(false);
  const [attendanceDrawerOpen, setAttendanceDrawerOpen] = useState(false);
  const [employeeSaving, setEmployeeSaving] = useState(false);
  const [attendanceSaving, setAttendanceSaving] = useState(false);
  const [employeeError, setEmployeeError] = useState('');
  const [attendanceError, setAttendanceError] = useState('');

  const employeeDirty = useMemo(() => JSON.stringify(form) !== JSON.stringify(initialForm), [form, initialForm]);
  const attendanceDirty = useMemo(() => JSON.stringify(attForm) !== JSON.stringify(EMPTY_ATTENDANCE), [attForm]);

  async function load() {
    setEmployees(await fetchEmployees());
    setAttendance(await fetchAttendance());
  }

  useEffect(() => { load().catch(console.error); }, []);

  function openNewEmployee() {
    setEditingId(null);
    setForm(EMPTY_EMPLOYEE);
    setInitialForm(EMPTY_EMPLOYEE);
    setEmployeeError('');
    setEmployeeDrawerOpen(true);
  }

  function closeEmployeeDrawer() {
    setEmployeeDrawerOpen(false);
    setEditingId(null);
    setForm(EMPTY_EMPLOYEE);
    setInitialForm(EMPTY_EMPLOYEE);
    setEmployeeError('');
  }

  function openAttendanceDrawer() {
    setAttForm(EMPTY_ATTENDANCE);
    setAttendanceError('');
    setAttendanceDrawerOpen(true);
  }

  function closeAttendanceDrawer() {
    setAttendanceDrawerOpen(false);
    setAttForm(EMPTY_ATTENDANCE);
    setAttendanceError('');
  }

  async function saveEmployee(e) {
    e.preventDefault();
    setEmployeeError('');
    setEmployeeSaving(true);
    try {
      const payload = {
        ...form,
        rate: Number(form.rate || 0),
        daily_rate: Number(form.daily_rate || 0),
        hourly_rate: Number(form.hourly_rate || 0),
      };
      if (editingId) await updateEmployee(editingId, payload);
      else await createEmployee(payload);
      closeEmployeeDrawer();
      await load();
    } catch (error) {
      setEmployeeError(error.message || 'The employee could not be saved.');
    } finally {
      setEmployeeSaving(false);
    }
  }

  async function saveAttendance(e) {
    e.preventDefault();
    setAttendanceError('');
    setAttendanceSaving(true);
    try {
      await createAttendance({
        ...attForm,
        employee_id: Number(attForm.employee_id),
        overtime_hours: Number(attForm.overtime_hours || 0),
        night_diff_hours: Number(attForm.night_diff_hours || 0),
      });
      closeAttendanceDrawer();
      await load();
    } catch (error) {
      setAttendanceError(error.message || 'The attendance entry could not be saved.');
    } finally {
      setAttendanceSaving(false);
    }
  }

  function startEdit(employee) {
    const nextForm = {
      full_name: employee.full_name,
      department: employee.department || '',
      job_title: employee.job_title || '',
      compensation_type: employee.compensation_type || 'Monthly',
      rate: employee.rate || '',
      daily_rate: employee.daily_rate || '',
      hourly_rate: employee.hourly_rate || '',
    };
    setEditingId(employee.id);
    setForm(nextForm);
    setInitialForm(nextForm);
    setEmployeeError('');
    setEmployeeDrawerOpen(true);
  }

  return (
    <div>
      <LegacyExternalModuleNotice appName="Staff & Payroll" />

      <section className="section">
        <h1>Employees & Attendance</h1>
        <p className="muted">Manage employee profiles and daily attendance without crowding the workspace.</p>
        <div className="ho-quick-actions">
          <button type="button" onClick={openNewEmployee}>Add Employee</button>
          <button type="button" className="secondary" onClick={openAttendanceDrawer}>Record Attendance</button>
        </div>
      </section>

      <section className="section">
        <div className="row wrap" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <div><h2>Employees</h2><p className="small muted">Current employee registry and compensation basis.</p></div>
          <button type="button" onClick={openNewEmployee}>Add Employee</button>
        </div>
        <div className="table-wrap" role="region" aria-label="Employees" tabIndex="0">
          <table className="table">
            <thead><tr><th>Name</th><th>Department</th><th>Job Title</th><th>Rate</th><th>Actions</th></tr></thead>
            <tbody>
              {employees.map((employee) => (
                <tr key={employee.id}>
                  <td><strong>{employee.full_name}</strong></td>
                  <td>{employee.department || '—'}</td>
                  <td>{employee.job_title || '—'}</td>
                  <td>{employee.rate}</td>
                  <td><div className="ho-table-actions">
                    <button className="secondary" onClick={() => startEdit(employee)}>Edit</button>
                    <button className="secondary" onClick={async () => {
                      if (await confirmAction({ title: `Delete employee ${employee.full_name}?`, description: 'Employee history may be needed for payroll review. Remove only profiles entered in error.' })) {
                        await deleteEmployee(employee.id); await load();
                      }
                    }}>Delete</button>
                  </div></td>
                </tr>
              ))}
              {!employees.length && <tr><td colSpan="5" className="muted">No employee records yet. Add an employee to begin.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <section className="section">
        <div className="row wrap" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <div><h2>Recent Attendance</h2><p className="small muted">Latest daily attendance entries used by payroll.</p></div>
          <button type="button" className="secondary" onClick={openAttendanceDrawer}>Record Attendance</button>
        </div>
        <div className="table-wrap" role="region" aria-label="Recent attendance" tabIndex="0">
          <table className="table">
            <thead><tr><th>Date</th><th>Employee</th><th>In</th><th>Out</th><th>OT</th><th>Actions</th></tr></thead>
            <tbody>
              {attendance.map((row) => (
                <tr key={row.id}>
                  <td>{row.work_date}</td><td>{employees.find((employee) => employee.id === row.employee_id)?.full_name || row.employee_id}</td><td>{row.time_in}</td><td>{row.time_out}</td><td>{row.overtime_hours}</td>
                  <td><div className="ho-table-actions"><button className="secondary" onClick={async () => {
                    if (await confirmAction({ title: 'Delete this attendance entry?', description: 'This can change payroll calculations for the affected employee.' })) {
                      await deleteAttendance(row.id); await load();
                    }
                  }}>Delete</button></div></td>
                </tr>
              ))}
              {!attendance.length && <tr><td colSpan="6" className="muted">No attendance records yet. Record attendance when a shift is completed.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <Drawer
        open={employeeDrawerOpen}
        onClose={closeEmployeeDrawer}
        title={editingId ? 'Edit employee' : 'Add employee'}
        description="Maintain operational identity, department, role, and compensation basis."
        busy={employeeSaving}
        dirty={employeeDirty}
        footer={(
          <>
            <button type="button" className="secondary" onClick={closeEmployeeDrawer} disabled={employeeSaving}>Cancel</button>
            <button type="submit" form="employee-form" disabled={employeeSaving}>{employeeSaving ? 'Saving…' : editingId ? 'Update Employee' : 'Save Employee'}</button>
          </>
        )}
      >
        <form id="employee-form" onSubmit={saveEmployee}>
          {employeeError ? <div className="ho-notice ho-notice--danger" role="alert">{employeeError}</div> : null}
          <div className="form-grid">
            <label>Name<input data-drawer-autofocus required value={form.full_name} onChange={(e) => setForm((value) => ({ ...value, full_name: e.target.value }))} /></label>
            <label>Department<input value={form.department} onChange={(e) => setForm((value) => ({ ...value, department: e.target.value }))} /></label>
            <label>Job Title<input value={form.job_title} onChange={(e) => setForm((value) => ({ ...value, job_title: e.target.value }))} /></label>
            <label>Compensation Type<select value={form.compensation_type} onChange={(e) => setForm((value) => ({ ...value, compensation_type: e.target.value }))}><option>Monthly</option><option>Daily</option><option>Hourly</option></select></label>
            <label>Monthly / Rate<input type="number" step="0.01" min="0" value={form.rate} onChange={(e) => setForm((value) => ({ ...value, rate: e.target.value }))} /></label>
            <label>Daily Rate<input type="number" step="0.01" min="0" value={form.daily_rate} onChange={(e) => setForm((value) => ({ ...value, daily_rate: e.target.value }))} /></label>
            <label>Hourly Rate<input type="number" step="0.01" min="0" value={form.hourly_rate} onChange={(e) => setForm((value) => ({ ...value, hourly_rate: e.target.value }))} /></label>
          </div>
        </form>
      </Drawer>

      <Drawer
        open={attendanceDrawerOpen}
        onClose={closeAttendanceDrawer}
        title="Record attendance"
        description="Add a daily time record and payroll-relevant hours."
        busy={attendanceSaving}
        dirty={attendanceDirty}
        footer={(
          <>
            <button type="button" className="secondary" onClick={closeAttendanceDrawer} disabled={attendanceSaving}>Cancel</button>
            <button type="submit" form="attendance-form" disabled={attendanceSaving}>{attendanceSaving ? 'Saving…' : 'Save Attendance'}</button>
          </>
        )}
      >
        <form id="attendance-form" onSubmit={saveAttendance}>
          {attendanceError ? <div className="ho-notice ho-notice--danger" role="alert">{attendanceError}</div> : null}
          <div className="form-grid">
            <label>Employee<select data-drawer-autofocus required value={attForm.employee_id} onChange={(e) => setAttForm((value) => ({ ...value, employee_id: e.target.value }))}><option value="">Select employee</option>{employees.map((employee) => <option key={employee.id} value={employee.id}>{employee.full_name}</option>)}</select></label>
            <label>Date<input required type="date" value={attForm.work_date} onChange={(e) => setAttForm((value) => ({ ...value, work_date: e.target.value }))} /></label>
            <label>Time In<input type="time" value={attForm.time_in} onChange={(e) => setAttForm((value) => ({ ...value, time_in: e.target.value }))} /></label>
            <label>Time Out<input type="time" value={attForm.time_out} onChange={(e) => setAttForm((value) => ({ ...value, time_out: e.target.value }))} /></label>
            <label>OT Hours<input type="number" step="0.01" min="0" value={attForm.overtime_hours} onChange={(e) => setAttForm((value) => ({ ...value, overtime_hours: e.target.value }))} /></label>
            <label>Night Differential Hours<input type="number" step="0.01" min="0" value={attForm.night_diff_hours} onChange={(e) => setAttForm((value) => ({ ...value, night_diff_hours: e.target.value }))} /></label>
            <label>Day Type<select value={attForm.day_type} onChange={(e) => setAttForm((value) => ({ ...value, day_type: e.target.value }))}><option value="regular_day">Regular day</option><option value="rest_day">Rest day</option><option value="holiday">Holiday</option></select></label>
          </div>
        </form>
      </Drawer>
    </div>
  );
}
