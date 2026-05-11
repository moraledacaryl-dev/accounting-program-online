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

const EMPTY_ROLE_FORM = {
  code: '',
  name: '',
  description: '',
  is_active: true,
};

function groupPermissions(rows) {
  const groups = {};
  for (const row of rows || []) {
    const group = row.group_name || 'Other';
    if (!groups[group]) groups[group] = [];
    groups[group].push(row);
  }
  for (const key of Object.keys(groups)) {
    groups[key].sort((a, b) => String(a.key || '').localeCompare(String(b.key || '')));
  }
  return groups;
}

export default function RolesPermissionsPage() {
  const [roles, setRoles] = useState([]);
  const [permissions, setPermissions] = useState([]);
  const [users, setUsers] = useState([]);

  const [selectedRoleId, setSelectedRoleId] = useState(null);
  const [roleForm, setRoleForm] = useState({ ...EMPTY_ROLE_FORM });
  const [selectedPermissionKeys, setSelectedPermissionKeys] = useState(new Set());
  const [roleSearch, setRoleSearch] = useState('');

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
      for (const row of (Array.isArray(userRows) ? userRows : [])) {
        next[row.id] = Array.isArray(row.role_ids) ? [...row.role_ids] : [];
      }
      return next;
    });

    if (sortedRoles.length && !selectedRoleId) {
      const first = sortedRoles[0];
      setSelectedRoleId(first.id);
      setRoleForm({
        code: first.code || '',
        name: first.name || '',
        description: first.description || '',
        is_active: !!first.is_active,
      });
      setSelectedPermissionKeys(new Set(first.permission_keys || []));
    }
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || 'Failed to load roles and permissions.'));
  }, []);

  const selectedRole = useMemo(() => roles.find((row) => row.id === selectedRoleId) || null, [roles, selectedRoleId]);
  const filteredRoles = useMemo(() => {
    const q = String(roleSearch || '').trim().toLowerCase();
    if (!q) return roles;
    return roles.filter((row) => {
      const code = String(row.code || '').toLowerCase();
      const name = String(row.name || '').toLowerCase();
      return code.includes(q) || name.includes(q);
    });
  }, [roles, roleSearch]);
  const groupedPermissions = useMemo(() => groupPermissions(permissions), [permissions]);
  const roleById = useMemo(() => {
    const map = new Map();
    for (const row of roles) map.set(row.id, row);
    return map;
  }, [roles]);

  function chooseRole(roleId) {
    const role = roles.find((row) => row.id === roleId);
    if (!role) return;
    setSelectedRoleId(role.id);
    setRoleForm({
      code: role.code || '',
      name: role.name || '',
      description: role.description || '',
      is_active: !!role.is_active,
    });
    setSelectedPermissionKeys(new Set(role.permission_keys || []));
  }

  function togglePermission(key) {
    setSelectedPermissionKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function toggleGroup(groupName, enable) {
    const keys = (groupedPermissions[groupName] || []).map((row) => row.key);
    setSelectedPermissionKeys((prev) => {
      const next = new Set(prev);
      for (const key of keys) {
        if (enable) next.add(key);
        else next.delete(key);
      }
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
    setError('');
    setNotice('');
    try {
      if (!selectedRoleId) {
        setError('Select a role first.');
        return;
      }
      await updateRole(selectedRoleId, {
        code: roleForm.code,
        name: roleForm.name,
        description: roleForm.description || null,
        is_active: !!roleForm.is_active,
      });
      setNotice('Role details updated.');
      await load();
      chooseRole(selectedRoleId);
    } catch (err) {
      setError(err.message || 'Failed to update role.');
    }
  }

  async function saveRolePermissions() {
    setError('');
    setNotice('');
    try {
      if (!selectedRoleId) {
        setError('Select a role first.');
        return;
      }
      await updateRolePermissions(selectedRoleId, [...selectedPermissionKeys]);
      setNotice('Role permissions saved.');
      await load();
      chooseRole(selectedRoleId);
    } catch (err) {
      setError(err.message || 'Failed to save role permissions.');
    }
  }

  async function createNewRole() {
    setError('');
    setNotice('');
    try {
      const payload = {
        code: roleForm.code,
        name: roleForm.name,
        description: roleForm.description || null,
        is_active: !!roleForm.is_active,
      };
      const created = await createRole(payload);
      setNotice(`Role ${created.name} created.`);
      await load();
      chooseRole(created.id);
    } catch (err) {
      setError(err.message || 'Failed to create role.');
    }
  }

  async function removeRole() {
    if (!selectedRole) return;
    if (!window.confirm(`Delete role ${selectedRole.name}?`)) return;
    setError('');
    setNotice('');
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
    setError('');
    setNotice('');
    try {
      const roleIds = (userRoleDraft[userId] || []).map((value) => Number(value)).filter(Boolean);
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
      if (current.has(roleId)) current.delete(roleId);
      else current.add(roleId);
      return { ...prev, [userId]: [...current] };
    });
  }

  return (
    <div className="stack">
      <section className="section">
        <h1>Roles & Permissions</h1>
        <p className="muted">Checklist-style role permissions and user role assignment by workspace.</p>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <div className="grid-30-70">
        <section className="section role-list-panel">
          <h2>Roles</h2>
          <input
            type="search"
            placeholder="Search role name/code"
            value={roleSearch}
            onChange={(e) => setRoleSearch(e.target.value)}
            data-enter-context="search"
          />
          <div className="stack role-list">
            {filteredRoles.map((row) => (
              <button
                type="button"
                key={row.id}
                className={selectedRoleId === row.id ? 'tab active full-width role-chip' : 'tab full-width role-chip'}
                onClick={() => chooseRole(row.id)}
              >
                <span>{row.name}</span>
                <span className="small muted">{row.permission_count || 0}</span>
              </button>
            ))}
          </div>
          {!filteredRoles.length && <p className="muted">No matching roles found.</p>}
        </section>

        <section className="section">
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <h2>{selectedRole ? `Role: ${selectedRole.name}` : 'Create Role'}</h2>
            {selectedRole && (
              <button type="button" className="secondary" onClick={removeRole}>Delete Role</button>
            )}
          </div>

          <div className="stack">
            <div className="form-grid">
              <label>Code<input value={roleForm.code} onChange={(e) => setRoleForm((prev) => ({ ...prev, code: e.target.value }))} /></label>
              <label>Name<input value={roleForm.name} onChange={(e) => setRoleForm((prev) => ({ ...prev, name: e.target.value }))} /></label>
              <label>Active
                <select value={String(roleForm.is_active)} onChange={(e) => setRoleForm((prev) => ({ ...prev, is_active: e.target.value === 'true' }))}>
                  <option value="true">Active</option>
                  <option value="false">Inactive</option>
                </select>
              </label>
            </div>
            <label>Description<textarea value={roleForm.description} onChange={(e) => setRoleForm((prev) => ({ ...prev, description: e.target.value }))} /></label>
            <div className="row wrap">
              {!selectedRole && <button type="button" onClick={createNewRole}>Create Role</button>}
              {!!selectedRole && <button type="button" onClick={saveRoleMeta}>Save Role Details</button>}
            </div>
          </div>

          {!!selectedRole && (
            <div className="stack" style={{ marginTop: 16 }}>
              <div className="row wrap" style={{ justifyContent: 'space-between' }}>
                <h3>Permissions</h3>
                <label>
                  Copy From Role
                  <select defaultValue="" onChange={(e) => copyFromRole(e.target.value)}>
                    <option value="">Select</option>
                    {filteredRoles.filter((row) => row.id !== selectedRole.id).map((row) => (
                      <option key={row.id} value={row.id}>{row.name}</option>
                    ))}
                  </select>
                </label>
              </div>

              {Object.entries(groupedPermissions).map(([groupName, groupRows]) => {
                const checkedCount = groupRows.filter((row) => selectedPermissionKeys.has(row.key)).length;
                const allChecked = checkedCount === groupRows.length;
                return (
                  <section className="section" key={groupName} style={{ marginBottom: 0 }}>
                    <div className="row" style={{ justifyContent: 'space-between' }}>
                      <h3>{groupName}</h3>
                      <div className="row wrap">
                        <span className="small muted">{checkedCount}/{groupRows.length}</span>
                        <button type="button" className="secondary" onClick={() => toggleGroup(groupName, !allChecked)}>
                          {allChecked ? 'Unselect Group' : 'Select All in Group'}
                        </button>
                      </div>
                    </div>
                    <div className="form-grid" style={{ gridTemplateColumns: 'repeat(2, minmax(0, 1fr))' }}>
                      {groupRows.map((perm) => (
                        <label key={perm.key} className="toggle-field" style={{ alignItems: 'flex-start' }}>
                          <div>
                            <div className="toggle-label">{perm.label || perm.key}</div>
                            <div className="toggle-hint">{perm.key}</div>
                          </div>
                          <input
                            type="checkbox"
                            checked={selectedPermissionKeys.has(perm.key)}
                            onChange={() => togglePermission(perm.key)}
                          />
                        </label>
                      ))}
                    </div>
                  </section>
                );
              })}

              <button type="button" onClick={saveRolePermissions}>Save Role Permissions</button>
            </div>
          )}
        </section>
      </div>

      <section className="section">
        <h2>User Role Assignments</h2>
        <table className="table">
          <thead><tr><th>User</th><th>Legacy Role</th><th>Assigned Roles</th><th></th></tr></thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id}>
                <td>{user.username}<br /><span className="small muted">{user.full_name || '-'}</span></td>
                <td>{user.role || '-'}</td>
                <td>
                  <div className="row wrap">
                    {roles.map((role) => (
                      <label key={`${user.id}-${role.id}`} className="row" style={{ gap: 6 }}>
                        <input
                          type="checkbox"
                          checked={(userRoleDraft[user.id] || []).includes(role.id)}
                          onChange={() => toggleUserRole(user.id, role.id)}
                        />
                        <span className="small">{role.name}</span>
                      </label>
                    ))}
                  </div>
                </td>
                <td><button type="button" className="secondary" onClick={() => saveUserRoles(user.id)}>Save</button></td>
              </tr>
            ))}
            {!users.length && <tr><td colSpan="4" className="muted">No users found.</td></tr>}
          </tbody>
        </table>
      </section>
    </div>
  );
}
