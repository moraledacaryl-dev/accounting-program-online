'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  assignUserRoles,
  createRole,
  deleteRole,
  fetchPermissions,
  fetchRoles,
  fetchUsers,
  updateRole,
  updateRolePermissions,
} from '../../lib/api';
import { useConfirmAction } from '../../components/ConfirmActionProvider';

const EMPTY_ROLE_FORM = { code: '', name: '', description: '', is_active: true };

function groupPermissions(rows) {
  const groups = {};
  for (const row of rows || []) {
    const group = row.group_name || 'Other';
    if (!groups[group]) groups[group] = [];
    groups[group].push(row);
  }
  for (const key of Object.keys(groups)) {
    groups[key].sort((a, b) => String(a.label || a.key || '').localeCompare(String(b.label || b.key || '')));
  }
  return groups;
}

export default function RolesPermissionsPage() {
  const confirmAction = useConfirmAction();
  const [roles, setRoles] = useState([]);
  const [permissions, setPermissions] = useState([]);
  const [users, setUsers] = useState([]);
  const [selectedRoleId, setSelectedRoleId] = useState(null);
  const [roleForm, setRoleForm] = useState({ ...EMPTY_ROLE_FORM });
  const [selectedPermissionKeys, setSelectedPermissionKeys] = useState(new Set());
  const [roleSearch, setRoleSearch] = useState('');
  const [permissionSearch, setPermissionSearch] = useState('');
  const [userRoleDraft, setUserRoleDraft] = useState({});
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function load() {
    const [roleRows, permissionRows, userRows] = await Promise.all([
      fetchRoles(false),
      fetchPermissions(),
      fetchUsers(),
    ]);
    const sortedRoles = (Array.isArray(roleRows) ? roleRows : []).sort((a, b) => String(a.name || '').localeCompare(String(b.name || '')));
    setRoles(sortedRoles);
    setPermissions(Array.isArray(permissionRows) ? permissionRows : []);
    setUsers(Array.isArray(userRows) ? userRows : []);
    setUserRoleDraft(() => {
      const next = {};
      for (const row of (Array.isArray(userRows) ? userRows : [])) next[row.id] = Array.isArray(row.role_ids) ? [...row.role_ids] : [];
      return next;
    });
    if (sortedRoles.length && !selectedRoleId) chooseRoleFromRows(sortedRoles[0], false);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || 'Failed to load roles and permissions.'));
  }, []);

  const selectedRole = useMemo(() => roles.find((row) => row.id === selectedRoleId) || null, [roles, selectedRoleId]);
  const filteredRoles = useMemo(() => {
    const q = roleSearch.trim().toLowerCase();
    if (!q) return roles;
    return roles.filter((row) => `${row.code || ''} ${row.name || ''}`.toLowerCase().includes(q));
  }, [roles, roleSearch]);

  const filteredPermissions = useMemo(() => {
    const q = permissionSearch.trim().toLowerCase();
    if (!q) return permissions;
    return permissions.filter((row) => `${row.group_name || ''} ${row.label || ''} ${row.key || ''}`.toLowerCase().includes(q));
  }, [permissions, permissionSearch]);

  const groupedPermissions = useMemo(() => groupPermissions(filteredPermissions), [filteredPermissions]);
  const roleById = useMemo(() => new Map(roles.map((row) => [row.id, row])), [roles]);

  function chooseRoleFromRows(role, clearNotice = true) {
    if (!role) return;
    setSelectedRoleId(role.id);
    setRoleForm({
      code: role.code || '',
      name: role.name || '',
      description: role.description || '',
      is_active: !!role.is_active,
    });
    setSelectedPermissionKeys(new Set(role.permission_keys || []));
    if (clearNotice) {
      setError('');
      setNotice('');
    }
  }

  function chooseRole(roleId) {
    chooseRoleFromRows(roles.find((row) => row.id === roleId));
  }

  function startNewRole() {
    setSelectedRoleId(null);
    setRoleForm({ ...EMPTY_ROLE_FORM });
    setSelectedPermissionKeys(new Set());
    setNotice('');
    setError('');
  }

  function togglePermission(key) {
    setSelectedPermissionKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }

  function toggleGroup(groupName, enable) {
    const keys = (groupedPermissions[groupName] || []).map((row) => row.key);
    setSelectedPermissionKeys((prev) => {
      const next = new Set(prev);
      for (const key of keys) enable ? next.add(key) : next.delete(key);
      return next;
    });
  }

  function copyFromRole(copyRoleId) {
    const source = roleById.get(Number(copyRoleId));
    if (!source) return;
    setSelectedPermissionKeys(new Set(source.permission_keys || []));
    setNotice(`Copied permissions from ${source.name}.`);
  }

  async function saveRoleMeta() {
    setError(''); setNotice('');
    try {
      if (!selectedRoleId) return setError('Select a role first.');
      await updateRole(selectedRoleId, {
        code: roleForm.code,
        name: roleForm.name,
        description: roleForm.description || null,
        is_active: !!roleForm.is_active,
      });
      setNotice('Role details updated.');
      await load();
    } catch (err) {
      setError(err.message || 'Failed to update role.');
    }
  }

  async function saveRolePermissions() {
    setError(''); setNotice('');
    try {
      if (!selectedRoleId) return setError('Select a role first.');
      await updateRolePermissions(selectedRoleId, [...selectedPermissionKeys]);
      setNotice('Role permissions saved.');
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save role permissions.');
    }
  }

  async function createNewRole() {
    setError(''); setNotice('');
    try {
      const created = await createRole({
        code: roleForm.code,
        name: roleForm.name,
        description: roleForm.description || null,
        is_active: !!roleForm.is_active,
      });
      setNotice(`Role ${created.name} created.`);
      await load();
      chooseRole(created.id);
    } catch (err) {
      setError(err.message || 'Failed to create role.');
    }
  }

  async function removeRole() {
    if (!selectedRole) return;
    if (!await confirmAction({ title: `Delete role ${selectedRole.name}?`, description: 'Users assigned only to this role may lose access until another role is assigned.' })) return;
    setError(''); setNotice('');
    try {
      await deleteRole(selectedRole.id);
      setNotice('Role deleted.');
      setSelectedRoleId(null);
      setRoleForm({ ...EMPTY_ROLE_FORM });
      setSelectedPermissionKeys(new Set());
      await load();
    } catch (err) {
      setError(err.message || 'Failed to delete role.');
    }
  }

  async function saveUserRoles(userId) {
    setError(''); setNotice('');
    try {
      const roleIds = (userRoleDraft[userId] || []).map(Number).filter(Boolean);
      await assignUserRoles(userId, roleIds);
      setNotice('User roles updated.');
      await load();
    } catch (err) {
      setError(err.message || 'Failed to update user roles.');
    }
  }

  function toggleUserRole(userId, roleId) {
    setUserRoleDraft((prev) => {
      const current = new Set(prev[userId] || []);
      if (current.has(roleId)) current.delete(roleId); else current.add(roleId);
      return { ...prev, [userId]: [...current] };
    });
  }

  return (
    <div className="stack">
      <section className="section" style={{ paddingBottom: 14 }}>
        <div className="row wrap" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h1>Roles & Permissions</h1>
            <p className="muted">Control workspace access without losing context in a wall of checkboxes.</p>
          </div>
          <div className="row wrap">
            <span className="badge">{roles.length} roles</span>
            <span className="badge">{permissions.length} permissions</span>
            <span className="badge">{users.length} users</span>
          </div>
        </div>
        {!!notice && <p className="success-text" style={{ marginTop: 10 }}>{notice}</p>}
        {!!error && <p className="error-text" style={{ marginTop: 10 }}>{error}</p>}
      </section>

      <div className="grid-30-70" style={{ alignItems: 'start' }}>
        <aside className="section role-list-panel" style={{ position: 'sticky', top: 76, padding: 12 }}>
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
            <h2 style={{ margin: 0 }}>Roles</h2>
            <button type="button" className="secondary" onClick={startNewRole}>New</button>
          </div>
          <input
            type="search"
            aria-label="Search roles"
            placeholder="Search roles…"
            value={roleSearch}
            onChange={(e) => setRoleSearch(e.target.value)}
            data-enter-context="search"
          />
          <div className="stack role-list" style={{ gap: 6, marginTop: 8 }}>
            {filteredRoles.map((row) => (
              <button
                type="button"
                key={row.id}
                className={selectedRoleId === row.id ? 'tab active full-width role-chip' : 'tab full-width role-chip'}
                onClick={() => chooseRole(row.id)}
              >
                <span style={{ textAlign: 'left' }}>{row.name}<br /><span className="small muted">{row.code}</span></span>
                <span className="small muted">{row.permission_count || 0}</span>
              </button>
            ))}
          </div>
          {!filteredRoles.length && <p className="muted small" style={{ marginTop: 8 }}>No matching roles.</p>}
        </aside>

        <main className="stack">
          <section className="section">
            <div className="row wrap" style={{ justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
              <div>
                <h2 style={{ marginBottom: 2 }}>{selectedRole ? selectedRole.name : 'Create role'}</h2>
                <p className="small muted">Identity, status, and role description</p>
              </div>
              {selectedRole && <button type="button" className="secondary" onClick={removeRole}>Delete Role</button>}
            </div>

            <div className="form-grid">
              <label>Code<input value={roleForm.code} onChange={(e) => setRoleForm((prev) => ({ ...prev, code: e.target.value }))} /></label>
              <label>Name<input value={roleForm.name} onChange={(e) => setRoleForm((prev) => ({ ...prev, name: e.target.value }))} /></label>
              <label>Status
                <select value={String(roleForm.is_active)} onChange={(e) => setRoleForm((prev) => ({ ...prev, is_active: e.target.value === 'true' }))}>
                  <option value="true">Active</option>
                  <option value="false">Inactive</option>
                </select>
              </label>
            </div>
            <label>Description<textarea rows="2" value={roleForm.description} onChange={(e) => setRoleForm((prev) => ({ ...prev, description: e.target.value }))} /></label>
            <div className="row" style={{ justifyContent: 'flex-end', marginTop: 12 }}>
              {!selectedRole
                ? <button type="button" onClick={createNewRole}>Create Role</button>
                : <button type="button" onClick={saveRoleMeta}>Save Role Details</button>}
            </div>
          </section>

          {!!selectedRole && (
            <section className="section" style={{ padding: 0, overflow: 'hidden' }}>
              <div className="row wrap" style={{ justifyContent: 'space-between', alignItems: 'center', padding: '12px 14px', borderBottom: '1px solid var(--line)' }}>
                <div>
                  <h2 style={{ marginBottom: 2 }}>Permissions</h2>
                  <p className="small muted">{selectedPermissionKeys.size} selected</p>
                </div>
                <div className="row wrap">
                  <input
                    type="search"
                    aria-label="Search permissions"
                    placeholder="Search permissions…"
                    value={permissionSearch}
                    onChange={(e) => setPermissionSearch(e.target.value)}
                    style={{ width: 220 }}
                  />
                  <select aria-label="Copy permissions from role" defaultValue="" onChange={(e) => copyFromRole(e.target.value)}>
                    <option value="">Copy from role…</option>
                    {roles.filter((row) => row.id !== selectedRole.id).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
                  </select>
                </div>
              </div>

              <div className="stack" style={{ gap: 8, padding: 12 }}>
                {Object.entries(groupedPermissions).map(([groupName, groupRows], index) => {
                  const checkedCount = groupRows.filter((row) => selectedPermissionKeys.has(row.key)).length;
                  const allChecked = groupRows.length > 0 && checkedCount === groupRows.length;
                  return (
                    <details key={groupName} open={index === 0 || !!permissionSearch} className="section" style={{ margin: 0, padding: 0, overflow: 'hidden' }}>
                      <summary style={{ cursor: 'pointer', padding: '10px 12px', listStyle: 'none' }}>
                        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
                          <div><strong>{groupName}</strong><span className="small muted" style={{ marginLeft: 8 }}>{checkedCount}/{groupRows.length}</span></div>
                          <button type="button" className="secondary" onClick={(e) => { e.preventDefault(); toggleGroup(groupName, !allChecked); }}>
                            {allChecked ? 'Clear group' : 'Select group'}
                          </button>
                        </div>
                      </summary>
                      <div className="form-grid" style={{ gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', padding: '0 12px 12px' }}>
                        {groupRows.map((perm) => (
                          <label key={perm.key} className="toggle-field" style={{ alignItems: 'flex-start' }}>
                            <div>
                              <div className="toggle-label">{perm.label || perm.key}</div>
                              <div className="toggle-hint">{perm.key}</div>
                            </div>
                            <input type="checkbox" checked={selectedPermissionKeys.has(perm.key)} onChange={() => togglePermission(perm.key)} />
                          </label>
                        ))}
                      </div>
                    </details>
                  );
                })}
                {!Object.keys(groupedPermissions).length && <p className="muted">No permissions match your search.</p>}
              </div>

              <div className="row" style={{ position: 'sticky', bottom: 0, justifyContent: 'flex-end', padding: '10px 14px', borderTop: '1px solid var(--line)', background: 'var(--surface)' }}>
                <button type="button" onClick={saveRolePermissions}>Save Permissions</button>
              </div>
            </section>
          )}
        </main>
      </div>

      <section className="section" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--line)' }}>
          <h2 style={{ marginBottom: 2 }}>User Role Assignments</h2>
          <p className="small muted">Assign roles without leaving this administration workspace.</p>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table className="table" style={{ margin: 0 }}>
            <thead><tr><th>User</th><th>Legacy Role</th><th>Assigned Roles</th><th style={{ textAlign: 'right' }}>Action</th></tr></thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td><strong>{user.username}</strong><br /><span className="small muted">{user.full_name || '-'}</span></td>
                  <td>{user.role || '-'}</td>
                  <td>
                    <div className="row wrap" style={{ gap: 8 }}>
                      {roles.map((role) => (
                        <label key={`${user.id}-${role.id}`} className="row" style={{ gap: 5 }}>
                          <input type="checkbox" checked={(userRoleDraft[user.id] || []).includes(role.id)} onChange={() => toggleUserRole(user.id, role.id)} />
                          <span className="small">{role.name}</span>
                        </label>
                      ))}
                    </div>
                  </td>
                  <td style={{ textAlign: 'right' }}><button type="button" className="secondary" onClick={() => saveUserRoles(user.id)}>Save</button></td>
                </tr>
              ))}
              {!users.length && <tr><td colSpan="4" className="muted">No users found.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
