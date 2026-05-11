'use client';

import { useEffect, useMemo, useState } from 'react';
import { createUser, fetchRoles, fetchUsers, updateUser } from '../../lib/api';
import { shouldPreventEnterSubmit } from '../../lib/formBehavior';

const EMPTY_FORM = {
  username: '',
  password: '',
  full_name: '',
  role: 'staff',
  role_ids: [],
  is_active: true,
};

export default function UsersPage() {
  const [rows, setRows] = useState([]);
  const [roles, setRoles] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function load() {
    const [userData, roleData] = await Promise.all([fetchUsers(), fetchRoles(true)]);
    setRows(Array.isArray(userData) ? userData : []);
    setRoles(Array.isArray(roleData) ? roleData : []);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || 'Failed to load users.'));
  }, []);

  const roleById = useMemo(() => {
    const map = new Map();
    for (const row of roles) map.set(row.id, row);
    return map;
  }, [roles]);

  function toggleRole(roleId) {
    setForm((prev) => {
      const set = new Set(prev.role_ids || []);
      if (set.has(roleId)) set.delete(roleId);
      else set.add(roleId);
      return { ...prev, role_ids: [...set] };
    });
  }

  async function submit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      const payload = {
        username: form.username,
        password: form.password || undefined,
        full_name: form.full_name || null,
        role: form.role || 'staff',
        role_ids: (form.role_ids || []).map((value) => Number(value)).filter(Boolean),
        is_active: !!form.is_active,
      };

      if (editingId) {
        await updateUser(editingId, payload);
        setNotice('User updated.');
      } else {
        if (!payload.password) {
          setError('Password is required for new users.');
          return;
        }
        await createUser(payload);
        setNotice('User created.');
      }

      setEditingId(null);
      setForm({ ...EMPTY_FORM });
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save user.');
    }
  }

  function isSubmittable() {
    if (!String(form.username || '').trim()) return false;
    if (!editingId && !String(form.password || '').trim()) return false;
    return true;
  }

  function editUser(row) {
    setEditingId(row.id);
    setForm({
      username: row.username,
      password: '',
      full_name: row.full_name || '',
      role: row.role || 'staff',
      role_ids: (row.role_ids || []).map((value) => Number(value)),
      is_active: !!row.is_active,
    });
  }

  function resetForm() {
    setEditingId(null);
    setForm({ ...EMPTY_FORM });
  }

  return (
    <div className="stack">
      <section className="section">
        <h1>Users</h1>
        <p className="muted">Manage user accounts and assign one or more roles.</p>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <div className="grid">
        <section className="section">
          <h2>{editingId ? `Edit User #${editingId}` : 'Create User'}</h2>
          <form onSubmit={submit} className="stack" onKeyDown={(event) => shouldPreventEnterSubmit(event, isSubmittable)}>
            <div className="form-grid">
              <label>Username
                <input
                  required
                  autoComplete="username"
                  value={form.username}
                  onChange={(e) => setForm((prev) => ({ ...prev, username: e.target.value }))}
                  disabled={!!editingId}
                />
              </label>
              <label>Password
                <input
                  type="password"
                  autoComplete="new-password"
                  value={form.password}
                  onChange={(e) => setForm((prev) => ({ ...prev, password: e.target.value }))}
                  placeholder={editingId ? 'Leave blank to keep current' : 'Required'}
                />
              </label>
              <label>Full Name
                <input value={form.full_name} onChange={(e) => setForm((prev) => ({ ...prev, full_name: e.target.value }))} />
              </label>
              <label>Legacy Role
                <select value={form.role} onChange={(e) => setForm((prev) => ({ ...prev, role: e.target.value }))}>
                  <option value="admin">admin</option>
                  <option value="owner">owner</option>
                  <option value="manager">manager</option>
                  <option value="accountant">accountant</option>
                  <option value="staff">staff</option>
                </select>
              </label>
              <label>Active
                <select value={String(form.is_active)} onChange={(e) => setForm((prev) => ({ ...prev, is_active: e.target.value === 'true' }))}>
                  <option value="true">Active</option>
                  <option value="false">Inactive</option>
                </select>
              </label>
            </div>

            <div className="section" style={{ marginBottom: 0 }}>
              <h3>Role Assignments</h3>
              <div className="row wrap">
                {roles.map((role) => (
                  <label key={role.id} className="row" style={{ gap: 6 }}>
                    <input
                      type="checkbox"
                      checked={(form.role_ids || []).includes(role.id)}
                      onChange={() => toggleRole(role.id)}
                    />
                    <span className="small">{role.name}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="row wrap">
              <button type="submit">{editingId ? 'Update User' : 'Create User'}</button>
              {editingId && <button type="button" className="secondary" onClick={resetForm}>Cancel</button>}
            </div>
          </form>
        </section>

        <section className="section">
          <h2>User List</h2>
          <table className="table">
            <thead><tr><th>User</th><th>Legacy</th><th>Assigned Roles</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.username}<br /><span className="small muted">{row.full_name || '-'}</span></td>
                  <td>{row.role || '-'}</td>
                  <td>
                    {(row.roles || []).length
                      ? row.roles.map((item) => roleById.get(item.id)?.name || item.name || item.code).join(', ')
                      : '-'}
                  </td>
                  <td>{row.is_active ? 'Active' : 'Inactive'}</td>
                  <td><button type="button" className="secondary" onClick={() => editUser(row)}>Edit</button></td>
                </tr>
              ))}
              {!rows.length && <tr><td colSpan="5" className="muted">No users found.</td></tr>}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}
