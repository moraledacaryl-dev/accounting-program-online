'use client';
import { useEffect, useState } from 'react';
import {
  createAttendance,
  createEmployee,
  deleteAttendance,
  deleteEmployee,
  fetchAttendance,
  fetchEmployees,
  updateEmployee,
} from '../../lib/api';

export default function EmployeesPage() {
  const [employees, setEmployees] = useState([]);
  const [attendance, setAttendance] = useState([]);
  const [form, setForm] = useState({
    full_name: '',
    department: '',
    job_title: '',
    compensation_type: 'Monthly',
    rate: '',
    daily_rate: '',
    hourly_rate: '',
  });
  const [attForm, setAttForm] = useState({
    employee_id: '',
    work_date: '',
    time_in: '08:00',
    time_out: '17:00',
    overtime_hours: '0',
    night_diff_hours: '0',
    day_type: 'regular_day',
  });
  const [editingId, setEditingId] = useState(null);

  async function load() {
    setEmployees(await fetchEmployees());
    setAttendance(await fetchAttendance());
  }

  useEffect(() => {
    load().catch(console.error);
  }, []);

  async function saveEmployee(e) {
    e.preventDefault();
    const payload = {
      ...form,
      rate: Number(form.rate || 0),
      daily_rate: Number(form.daily_rate || 0),
      hourly_rate: Number(form.hourly_rate || 0),
    };
    if (editingId) await updateEmployee(editingId, payload);
    else await createEmployee(payload);
    setEditingId(null);
    setForm({
      full_name: '',
      department: '',
      job_title: '',
      compensation_type: 'Monthly',
      rate: '',
      daily_rate: '',
      hourly_rate: '',
    });
    await load();
  }

  async function saveAttendance(e) {
    e.preventDefault();
    await createAttendance({
      ...attForm,
      employee_id: Number(attForm.employee_id),
      overtime_hours: Number(attForm.overtime_hours || 0),
      night_diff_hours: Number(attForm.night_diff_hours || 0),
    });
    setAttForm({
      employee_id: '',
      work_date: '',
      time_in: '08:00',
      time_out: '17:00',
      overtime_hours: '0',
      night_diff_hours: '0',
      day_type: 'regular_day',
    });
    await load();
  }

  return (
    <div>
      <section className="section">
        <h1>Employees & Attendance</h1>
        <p className="muted">Manage employee profiles and daily attendance in one place.</p>
      </section>

      <div className="grid">
        <section className="section">
          <h2>{editingId ? 'Edit Employee' : 'Add Employee'}</h2>
          <form onSubmit={saveEmployee}>
            <div className="form-grid">
              <label>Name<input required value={form.full_name} onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))} /></label>
              <label>Department<input value={form.department} onChange={e => setForm(f => ({ ...f, department: e.target.value }))} /></label>
              <label>Job Title<input value={form.job_title} onChange={e => setForm(f => ({ ...f, job_title: e.target.value }))} /></label>
              <label>Comp Type<select value={form.compensation_type} onChange={e => setForm(f => ({ ...f, compensation_type: e.target.value }))}><option>Monthly</option><option>Daily</option><option>Hourly</option></select></label>
              <label>Monthly / Rate<input type="number" step="0.01" inputMode="decimal" min="0" value={form.rate} onChange={e => setForm(f => ({ ...f, rate: e.target.value }))} /></label>
              <label>Daily Rate<input type="number" step="0.01" inputMode="decimal" min="0" value={form.daily_rate} onChange={e => setForm(f => ({ ...f, daily_rate: e.target.value }))} /></label>
              <label>Hourly Rate<input type="number" step="0.01" inputMode="decimal" min="0" value={form.hourly_rate} onChange={e => setForm(f => ({ ...f, hourly_rate: e.target.value }))} /></label>
            </div>
            <div className="row wrap">
              <button type="submit">{editingId ? 'Update' : 'Save'}</button>
              {editingId && <button type="button" className="secondary" onClick={() => { setEditingId(null); setForm({ full_name: '', department: '', job_title: '', compensation_type: 'Monthly', rate: '', daily_rate: '', hourly_rate: '' }); }}>Cancel</button>}
            </div>
          </form>
        </section>

        <section className="section">
          <h2>Add Attendance</h2>
          <form onSubmit={saveAttendance}>
            <div className="form-grid">
              <label>Employee<select required value={attForm.employee_id} onChange={e => setAttForm(f => ({ ...f, employee_id: e.target.value }))}><option value="">Select</option>{employees.map(e => <option key={e.id} value={e.id}>{e.full_name}</option>)}</select></label>
              <label>Date<input required type="date" value={attForm.work_date} onChange={e => setAttForm(f => ({ ...f, work_date: e.target.value }))} /></label>
              <label>Time In<input type="time" value={attForm.time_in} onChange={e => setAttForm(f => ({ ...f, time_in: e.target.value }))} /></label>
              <label>Time Out<input type="time" value={attForm.time_out} onChange={e => setAttForm(f => ({ ...f, time_out: e.target.value }))} /></label>
              <label>OT Hours<input type="number" step="0.01" inputMode="decimal" min="0" value={attForm.overtime_hours} onChange={e => setAttForm(f => ({ ...f, overtime_hours: e.target.value }))} /></label>
              <label>ND Hours<input type="number" step="0.01" inputMode="decimal" min="0" value={attForm.night_diff_hours} onChange={e => setAttForm(f => ({ ...f, night_diff_hours: e.target.value }))} /></label>
              <label>Day Type<select value={attForm.day_type} onChange={e => setAttForm(f => ({ ...f, day_type: e.target.value }))}><option value="regular_day">regular_day</option><option value="rest_day">rest_day</option><option value="holiday">holiday</option></select></label>
            </div>
            <button type="submit">Save Attendance</button>
          </form>
        </section>
      </div>

      <section className="section">
        <h2>Employees</h2>
        <table className="table">
          <thead><tr><th>Name</th><th>Department</th><th>Rate</th><th></th></tr></thead>
          <tbody>
            {employees.map(e => (
              <tr key={e.id}>
                <td>{e.full_name}</td>
                <td>{e.department}</td>
                <td>{e.rate}</td>
                <td className="row wrap">
                  <button className="secondary" onClick={() => { setEditingId(e.id); setForm({ full_name: e.full_name, department: e.department || '', job_title: e.job_title || '', compensation_type: e.compensation_type || 'Monthly', rate: e.rate || '', daily_rate: e.daily_rate || '', hourly_rate: e.hourly_rate || '' }); }}>Edit</button>
                  <button className="secondary" onClick={async () => { if (confirm('Delete employee?')) { await deleteEmployee(e.id); await load(); } }}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="section">
        <h2>Recent Attendance</h2>
        <table className="table">
          <thead><tr><th>Date</th><th>Employee ID</th><th>In</th><th>Out</th><th>OT</th><th></th></tr></thead>
          <tbody>
            {attendance.map(a => (
              <tr key={a.id}>
                <td>{a.work_date}</td>
                <td>{a.employee_id}</td>
                <td>{a.time_in}</td>
                <td>{a.time_out}</td>
                <td>{a.overtime_hours}</td>
                <td><button className="secondary" onClick={async () => { await deleteAttendance(a.id); await load(); }}>Delete</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
