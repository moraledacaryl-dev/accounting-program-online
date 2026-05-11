'use client';
import { useEffect, useMemo, useState } from 'react';
import { createMasterValue, deleteMasterValue, fetchMasterValues, updateMasterValue } from '../../lib/api';

const GROUPS = [
  { key: 'restaurant_categories', label: 'Restaurant' },
  { key: 'breakfast_categories', label: 'Breakfast' },
  { key: 'cafe_categories', label: 'Cafe' },
  { key: 'bar_categories', label: 'Bar' },
];

export default function MenuCategoriesPage() {
  const [groupName, setGroupName] = useState(GROUPS[0].key);
  const [value, setValue] = useState('');
  const [code, setCode] = useState('');
  const [isActive, setIsActive] = useState(true);
  const [rows, setRows] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [edit, setEdit] = useState({ value: '', code: '', is_active: true });
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const currentGroupLabel = useMemo(
    () => GROUPS.find((group) => group.key === groupName)?.label || groupName,
    [groupName]
  );

  async function load() {
    setError('');
    try {
      setRows(await fetchMasterValues('', false));
    } catch (err) {
      setError(err.message || 'Unable to load menu categories.');
    }
  }

  useEffect(() => { load().catch(console.error); }, []);

  async function submit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    if (!value.trim()) {
      setError('Category name is required.');
      return;
    }
    try {
      await createMasterValue({ group_name: groupName, value: value.trim(), code: code.trim(), is_active: isActive });
      setNotice('Category added.');
      setValue(''); setCode(''); setIsActive(true);
      await load();
    } catch (err) {
      setError(err.message || 'Unable to save category.');
    }
  }

  async function saveEdit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    if (!edit.value.trim()) {
      setError('Category name is required.');
      return;
    }
    try {
      await updateMasterValue(editingId, { ...edit, value: edit.value.trim(), code: edit.code.trim() });
      setNotice('Category updated.');
      setEditingId(null);
      setEdit({ value: '', code: '', is_active: true });
      await load();
    } catch (err) {
      setError(err.message || 'Unable to update category.');
    }
  }

  async function toggleActive(row) {
    setError('');
    setNotice('');
    try {
      await updateMasterValue(row.id, { ...row, is_active: !row.is_active });
      setNotice(row.is_active ? 'Category archived.' : 'Category restored.');
      await load();
    } catch (err) {
      setError(err.message || 'Unable to update category status.');
    }
  }

  async function removeCategory(row) {
    if (!confirm('Remove this archived category?')) return;
    setError('');
    setNotice('');
    try {
      await deleteMasterValue(row.id);
      setNotice('Category removed.');
      await load();
    } catch (err) {
      setError(err.message || 'Unable to remove category.');
    }
  }

  const filtered = useMemo(
    () => rows.filter((row) => row.group_name === groupName),
    [rows, groupName]
  );

  return (
    <div>
      <section className="section">
        <h1>Menu Categories</h1>
        <p className="muted">Menu categories are the shared source of truth for menu item setup, recipe assignment, and POS filters. Use this page to manage restaurant, breakfast, cafe, and bar categories. Active categories appear in Menu & Recipes.</p>
      </section>

      {!!notice && <p className="success-text">{notice}</p>}
      {!!error && <p className="error-text">{error}</p>}

      <div className="grid-30-70">
        <section className="section">
          <h2>Category groups</h2>
          <div className="stack">
            {GROUPS.map((group) => (
              <button
                key={group.key}
                type="button"
                className={groupName === group.key ? 'tab active full-width' : 'tab full-width'}
                onClick={() => { setGroupName(group.key); setEditingId(null); }}
              >
                {group.label}
              </button>
            ))}
          </div>
        </section>

        <section className="stack">
          <section className="section">
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <div>
                <h2>{currentGroupLabel}</h2>
                <p className="muted">Keep active values available to menu item setup. Archive categories instead of deleting them to preserve history and existing item assignments.</p>
              </div>
              <span className="badge">{filtered.length}</span>
            </div>

            <form onSubmit={editingId ? saveEdit : submit}>
              <div className="form-grid">
                <label>Category name<input required value={editingId ? edit.value : value} onChange={(e) => editingId ? setEdit((prev) => ({ ...prev, value: e.target.value })) : setValue(e.target.value)} /></label>
                <label>Optional code<input value={editingId ? edit.code : code} onChange={(e) => editingId ? setEdit((prev) => ({ ...prev, code: e.target.value })) : setCode(e.target.value)} /></label>
                <label>Status<select value={String(editingId ? edit.is_active : isActive)} onChange={(e) => editingId ? setEdit((prev) => ({ ...prev, is_active: e.target.value === 'true' })) : setIsActive(e.target.value === 'true')}>
                  <option value="true">Active</option>
                  <option value="false">Inactive</option>
                </select></label>
              </div>
              <button type="submit">{editingId ? 'Save changes' : 'Add category'}</button>
            </form>
          </section>

          <section className="section">
            <table className="table">
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Code</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => (
                  <tr key={row.id}>
                    <td>
                      {editingId === row.id ? (
                        <input value={edit.value} onChange={(e) => setEdit((prev) => ({ ...prev, value: e.target.value }))} />
                      ) : (
                        row.value
                      )}
                    </td>
                    <td>
                      {editingId === row.id ? (
                        <input value={edit.code || ''} onChange={(e) => setEdit((prev) => ({ ...prev, code: e.target.value }))} />
                      ) : (
                        row.code || '-'
                      )}
                    </td>
                    <td>
                      {editingId === row.id ? (
                        <select value={String(edit.is_active)} onChange={(e) => setEdit((prev) => ({ ...prev, is_active: e.target.value === 'true' }))}>
                          <option value="true">Active</option>
                          <option value="false">Inactive</option>
                        </select>
                      ) : (
                        row.is_active ? 'Active' : 'Inactive'
                      )}
                    </td>
                    <td className="row">
                      {editingId === row.id ? (
                        <>
                          <button type="button" className="secondary" onClick={saveEdit}>Save</button>
                          <button type="button" className="secondary" onClick={() => { setEditingId(null); setEdit({ value: '', code: '', is_active: true }); }}>Cancel</button>
                        </>
                      ) : (
                        <>
                          <button type="button" className="secondary" onClick={() => { setEditingId(row.id); setEdit({ value: row.value || '', code: row.code || '', is_active: !!row.is_active }); }}>
                            Edit
                          </button>
                          <button type="button" className="secondary" onClick={() => toggleActive(row)}>
                            {row.is_active ? 'Archive' : 'Restore'}
                          </button>
                          {!row.is_active && (
                            <button type="button" className="secondary" onClick={() => removeCategory(row)}>
                              Remove
                            </button>
                          )}
                        </>
                      )}
                    </td>
                  </tr>
                ))}
                {!filtered.length && (
                  <tr>
                    <td colSpan="4" className="muted">No categories yet for this group.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </section>
        </section>
      </div>
    </div>
  );
}
